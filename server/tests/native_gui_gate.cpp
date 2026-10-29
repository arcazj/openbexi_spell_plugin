// SPDX-License-Identifier: GPL-3.0-or-later
// Exact production GUI gate and message class; unchanged real Unix admission.
#include "SPELL_IPC/SPELLipcMessage.H"
#include "gui_gate.H"
#include <atomic>
#include <cassert>
#include <iostream>
#include <thread>
#include <vector>

using Json = nlohmann::json;
static constexpr const char* A = "11111111-1111-4111-8111-111111111111";
static constexpr const char* B = "22222222-2222-4222-8222-222222222222";
static std::string epochPath;
static thread_local bool measuring = false;
static thread_local uint64_t allocations = 0, allocatedBytes = 0;
#ifdef V08_GUI_WORKSPACE
static thread_local bool trackingWorkspace = false;
struct TrackedAllocation { const volatile void* pointer = nullptr; size_t bytes = 0; };
static thread_local TrackedAllocation trackedWorkspace[4096];
static thread_local size_t workspaceLive = 0, workspacePeak = 0;
#endif
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*, size_t), void (*)(const volatile void*));
static void allocated(const volatile void* pointer, size_t bytes) {
    if (measuring) { ++allocations; allocatedBytes += bytes; }
#ifdef V08_GUI_WORKSPACE
    if (trackingWorkspace) {
        bool recorded = false;
        for (auto& allocation : trackedWorkspace) if (!allocation.pointer) {
            allocation = {pointer, bytes}; workspaceLive += bytes;
            workspacePeak = std::max(workspacePeak, workspaceLive); recorded = true; break;
        }
        assert(recorded);
    }
#else
    (void)pointer;
#endif
}
static void freed(const volatile void* pointer) {
#ifdef V08_GUI_WORKSPACE
    if (trackingWorkspace) for (auto& allocation : trackedWorkspace) if (allocation.pointer == pointer) {
        workspaceLive -= allocation.bytes; allocation = {}; break;
    }
#else
    (void)pointer;
#endif
}
static void rotate(const std::string& value) {
    const auto next = epochPath + ".next";
    const int fd = open(next.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    assert(fd >= 0);
    assert(write(fd, value.data(), value.size()) == static_cast<ssize_t>(value.size()));
    assert(close(fd) == 0 && rename(next.c_str(), epochPath.c_str()) == 0);
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

static SPELLipcMessage guiMessage(int key, int shape) {
    SPELLipcMessage message(shape == 3 ? std::string("REQ_\xc3\xa9\"STATUS") : "REQ_STATUS");
    message.setKey(key);
    message.set("User", "descriptive socket label: never authority");
    if (shape != 3) {
        message.set("CommandId", "RUN"); message.set("ExecId", "ROOT#1");
        message.set("Value", shape == 1 ? std::string(513, 'v') : "42");
    }
    if (shape == 1) message.set("Description", std::string(160, 'x'));
    if (shape == 2) {
        message.set("Quoted", "line\n\t\"value\"\\end");
        message.set(std::string("Nul\0Key", 7), std::string("\xc3\xa9\0\xe2\x98\x83", 6));
    }
    return message;
}

// Independent byte oracle, deliberately using no JSON library.
static std::string quoted(const std::string& text) {
    static constexpr char hex[] = "0123456789abcdef";
    std::string result = "\"";
    for (unsigned char c : text) {
        switch (c) {
            case '"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default:
                if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
                else result += static_cast<char>(c);
        }
    }
    return result + "\"";
}
static std::string guiWire(const SPELLipcMessage& message, bool request, const std::string& epoch) {
    std::string wire = "{\"fields\":{"; bool comma = false;
    for (const auto& field : message.v08Fields()) {
        if (field.first == "User") continue;
        if (comma) wire += ',';
        wire += quoted(field.first) + ':' + quoted(field.second); comma = true;
    }
    return wire + "},\"key\":" + std::to_string(message.getKey())
        + ",\"operation\":" + quoted(message.getId()) + ",\"request\":" + (request ? "true" : "false")
        + ",\"runtime_epoch\":" + quoted(epoch) + ",\"schema\":\"openbexi.native-gui/1\"}\n";
}
static void guiBenchmark(Server& server, int shape, int count) {
    uint64_t hash = UINT64_C(14695981039346656037), bytes = 0;
    std::thread provider([&] {
        for (int n = 0; n < count; ++n) {
            std::string packet; const int peer = server.acceptRequest(packet);
            const auto expected = guiMessage(n - 7, shape);
            assert(packet == guiWire(expected, n % 2 == 0, n < count / 2 ? A : B));
            for (unsigned char c : packet) { hash ^= c; hash *= UINT64_C(1099511628211); ++bytes; }
            if (n == count / 2 - 1) rotate(B);
            reply(peer);
        }
    });
    uint64_t calls = 0, allocated = 0;
    for (int n = 0; n < count; ++n) {
        const auto message = guiMessage(n - 7, shape);
        const auto original = message.v08Fields(); const auto id = message.getId();
        const auto beforeCalls = allocations, beforeBytes = allocatedBytes;
        measuring = true; v08_admit_gui(message, n % 2 == 0); measuring = false;
        calls += allocations - beforeCalls; allocated += allocatedBytes - beforeBytes;
        assert(message.v08Fields() == original && message.getId() == id && message.getKey() == n - 7);
    }
    provider.join();
    std::cout << "{\"requests\":" << count << ",\"shape\":" << shape
        << ",\"caller_allocations\":" << calls << ",\"caller_allocated_bytes\":" << allocated
        << ",\"wire_fnv1a64\":" << hash << ",\"wire_bytes\":" << bytes
        << ",\"independent_wire_oracle\":true,\"caller_message_unchanged\":true,\"fresh_epoch_rotation\":true,\"component_only\":true}\n";
}
static void guiFailures(Server& server) {
    const auto message = guiMessage(17, 2); const auto original = message.v08Fields();
    std::thread provider([&] {
        for (int n = 0; n < 3; ++n) {
            std::string packet; const int peer = server.acceptRequest(packet);
            assert(packet == guiWire(message, true, n < 2 ? A : B));
            if (n == 0) reply(peer, false);
            else if (n == 1) { rotate(B); close(peer); }
            else reply(peer);
        }
    });
    try { v08_admit_gui(message, true); assert(false); }
    catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "admission_denied"); }
    try { v08_admit_gui(message, true); assert(false); }
    catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "reply_lost" || std::string(error.reason) == "channel_unavailable"); }
    v08_admit_gui(message, true); provider.join();
    assert(message.v08Fields() == original);
    pollfd pending{server.listener, POLLIN, 0}; assert(poll(&pending, 1, 0) == 0);
    rotate("too-short");
    try { v08_admit_gui(message, true); assert(false); }
    catch (const std::runtime_error& error) { assert(std::string(error.what()) == "Native runtime epoch unavailable"); }
    rotate(B);
    auto invalid = message; invalid.set("Value", std::string("\xff", 1));
    const auto invalidOriginal = invalid.v08Fields();
    try { v08_admit_gui(invalid, true); assert(false); }
    catch (const Json::type_error&) {}
    assert(invalid.v08Fields() == invalidOriginal && message.v08Fields() == original);
    auto large = message; large.set("Value", std::string(32768, 'x'));
    try { v08_admit_gui(large, true); assert(false); }
    catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "request_too_large"); }
    assert(poll(&pending, 1, 0) == 0);
    std::cout << "{\"denial_preserved\":true,\"uncertain_reply_not_replayed\":true,\"invalid_epoch_utf8_size_fail_before_send\":true,\"caller_message_unchanged\":true}\n";
}
static void guiConcurrent(Server& server) {
    constexpr int callers = 8, count = 32;
    std::thread provider([&] {
        bool seen[callers][count]{};
        for (int n = 0; n < callers * count; ++n) {
            std::string packet; const int peer = server.acceptRequest(packet);
            const auto parsed = Json::parse(packet); const auto key = parsed.at("key").get<int>();
            const int thread = key / 1000, index = key % 1000;
            assert(thread >= 0 && thread < callers && index >= 0 && index < count && !seen[thread][index]);
            seen[thread][index] = true;
            assert(packet == guiWire(guiMessage(key, index % 4), index % 2 == 0, A)); reply(peer);
        }
    });
    std::vector<std::thread> clients;
    for (int t = 0; t < callers; ++t) clients.emplace_back([t] {
        for (int n = 0; n < count; ++n) {
            const auto message = guiMessage(t * 1000 + n, n % 4); const auto original = message.v08Fields();
            v08_admit_gui(message, n % 2 == 0); assert(message.v08Fields() == original);
        }
    });
    for (auto& client : clients) client.join();
    provider.join();
    std::cout << "{\"parallel_requests\":256,\"independent_fields\":true,\"caller_message_unchanged\":true}\n";
}

#ifdef V08_GUI_EXCHANGE_COMPONENT
// Explicit test sink: only JSON construction, fresh epoch input, serialization
// and exception ownership execute here. This is not a Unix transport pass.
static thread_local std::string componentExpected;
static thread_local int componentFailure = 0;
static thread_local uint64_t componentHash = UINT64_C(14695981039346656037), componentBytes = 0, componentPackets = 0;
static thread_local void (*componentHook)(const std::string&) = nullptr;
static inline void v08_admission_exchange(const char*, const std::string&, const std::string& packet) {
    if (packet.size() > 32768) throw v08_admission_failure("request_too_large");
    assert(packet == componentExpected); ++componentPackets;
    for (unsigned char byte : packet) { componentHash ^= byte; componentHash *= UINT64_C(1099511628211); ++componentBytes; }
    if (componentFailure == 1) throw v08_admission_failure("admission_denied");
    if (componentFailure == 2) throw v08_admission_failure("reply_lost");
    if (componentHook) componentHook(packet);
}
static void componentBenchmark(int shape) {
    constexpr int count = 10000;
    uint64_t calls = 0, allocated = 0;
    for (int n = 0; n < count; ++n) {
        if (n == count / 2) rotate(B);
        const auto message = guiMessage(n - 7, shape); const auto original = message.v08Fields();
        componentExpected = guiWire(message, n % 2 == 0, n < count / 2 ? A : B);
        const auto beforeCalls = allocations, beforeBytes = allocatedBytes;
        measuring = true; v08_admit_gui(message, n % 2 == 0); measuring = false;
        calls += allocations - beforeCalls; allocated += allocatedBytes - beforeBytes;
        assert(message.v08Fields() == original && message.getKey() == n - 7);
    }
    assert(componentPackets == count);
    std::cout << "{\"requests\":" << count << ",\"shape\":" << shape
        << ",\"caller_allocations\":" << calls << ",\"caller_allocated_bytes\":" << allocated
        << ",\"wire_fnv1a64\":" << componentHash << ",\"wire_bytes\":" << componentBytes
        << ",\"independent_wire_oracle\":true,\"caller_message_unchanged\":true,\"fresh_epoch_rotation\":true"
        << ",\"physical_unix_transport_executed\":false,\"component_only\":true}\n";
}
static void componentFailures() {
    const auto message = guiMessage(17, 2); const auto original = message.v08Fields();
    componentExpected = guiWire(message, true, A);
    for (int reason : {1, 2}) {
        componentFailure = reason;
        try { v08_admit_gui(message, true); assert(false); }
        catch (const v08_admission_failure& error) {
            assert(std::string(error.reason) == (reason == 1 ? "admission_denied" : "reply_lost"));
        }
        assert(message.v08Fields() == original);
    }
    componentFailure = 0; rotate(B); componentExpected = guiWire(message, true, B);
    v08_admit_gui(message, true); assert(componentPackets == 3);
    rotate("too-short");
    try { v08_admit_gui(message, true); assert(false); }
    catch (const std::runtime_error& error) { assert(std::string(error.what()) == "Native runtime epoch unavailable"); }
    rotate(B);
    auto invalid = message; invalid.set("Value", std::string("\xff", 1));
    const auto invalidOriginal = invalid.v08Fields();
    try { v08_admit_gui(invalid, true); assert(false); }
    catch (const Json::type_error&) {}
    assert(invalid.v08Fields() == invalidOriginal && message.v08Fields() == original && componentPackets == 3);
    std::cout << "{\"injected_denial_and_reply_loss_preserved\":true,\"fresh_epoch_failure_preserved\":true,"
        << "\"serialization_exception_unwinds\":true,\"caller_message_unchanged\":true,\"physical_unix_transport_executed\":false}\n";
}
#endif
#ifdef V08_GUI_WORKSPACE
extern "C" size_t __sanitizer_get_current_allocated_bytes();
static constexpr size_t workspaceStringBound = 64 * (128 + 4096) + 65536 + 1024;
static void workspaceCheck(const V08GuiAdmissionWorkspace& workspace) {
    assert(workspace.empty()); assert(workspace.retainedFields() <= 64);
    assert(workspace.retainedStringCapacity() <= workspaceStringBound);
}
static void workspaceBoundaries() {
    componentExpected.reserve(131072);
    auto shortMessage = guiMessage(3, 0), longMessage = guiMessage(4, 1), unicode = guiMessage(5, 2);
    auto huge = guiMessage(6, 0); huge.set("Value", std::string(70000, 'x'));
    const auto before = __sanitizer_get_current_allocated_bytes();
    size_t maximumRetainedBytes = 0, maximumCapacity = 0, maximumFields = 0;
    const auto observe = [&](const V08GuiAdmissionWorkspace& workspace) {
        workspaceCheck(workspace);
        maximumRetainedBytes = std::max(maximumRetainedBytes, workspaceLive);
        maximumCapacity = std::max(maximumCapacity, workspace.retainedStringCapacity());
        maximumFields = std::max(maximumFields, workspace.retainedFields());
    };
    trackingWorkspace = true;
    {
        V08GuiAdmissionWorkspace workspace;
        trackingWorkspace = false;
        for (unsigned n = 0; n < 1000; ++n) {
            const auto& message = n % 3 == 0 ? longMessage : n % 3 == 1 ? shortMessage : unicode;
            componentExpected = guiWire(message, n % 2 == 0, A);
            trackingWorkspace = true; workspace.admit(message, n % 2 == 0); trackingWorkspace = false;
            observe(workspace);
        }
        // Arbitrary alternating schemas must not grow the retained key set.
        for (unsigned n = 0; n < 200; ++n) {
            auto message = shortMessage; message.set("New-" + std::to_string(n), std::string(4000, 'x'));
            componentExpected = guiWire(message, true, A);
            trackingWorkspace = true; workspace.admit(message, true); trackingWorkspace = false;
            observe(workspace);
        }
        // The normal provider limit rejects this oversized request. Releasing
        // its staging storage must not retain the large payload or poison the
        // next valid request's schema, fields or UTF-8 state.
        componentExpected = guiWire(huge, true, A);
        trackingWorkspace = true;
        try { workspace.admit(huge, true); assert(false); }
        catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "request_too_large"); }
        trackingWorkspace = false; observe(workspace);
        for (int reason : {1, 2}) {
            componentFailure = reason; componentExpected = guiWire(shortMessage, true, A);
            trackingWorkspace = true;
            try { workspace.admit(shortMessage, true); assert(false); }
            catch (const v08_admission_failure&) {} trackingWorkspace = false; observe(workspace);
        }
        componentFailure = 0;
        auto invalid = shortMessage; invalid.set("Value", std::string("\xff", 1));
        trackingWorkspace = true;
        try { workspace.admit(invalid, true); assert(false); }
        catch (const Json::type_error&) {} trackingWorkspace = false; observe(workspace);
        // Removing an epoch variable after an earlier valid request omits the
        // key completely. Restoring it re-reads an atomically rotated inode.
        assert(unsetenv("OPENBEXI_V08_RUNTIME_EPOCH") == 0);
        componentExpected = guiWire(shortMessage, true, A);
        const auto field = std::string(",\"runtime_epoch\":\"") + A + "\"";
        componentExpected.erase(componentExpected.find(field), field.size());
        trackingWorkspace = true; workspace.admit(shortMessage, true); trackingWorkspace = false;
        observe(workspace);
        assert(setenv("OPENBEXI_V08_RUNTIME_EPOCH", epochPath.c_str(), 1) == 0);
        rotate("too-short");
        trackingWorkspace = true;
        try { workspace.admit(shortMessage, true); assert(false); }
        catch (const std::runtime_error&) {} trackingWorkspace = false; observe(workspace);
        rotate(B); componentExpected = guiWire(shortMessage, true, B);
        trackingWorkspace = true; workspace.admit(shortMessage, true); trackingWorkspace = false;
        observe(workspace);
        const auto provider = std::string(std::getenv("OPENBEXI_V08_ADMISSION_SOCKET"));
        assert(unsetenv("OPENBEXI_V08_ADMISSION_SOCKET") == 0);
        trackingWorkspace = true;
        try { workspace.admit(invalid, true); assert(false); }
        catch (const Json::type_error&) { assert(false); }
        catch (const std::runtime_error& error) {
            assert(std::string(error.what()) == "Native admission provider unavailable");
        }
        trackingWorkspace = false; observe(workspace);
        assert(setenv("OPENBEXI_V08_ADMISSION_SOCKET", provider.c_str(), 1) == 0);
        componentExpected = guiWire(shortMessage, true, B);
        trackingWorkspace = true; workspace.admit(shortMessage, true); trackingWorkspace = false;
        observe(workspace);
        trackingWorkspace = true;
    }
    trackingWorkspace = false; assert(workspaceLive == 0);
    // This measures live ASan allocations, not RSS/quarantine. The original
    // message class has a separate bounded node cache, so no family claim or
    // exact process-wide zero-delta assertion is made here.
    std::cout << "{\"passed\":true,\"physical_unix_transport_executed\":false,\"workspaces\":1,"
        << "\"maximum_retained_heap_allocation_bytes\":" << maximumRetainedBytes
        << ",\"maximum_in_call_heap_allocation_bytes\":" << workspacePeak
        << ",\"workspace_object_bytes\":" << sizeof(V08GuiAdmissionWorkspace)
        << ",\"tracked_allocation_bytes_after_destruction\":" << workspaceLive
        << ",\"maximum_retained_string_capacity\":" << maximumCapacity
        << ",\"maximum_retained_fields\":" << maximumFields
        << ",\"retained_string_capacity_bound\":" << workspaceStringBound
        << ",\"post_destroy_process_live_allocation_delta_bytes\":"
        << (static_cast<int64_t>(__sanitizer_get_current_allocated_bytes()) - static_cast<int64_t>(before)) << "}\n";
}
static void workspaceConcurrent() {
    std::atomic<unsigned> entered{0}; std::atomic<bool> go{false};
    std::atomic<size_t> maximumCapacity{0}; std::vector<std::thread> clients;
    for (int thread = 0; thread < 8; ++thread) clients.emplace_back([&, thread] {
        ++entered; while (!go.load()) std::this_thread::yield();
        for (int n = 0; n < 1000; ++n) {
            auto message = guiMessage(thread * 1000 + n, n % 4); const auto original = message.v08Fields();
            componentExpected = guiWire(message, n % 2 == 0, A);
            v08_admit_gui(message, n % 2 == 0); assert(original == message.v08Fields());
            auto& workspace = v08_gui_workspace(); workspaceCheck(workspace);
            const auto capacity = workspace.retainedStringCapacity(); auto prior = maximumCapacity.load();
            while (prior < capacity && !maximumCapacity.compare_exchange_weak(prior, capacity)) {}
        }
        assert(componentPackets == 1000);
    });
    while (entered.load() != 8) std::this_thread::yield();
    go = true;
    for (auto& client : clients) client.join();
    std::cout << "{\"passed\":true,\"physical_unix_transport_executed\":false,\"parallel_requests\":8000,"
        << "\"workspaces\":8,\"maximum_per_workspace_string_capacity\":" << maximumCapacity.load() << "}\n";
}
static void workspaceNested(const std::string& outerPacket) {
    const auto saved = outerPacket; const auto expected = componentExpected;
    assert(v08_gui_workspace().busy);
    componentHook = nullptr;
    auto message = guiMessage(99, 2); componentExpected = guiWire(message, false, A);
    v08_admit_gui(message, false);
    componentFailure = 1;
    try { v08_admit_gui(message, false); assert(false); }
    catch (const v08_admission_failure& error) { assert(std::string(error.reason) == "admission_denied"); }
    componentFailure = 0;
    assert(outerPacket == saved && v08_gui_workspace().busy);
    componentExpected = expected;
}
static void workspaceReentrant() {
    auto message = guiMessage(1, 0); const auto original = message.v08Fields();
    componentExpected = guiWire(message, true, A); componentHook = workspaceNested;
    v08_admit_gui(message, true); assert(componentPackets == 3 && message.v08Fields() == original);
    workspaceCheck(v08_gui_workspace());
    std::cout << "{\"passed\":true,\"physical_unix_transport_executed\":false,\"peak_workspaces\":2,\"outer_packet_unchanged\":true}\n";
}
#endif
int main(int argc, char** argv) {
    assert(argc == 4); epochPath = argv[2];
    assert(__sanitizer_install_malloc_and_free_hooks(allocated, freed) > 0);
    setup(argv[3]); const std::string mode = argv[1];
#ifdef V08_GUI_WORKSPACE
    if (mode == "workspace-boundaries") { workspaceBoundaries(); return 0; }
    if (mode == "workspace-concurrency") { workspaceConcurrent(); return 0; }
    if (mode == "workspace-reentrant") { workspaceReentrant(); return 0; }
#endif
#ifdef V08_GUI_EXCHANGE_COMPONENT
    if (mode == "component-failures") { componentFailures(); return 0; }
    if (mode.rfind("component-", 0) == 0) { componentBenchmark(std::stoi(mode.substr(10))); return 0; }
#endif
    Server server(argv[3]);
    if (mode == "failures") guiFailures(server);
    else if (mode == "concurrency") guiConcurrent(server);
    else { const int shape = std::stoi(mode); assert(shape >= 0 && shape <= 3); guiBenchmark(server, shape, 10000); }
}
