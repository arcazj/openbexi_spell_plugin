// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_ADMISSION_IPC_H
#define OPENBEXI_V08_ADMISSION_IPC_H
#include <nlohmann/json.hpp>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <unistd.h>
#include <chrono>
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

static void v08_native_request(const nlohmann::json& body)
{
    const char* path = std::getenv("OPENBEXI_V08_ADMISSION_SOCKET");
    const char* agent = std::getenv("OPENBEXI_V08_AGENT_PID");
    if (!path || !agent || std::strlen(path) >= sizeof(sockaddr_un::sun_path))
        throw std::runtime_error("Native admission provider unavailable");
    const std::string expectedAgent(agent);
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    if (fd < 0) throw std::runtime_error("Native admission socket unavailable");
    struct Close { int fd; ~Close() { close(fd); } } closeFd{fd};
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    std::strcpy(address.sun_path, path);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(4);
    auto ready = [&](short events) {
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
            deadline - std::chrono::steady_clock::now()).count();
        if (remaining <= 0) throw std::runtime_error("Native admission deadline expired");
        pollfd pending{fd, events, 0};
        if (poll(&pending, 1, static_cast<int>(remaining)) != 1
            || !(pending.revents & events))
            throw std::runtime_error("Native admission channel unavailable");
    };
    if (connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        if (errno != EINPROGRESS) throw std::runtime_error("Native admission connect denied");
        ready(POLLOUT);
        int error = 0; socklen_t size = sizeof(error);
        if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &size) != 0 || error)
            throw std::runtime_error("Native admission connect failed");
    }
    ucred peer{}; socklen_t size = sizeof(peer);
    if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &peer, &size) != 0
        || size != sizeof(peer) || peer.uid != getuid()
        || std::to_string(peer.pid) != expectedAgent)
        throw std::runtime_error("Native admission provider identity differs");
    const std::string packet = body.dump() + "\n";
    if (packet.size() > 32768) throw std::runtime_error("Native admission request too large");
    size_t sent = 0;
    while (sent < packet.size()) {
        ready(POLLOUT);
        const auto count = send(fd, packet.data() + sent, packet.size() - sent, MSG_NOSIGNAL);
        if (count <= 0) throw std::runtime_error("Native admission write uncertain");
        sent += static_cast<size_t>(count);
    }
    std::string reply;
    while (reply.find('\n') == std::string::npos && reply.size() < 16) {
        ready(POLLIN);
        char buffer[16];
        const auto count = recv(fd, buffer, sizeof(buffer), 0);
        if (count <= 0) throw std::runtime_error("Native admission reply lost");
        reply.append(buffer, static_cast<size_t>(count));
    }
    if (reply != "ALLOW\n") throw std::runtime_error("Native start admission denied");
}


#endif
