// SPDX-License-Identifier: GPL-3.0-or-later
// Actual production transport, real poll/signals and Unix peer credentials.
// Linker wrappers inject transient I/O faults without replacing the endpoint.
#include "admission_channel.H"
#include <atomic>
#include <cassert>
#include <csignal>
#include <iostream>
#include <thread>
#include <vector>
using namespace std::chrono_literals;
static std::string mode;
static int sends = 0, receives = 0;
static void interrupted(int) {}
extern "C" ssize_t __real_send(int, const void*, size_t, int);
extern "C" ssize_t __real_recv(int, void*, size_t, int);
extern "C" int __real_poll(struct pollfd*, nfds_t, int);
extern "C" int __wrap_poll(struct pollfd* fds, nfds_t count, int timeout) {
    const int result = __real_poll(fds, count, timeout);
    // Model a caller descheduled after readiness, without moving its deadline.
    if (mode == "wait_late_ready" && result > 0) std::this_thread::sleep_for(350ms);
    return result;
}
extern "C" ssize_t __wrap_send(int fd, const void* data, size_t size, int flags) {
    if (mode == "partial_io") {
        ++sends;
        if (sends <= 2) { errno = sends == 1 ? EINTR : EAGAIN; return -1; }
        size = std::min(size, size_t(3));
    }
    return __real_send(fd, data, size, flags);
}
extern "C" ssize_t __wrap_recv(int fd, void* data, size_t size, int flags) {
    if (mode == "partial_io") {
        ++receives;
        if (receives <= 2) { errno = receives == 1 ? EINTR : EAGAIN; return -1; }
        size = std::min(size, size_t(2));
    }
    const auto result = __real_recv(fd, data, size, flags);
    if (mode == "late_read" && result > 0) std::this_thread::sleep_for(4200ms);
    return result;
}

static void wait_case() {
    int descriptors[2]; assert(pipe(descriptors) == 0);
    const auto caller = pthread_self();
    std::atomic<bool> finished{false};
    std::thread writer([&] {
        for (int n = 0; n < 60 && !finished; ++n) {
            std::this_thread::sleep_for(10ms);
            if (finished) break;
            assert(pthread_kill(caller, SIGUSR1) == 0);
            if ((mode == "wait_interrupt" && n == 9) || mode == "wait_late_ready") {
                assert(write(descriptors[1], "x", 1) == 1);
                break;
            }
        }
    });
    unsigned interruptions = 0;
    const auto started = std::chrono::steady_clock::now();
    std::string failure;
    try { v08_admission_wait(descriptors[0], POLLIN, started + 300ms, interruptions); }
    catch (const v08_admission_failure& e) { failure = e.reason; }
    const auto elapsed = std::chrono::steady_clock::now() - started;
    finished = true; writer.join(); close(descriptors[0]); close(descriptors[1]);
    std::cerr << "wait result=" << failure << " elapsed_ms="
        << std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count() << "\n";
    if (mode == "wait_interrupt") assert(failure.empty());
    else { assert(failure == "deadline_expired"); assert(elapsed >= 290ms && elapsed < 1s); }
    if (mode != "wait_late_ready") assert(interruptions > 0);
    std::cout << "PASS " << mode << "\n";
}

int main(int argc, char** argv) {
    assert(argc == 3 || argc == 4); mode = argv[1];
    struct sigaction action{}; action.sa_handler = interrupted;
    sigemptyset(&action.sa_mask); assert(sigaction(SIGUSR1, &action, nullptr) == 0);
    signal(SIGPIPE, SIG_IGN);
    if (mode == "member_exchange") {
        assert(argc == 4);
        const auto started = std::chrono::steady_clock::now();
        std::string failure;
        try {
            v08_admission_exchange(argv[2], argv[3],
                "{\"schema\":\"openbexi.native-member/1\",\"instance_id\":\"main#1\",\"pid\":1234}\n");
        } catch (const v08_admission_failure& error) { failure = error.reason; }
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
        std::cout << "{\"admitted\":" << (failure.empty() ? "true" : "false")
            << ",\"reason\":\"" << failure << "\",\"elapsed_ms\":" << elapsed << "}\n";
        return 0;
    }
    if (mode.rfind("wait_", 0) == 0) { wait_case(); return 0; }
    if (mode == "oversize") {
        try { v08_admission_exchange(argv[2], std::to_string(getpid()), std::string(32769, 'x')); }
        catch (const v08_admission_failure& e) { assert(std::string(e.reason) == "request_too_large"); return 0; }
        assert(false);
    }
    int listener = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    assert(listener >= 0);
    sockaddr_un address{}; address.sun_family = AF_UNIX;
    assert(std::strlen(argv[2]) < sizeof(address.sun_path));
    std::strcpy(address.sun_path, argv[2]);
    assert(bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0);
    assert(listen(listener, 2) == 0);
    const auto caller = pthread_self();
    const std::string packet = "{\"fixed_request\":\"private-authority-must-not-appear-in-diagnostics\"}\n";
    std::string observed;
    std::atomic<bool> finished{false};
    std::thread provider([&] {
        pollfd pending{listener, POLLIN, 0}; assert(poll(&pending, 1, 2000) == 1);
        int peer = accept(listener, nullptr, nullptr); assert(peer >= 0);
        char buffer[128];
        while (observed.find('\n') == std::string::npos) {
            auto count = read(peer, buffer, sizeof(buffer));
            if (count <= 0) break;
            observed.append(buffer, static_cast<size_t>(count));
        }
        if (mode == "signal_reply") {
            for (int n = 0; n < 5 && !finished; ++n) {
                assert(pthread_kill(caller, SIGUSR1) == 0);
                std::this_thread::sleep_for(20ms);
            }
        }
        if (mode == "expired_reply" || mode == "signal_deadline") {
            for (int n = 0; n < 250 && !finished; ++n) {
                if (mode == "signal_deadline") assert(pthread_kill(caller, SIGUSR1) == 0);
                std::this_thread::sleep_for(20ms);
            }
        } else if (mode != "wrong_peer" && mode != "lost_reply") {
            const std::string reply = mode == "deny" ? "DENY\n" : "ALLOW\n";
            const auto ignored = write(peer, reply.data(), reply.size()); (void)ignored;
        }
        close(peer);
    });
    const auto started = std::chrono::steady_clock::now();
    std::string failure;
    try { v08_admission_exchange(argv[2], mode == "wrong_peer" ? "0" : std::to_string(getpid()), packet); }
    catch (const v08_admission_failure& e) { failure = e.reason; }
    const auto elapsed = std::chrono::steady_clock::now() - started;
    finished = true; provider.join();
    pollfd pending{listener, POLLIN, 0}; assert(poll(&pending, 1, 0) == 0);
    close(listener); unlink(argv[2]);
    if (mode == "wrong_peer") { assert(failure == "provider_identity_differs"); assert(observed.empty()); }
    else {
        assert(observed == packet); // Exact captured bytes once; no partial replay.
        if (mode == "deny") assert(failure == "admission_denied");
        else if (mode == "lost_reply") assert(failure == "reply_lost" || failure == "channel_unavailable");
        else if (mode == "expired_reply" || mode == "signal_deadline" || mode == "late_read") {
            assert(failure == "deadline_expired"); assert(elapsed >= 3900ms && elapsed < 5s);
        } else assert(failure.empty());
    }
    if (mode == "partial_io") assert(sends > 3 && receives >= 5);
    std::cout << "PASS " << mode << "\n";
}
