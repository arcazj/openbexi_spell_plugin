// SPDX-License-Identifier: GPL-3.0-or-later
// Production JSON capture and Unix admission transport, with real peer identity.
#include "admission_ipc.H"
#include <atomic>
#include <cassert>
#include <dirent.h>
#include <iostream>
#include <pthread.h>
#include <thread>
#include <vector>

using Json = nlohmann::json;
using Request = void (*)(const Json&);
static_assert(std::is_same_v<decltype(static_cast<Request>(&v08_native_request)), Request>);
static constexpr const char* A = "11111111-1111-4111-8111-111111111111";
static constexpr const char* B = "22222222-2222-4222-8222-222222222222";
static std::string epochPath;
static thread_local bool measuring = false;
static thread_local uint64_t allocations = 0, allocatedBytes = 0;
static std::atomic<const volatile void*> watched{nullptr};
static std::atomic<unsigned> watchedFrees{0};
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*, size_t), void (*)(const volatile void*));
extern "C" size_t __sanitizer_get_current_allocated_bytes(void);
static void allocated(const volatile void*, size_t bytes) {
    if (measuring) { ++allocations; allocatedBytes += bytes; }
}
static void freed(const volatile void* pointer) {
    if (pointer && pointer == watched.load()) ++watchedFrees;
}

static Json body(const std::string& key, bool alternate = false) {
    return {{"schema", "openbexi.native-gui/1"}, {"key", key},
            {"operation", "REQ_STATUS"}, {"request", true},
            {"fields", {{"CommandId", "RUN"}, {"Description", std::string(160, 'x')},
                        {"ExecId", "ROOT#1"}, {"Quoted", "line\n\"value\""},
                        {"Value", alternate ? "B" : "A"}}}};
}
// Independent byte oracle: no JSON encoder is used to make the expected wire.
static std::string wire(const std::string& key, const std::string& epoch, bool alternate = false) {
    return "{\"fields\":{\"CommandId\":\"RUN\",\"Description\":\"" + std::string(160, 'x')
        + "\",\"ExecId\":\"ROOT#1\",\"Quoted\":\"line\\n\\\"value\\\"\",\"Value\":\""
        + (alternate ? "B" : "A") + "\"},\"key\":\"" + key
        + "\",\"operation\":\"REQ_STATUS\",\"request\":true,\"runtime_epoch\":\""
        + epoch + "\",\"schema\":\"openbexi.native-gui/1\"}\n";
}
static void rotate(const std::string& value) {
    const auto next = epochPath + ".next";
    const int fd = open(next.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    assert(fd >= 0);
    assert(write(fd, value.data(), value.size()) == static_cast<ssize_t>(value.size()));
    assert(close(fd) == 0 && rename(next.c_str(), epochPath.c_str()) == 0);
}
static int descriptorCount() {
    auto* directory = opendir("/proc/self/fd"); assert(directory);
    int count = 0; while (readdir(directory)) ++count; closedir(directory); return count;
}
struct Server {
    int listener;
    std::string path;
    explicit Server(const char* value) : path(value) {
        listener = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0); assert(listener >= 0);
        sockaddr_un address{}; address.sun_family = AF_UNIX;
        assert(path.size() < sizeof(address.sun_path)); std::strcpy(address.sun_path, path.c_str());
        assert(bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0);
        assert(listen(listener, 64) == 0);
    }
    ~Server() { close(listener); unlink(path.c_str()); }
    int acceptRequest(std::string& packet) {
        pollfd pending{listener, POLLIN, 0}; assert(poll(&pending, 1, 5000) == 1);
        const int peer = accept(listener, nullptr, nullptr); assert(peer >= 0);
        char bytes[512];
        while (packet.find('\n') == std::string::npos) {
            const auto count = read(peer, bytes, sizeof(bytes)); assert(count > 0);
            packet.append(bytes, static_cast<size_t>(count)); assert(packet.size() <= 32768);
        }
        return peer;
    }
};
static void reply(int peer, bool allow = true) {
    const std::string value = allow ? "ALLOW\n" : "DENY\n";
    assert(write(peer, value.data(), value.size()) == static_cast<ssize_t>(value.size()));
    assert(close(peer) == 0);
}
static void setup(const char* path) {
    const auto pid = std::to_string(getpid());
    assert(setenv("OPENBEXI_V08_RUNTIME_EPOCH", epochPath.c_str(), 1) == 0);
    assert(setenv("OPENBEXI_V08_ADMISSION_SOCKET", path, 1) == 0);
    assert(setenv("OPENBEXI_V08_AGENT_PID", pid.c_str(), 1) == 0);
    rotate(A);
}

static void ownership(Server& server) {
    std::thread provider([&] {
        for (int i = 0; i < 4; ++i) {
            std::string packet; const int peer = server.acceptRequest(packet);
            assert(packet == wire("owned", i < 2 ? A : B));
            if (i == 1) rotate(B);
            reply(peer);
        }
    });
    Json lvalue = body("owned"); const Json original = lvalue;
    Request compatibility = &v08_native_request;
    compatibility(lvalue); assert(lvalue == original);
    v08_native_request(lvalue); assert(lvalue == original);
    const Json immutable = original;
    v08_native_request(std::move(immutable)); assert(immutable == original);
    Json moved = original; watched = moved.get_ptr<Json::object_t*>(); watchedFrees = 0;
    v08_native_request(std::move(moved));
#ifdef V08_OWNED_BODY
    assert(moved.is_null() && watchedFrees == 1);
#else
    assert(moved == original && watchedFrees == 0);
#endif
    watched = nullptr;
    provider.join();
    std::cout << "{\"legacy_const_reference\":true,\"lvalue_unchanged\":true,\"const_rvalue_unchanged\":true,\"fresh_epoch_rotation\":true,\"exact_wire_bytes\":true}\n";
}

static void failures(Server& server) {
    std::atomic<unsigned> received{0};
    std::thread provider([&] {
        for (int i = 0; i < 3; ++i) {
            std::string packet; const int peer = server.acceptRequest(packet);
            assert(packet == wire("failure", i < 2 ? A : B)); ++received;
            if (i == 0) reply(peer, false);
            else if (i == 1) { rotate(B); close(peer); }
            else reply(peer);
        }
    });
    Json original = body("failure"); const auto preserved = original;
    try { v08_native_request(original); assert(false); }
    catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "admission_denied"); }
    assert(original == preserved);
    Json moved = preserved; watched = moved.get_ptr<Json::object_t*>(); watchedFrees = 0;
    try { v08_native_request(std::move(moved)); assert(false); }
    catch (const v08_admission_failure& error) {
        assert(std::string(error.reason) == "reply_lost" || std::string(error.reason) == "channel_unavailable");
    }
#ifdef V08_OWNED_BODY
    assert(moved.is_null() && watchedFrees == 1);
#endif
    watched = nullptr;
    v08_native_request(body("failure"));
    provider.join(); assert(received == 3);
    pollfd pending{server.listener, POLLIN, 0}; assert(poll(&pending, 1, 0) == 0);
    rotate("too-short");
    for (bool move : {false, true}) {
        Json current = preserved;
        try {
            if (move) v08_native_request(std::move(current)); else v08_native_request(current);
            assert(false);
        } catch (const std::runtime_error& error) {
            assert(std::string(error.what()) == "Native runtime epoch unavailable");
        }
        if (!move) assert(current == preserved);
#ifdef V08_OWNED_BODY
        else assert(current.is_null());
#endif
    }
    rotate(B);
    Json invalid = body("invalid"); invalid["fields"]["Value"] = std::string("\xff", 1);
    const Json invalidCopy = invalid;
    try { v08_native_request(invalid); assert(false); }
    catch (const Json::type_error&) {}
    assert(invalid == invalidCopy);
    try { v08_native_request(std::move(invalid)); assert(false); }
    catch (const Json::type_error&) {}
#ifdef V08_OWNED_BODY
    assert(invalid.is_null());
#endif
    assert(poll(&pending, 1, 0) == 0);
    std::cout << "{\"denial_preserved\":true,\"uncertain_reply_not_replayed\":true,\"exception_ownership\":true,\"malformed_epoch_rejected_before_send\":true,\"serialization_exception_unwinds\":true}\n";
}

static void concurrency(Server& server) {
    constexpr int callers = 8, calls = 32;
    std::atomic<bool> done{false}; std::atomic<int> received{0};
    std::thread rotator([&] { unsigned n = 0; while (!done) { rotate((++n % 2) ? B : A); std::this_thread::yield(); } });
    std::thread provider([&] {
        bool seen[callers][calls]{};
        for (int count = 0; count < callers * calls; ++count) {
            std::string packet; const int peer = server.acceptRequest(packet);
            const auto parsed = Json::parse(packet); const auto key = parsed.at("key").get<std::string>();
            int thread = -1, index = -1; assert(std::sscanf(key.c_str(), "%d-%d", &thread, &index) == 2);
            assert(thread >= 0 && thread < callers && index >= 0 && index < calls && !seen[thread][index]);
            seen[thread][index] = true;
            const auto epoch = parsed.at("runtime_epoch").get<std::string>(); assert(epoch == A || epoch == B);
            assert(packet == wire(key, epoch, index % 2)); reply(peer); ++received;
        }
    });
    std::vector<std::thread> clients;
    for (int t = 0; t < callers; ++t) clients.emplace_back([t] {
        for (int index = 0; index < calls; ++index) {
            Json request = body(std::to_string(t) + "-" + std::to_string(index), index % 2);
            const auto original = request;
            if (index % 2) {
                v08_native_request(request); assert(request == original);
            } else {
                v08_native_request(std::move(request));
#ifdef V08_OWNED_BODY
                assert(request.is_null());
#endif
            }
        }
    });
    for (auto& client : clients) client.join();
    done = true; rotator.join(); provider.join(); assert(received == callers * calls);
    std::cout << "{\"parallel_requests\":256,\"independent_owned_bodies\":true,\"live_epoch_rotation\":true,\"stale_or_cross_caller_fields\":false}\n";
}

static void cancellation(Server& server) {
    const int before = descriptorCount();
    std::atomic<bool> received{false}, cancelled{false};
    std::thread provider([&] {
        std::string packet; const int peer = server.acceptRequest(packet);
        assert(packet == wire("cancelled", A)); received = true;
        while (!cancelled) std::this_thread::yield();
        close(peer);
    });
    pthread_t caller{};
    assert(pthread_create(&caller, nullptr, [](void*) -> void* {
        Json request = body("cancelled");
        watched = request.get_ptr<Json::object_t*>(); watchedFrees = 0;
        struct Ownership {
            Json& request;
            ~Ownership() {
#ifdef V08_OWNED_BODY
                assert(request.is_null() && watchedFrees == 1);
#endif
            }
        } ownership{request};
        v08_native_request(std::move(request)); assert(false); return nullptr;
    }, nullptr) == 0);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
    while (!received) { assert(std::chrono::steady_clock::now() < deadline); std::this_thread::yield(); }
    assert(pthread_cancel(caller) == 0); void* status = nullptr;
    assert(pthread_join(caller, &status) == 0 && status == PTHREAD_CANCELED);
    cancelled = true; provider.join(); watched = nullptr;
    assert(before == descriptorCount());
    std::cout << "{\"cancelled_sync_exchange\":true,\"owned_json_destroyed_once\":true,\"owned_socket_closed\":true}\n";
}

static void benchmark(Server& server, bool lvalue) {
    constexpr int requests = 10000;
    const auto original = body("0");
    const auto beforeCopyCalls = allocations, beforeCopyBytes = allocatedBytes;
    measuring = true; Json copied = original; measuring = false;
    const auto copyCalls = allocations - beforeCopyCalls, copyBytes = allocatedBytes - beforeCopyBytes;
    uint64_t wireHash = UINT64_C(14695981039346656037), wireBytes = 0;
    std::thread provider([&] {
        for (int index = -1; index < requests; ++index) {
            const auto key = index < 0 ? "warmup" : std::to_string(index);
            std::string packet; const int peer = server.acceptRequest(packet);
            assert(packet == wire(key, index < requests / 2 ? A : B, index >= 0 && index % 2));
            if (index >= 0) for (unsigned char byte : packet) { wireHash ^= byte; wireHash *= UINT64_C(1099511628211); ++wireBytes; }
            if (index == requests / 2 - 1) rotate(B);
            reply(peer);
        }
    });
    v08_native_request(body("warmup"));
    const auto beforeCalls = allocations, beforeBytes = allocatedBytes;
    const auto liveBefore = __sanitizer_get_current_allocated_bytes();
    for (int index = 0; index < requests; ++index) {
        Json request = body(std::to_string(index), index % 2);
        measuring = true;
        if (lvalue) v08_native_request(request); else v08_native_request(std::move(request));
        measuring = false;
    }
    const auto afterCalls = allocations, afterBytes = allocatedBytes;
    provider.join();
    const auto liveAfter = __sanitizer_get_current_allocated_bytes();
    std::cout << "{\"requests\":" << requests << ",\"caller_allocations\":" << afterCalls - beforeCalls
        << ",\"caller_allocated_bytes\":" << afterBytes - beforeBytes
        << ",\"one_body_copy_allocations\":" << copyCalls << ",\"one_body_copy_bytes\":" << copyBytes
        << ",\"wire_fnv1a64\":" << wireHash << ",\"wire_bytes\":" << wireBytes
        << ",\"all_packets_match_independent_literal_oracle\":true,\"fresh_epoch_rotation\":true"
        << ",\"lvalue\":" << (lvalue ? "true" : "false")
        << ",\"live_before\":" << liveBefore << ",\"live_after\":" << liveAfter
        << ",\"component_only\":true,\"whole_family_qualified\":false}\n";
}

int main(int argc, char** argv) {
    assert(argc == 4); const std::string mode = argv[1]; epochPath = argv[2];
    assert(__sanitizer_install_malloc_and_free_hooks(allocated, freed) > 0);
    setup(argv[3]); Server server(argv[3]);
    if (mode == "ownership") ownership(server);
    else if (mode == "failures") failures(server);
    else if (mode == "concurrency") concurrency(server);
    else if (mode == "cancellation") cancellation(server);
    else if (mode == "benchmark") benchmark(server, false);
    else if (mode == "benchmark-lvalue") benchmark(server, true);
    else assert(false);
}
