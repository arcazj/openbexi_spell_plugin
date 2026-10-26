// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_ADMISSION_CHANNEL_H
#define OPENBEXI_V08_ADMISSION_CHANNEL_H
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <unistd.h>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>

struct v08_admission_failure : std::runtime_error {
    const char* reason;
    int error;
    v08_admission_failure(const char* code, int number = 0)
        : std::runtime_error(code), reason(code), error(number) {}
};

// One absolute deadline covers connect, writes and reply. Waiting again on the
// same descriptor never replays the request or refreshes its captured authority.
static inline void v08_admission_wait(int fd, short events,
    std::chrono::steady_clock::time_point deadline, unsigned& interruptions)
{
    for (;;) {
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
            deadline - std::chrono::steady_clock::now()).count();
        if (remaining <= 0) throw v08_admission_failure("deadline_expired");
        pollfd pending{fd, events, 0};
        const int available = poll(&pending, 1, static_cast<int>(remaining));
        if (available < 0 && errno == EINTR) { ++interruptions; continue; }
        if (available < 0) throw v08_admission_failure("channel_unavailable", errno);
        // Readiness can precede a scheduler pause. It does not extend the
        // original deadline when this thread eventually resumes.
        if (std::chrono::steady_clock::now() >= deadline)
            throw v08_admission_failure("deadline_expired");
        if (available == 0) continue;
        if (!(pending.revents & events)) throw v08_admission_failure("channel_unavailable");
        return;
    }
}

static inline void v08_admission_exchange(const char* path,
    const std::string& expectedAgent, const std::string& packet)
{
    if (!path || std::strlen(path) >= sizeof(sockaddr_un::sun_path))
        throw v08_admission_failure("provider_unavailable");
    if (packet.size() > 32768) throw v08_admission_failure("request_too_large");
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    if (fd < 0) throw v08_admission_failure("socket_unavailable", errno);
    struct Close { int fd; ~Close() { close(fd); } } closeFd{fd};
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    std::strcpy(address.sun_path, path);
    const auto started = std::chrono::steady_clock::now();
    const auto deadline = started + std::chrono::seconds(4);
    unsigned interruptions = 0;
    const char* stage = "connect";
    try {
        if (connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
            if (errno != EINPROGRESS) throw v08_admission_failure("connect_denied", errno);
            v08_admission_wait(fd, POLLOUT, deadline, interruptions);
            int error = 0; socklen_t size = sizeof(error);
            if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &size) != 0)
                throw v08_admission_failure("connect_failed", errno);
            if (error) throw v08_admission_failure("connect_failed", error);
        }
        ucred peer{}; socklen_t size = sizeof(peer);
        if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &peer, &size) != 0)
            throw v08_admission_failure("provider_identity_unavailable", errno);
        if (size != sizeof(peer) || peer.uid != getuid()
            || std::to_string(peer.pid) != expectedAgent)
            throw v08_admission_failure("provider_identity_differs");
        stage = "write";
        size_t sent = 0;
        while (sent < packet.size()) {
            v08_admission_wait(fd, POLLOUT, deadline, interruptions);
            const auto count = send(fd, packet.data() + sent, packet.size() - sent, MSG_NOSIGNAL);
            if (count < 0 && errno == EINTR) { ++interruptions; continue; }
            if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) continue;
            if (count <= 0) throw v08_admission_failure("write_uncertain", count < 0 ? errno : 0);
            sent += static_cast<size_t>(count);
        }
        stage = "read";
        std::string reply;
        while (reply.find('\n') == std::string::npos && reply.size() < 16) {
            v08_admission_wait(fd, POLLIN, deadline, interruptions);
            char buffer[16];
            const auto count = recv(fd, buffer, sizeof(buffer), 0);
            if (count < 0 && errno == EINTR) { ++interruptions; continue; }
            if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) continue;
            if (count <= 0) throw v08_admission_failure("reply_lost", count < 0 ? errno : 0);
            reply.append(buffer, static_cast<size_t>(count));
        }
        // A complete reply is not authority to continue after the deadline.
        if (std::chrono::steady_clock::now() >= deadline)
            throw v08_admission_failure("deadline_expired");
        if (reply != "ALLOW\n") throw v08_admission_failure("admission_denied");
    } catch (const v08_admission_failure& error) {
        // Fixed labels and numeric metadata only: never log packets, paths,
        // arguments, capabilities or replies. Diagnostics grant no authority.
        const auto now = std::chrono::steady_clock::now();
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - started).count();
        const auto monotonic = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
        char record[384];
        const int size = std::snprintf(record, sizeof(record),
            "V08_ADMISSION {\"pid\":%ld,\"stage\":\"%s\",\"reason\":\"%s\",\"errno\":%d,\"elapsed_ms\":%lld,\"interruptions\":%u,\"monotonic_ns\":%lld}\n",
            static_cast<long>(getpid()), stage, error.reason, error.error,
            static_cast<long long>(elapsed), interruptions, static_cast<long long>(monotonic));
        if (size > 0 && static_cast<size_t>(size) < sizeof(record)) {
            const auto ignored = write(STDERR_FILENO, record, static_cast<size_t>(size));
            (void)ignored;
        }
        throw;
    }
}
#endif
