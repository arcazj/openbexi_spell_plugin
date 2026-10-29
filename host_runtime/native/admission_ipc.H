// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_ADMISSION_IPC_H
#define OPENBEXI_V08_ADMISSION_IPC_H
#include <nlohmann/json.hpp>
#include "admission_channel.H"
#include <cstdlib>
#include <fstream>
#include <fcntl.h>
#include <utility>

// Read the current inode for every admission, including after atomic epoch
// rotation. The former ifstream allocated an 8 KiB file buffer for each
// 36-byte identity; actual native samples show that buffer repeatedly freed
// into sanitizer quarantine. Never cache authority or borrow this stack data.
static std::string v08_read_runtime_epoch(const char* path)
{
    const int fd = ::open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) throw std::runtime_error("Native runtime epoch unavailable");
    struct Close { int fd; ~Close() { ::close(fd); } } closeEpoch{fd};
    char bytes[38];
    size_t used = 0;
    for (;;) {
        const auto count = ::read(fd, bytes + used, sizeof(bytes) - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) throw std::runtime_error("Native runtime epoch unavailable");
        if (count == 0) break;
        used += static_cast<size_t>(count);
        if (used == sizeof(bytes))
            throw std::runtime_error("Native runtime epoch unavailable");
    }
    // Preserve getline's accepted spelling: exactly 36 bytes, optionally
    // followed by one LF, then EOF. CRLF, a second line or trailing byte fails.
    if (!(used == 36 || (used == 37 && bytes[36] == '\n'))
        || std::memchr(bytes, '\n', 36))
        throw std::runtime_error("Native runtime epoch unavailable");
    return std::string(bytes, 36);
}

// An exclusively owned workspace may retain serialization capacity. Read the
// epoch once per call and restore its empty node only after that fresh read.
// The renderer and provider run synchronously; neither retains captured data.
template<class Render>
static inline void v08_native_request_in_place(
    nlohmann::json& captured, Render&& render,
    nlohmann::json::object_t::node_type* spareEpoch = nullptr)
{
    const char* epochPath = std::getenv("OPENBEXI_V08_RUNTIME_EPOCH");
    if (epochPath) {
        const auto current = v08_read_runtime_epoch(epochPath);
        if (spareEpoch && !spareEpoch->empty())
            captured.get_ref<nlohmann::json::object_t&>().insert(std::move(*spareEpoch));
        auto& epoch = captured["runtime_epoch"];
        if (epoch.is_string()) epoch.get_ref<nlohmann::json::string_t&>().assign(current);
        else epoch = current;
    }
    const char* path = std::getenv("OPENBEXI_V08_ADMISSION_SOCKET");
    const char* agent = std::getenv("OPENBEXI_V08_AGENT_PID");
    if (!path || !agent || std::strlen(path) >= sizeof(sockaddr_un::sun_path))
        throw std::runtime_error("Native admission provider unavailable");
    v08_admission_exchange(path, agent, render(captured));
}

// A temporary request already owns every JSON node exclusively. Consume that
// ownership for the synchronous exchange instead of copying the whole tree
// before adding the freshly read epoch. Never cache authority or share nodes
// between calls; captured still unwinds normally on denial or cancellation.
static inline void v08_native_request(nlohmann::json&& body)
{
    nlohmann::json captured = std::move(body);
    const char* epochPath = std::getenv("OPENBEXI_V08_RUNTIME_EPOCH");
    if (epochPath) {
        captured["runtime_epoch"] = v08_read_runtime_epoch(epochPath);
    }
    const char* path = std::getenv("OPENBEXI_V08_ADMISSION_SOCKET");
    const char* agent = std::getenv("OPENBEXI_V08_AGENT_PID");
    if (!path || !agent || std::strlen(path) >= sizeof(sockaddr_un::sun_path))
        throw std::runtime_error("Native admission provider unavailable");
    v08_admission_exchange(path, agent, captured.dump() + "\n");
}

// Preserve the original const-reference interface and caller-owned lvalues.
// Const rvalues also take this path: only a mutable JSON rvalue can be consumed.
static inline void v08_native_request(const nlohmann::json& body)
{
    v08_native_request(nlohmann::json(body));
}
#endif
