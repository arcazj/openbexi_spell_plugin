// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_TICKET_H
#define OPENBEXI_V08_TERMINAL_TICKET_H
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>

// This registry is NOT an authorization source. It carries a successful,
// durably consumed Context decision from the earliest CIF boundary to the
// original mailbox handler. Inline function-local statics are shared across
// translation units in the one independently qualified native runtime graph.
namespace v08_terminal {
enum class Phase { ATTEMPTED, ADMITTED, QUEUED, CLAIMED, HANDLED };
struct Ticket { std::string instance, command; Phase phase; };
inline std::mutex& mutex() { static std::mutex lock; return lock; }
inline std::map<std::string, Ticket>& tickets() {
    static std::map<std::string, Ticket> retained;
    return retained;
}
inline void begin(const std::string& instance, const std::string& command,
                  const std::string& request) {
    std::lock_guard<std::mutex> guard(mutex());
    if (instance.empty() || request.empty() ||
        (command != "CMD_ABORT" && command != "CMD_CLOSE") ||
        tickets().size() >= 512 || tickets().count(request))
        throw std::runtime_error("Native terminal attempt replay/capacity denied");
    tickets().emplace(request, Ticket{instance, command, Phase::ATTEMPTED});
}
inline void advance(const std::string& instance, const std::string& command,
                    const std::string& request, Phase expected, Phase next) {
    std::lock_guard<std::mutex> guard(mutex());
    auto found = tickets().find(request);
    if (found == tickets().end() || found->second.instance != instance ||
        found->second.command != command || found->second.phase != expected)
        throw std::runtime_error("Native terminal original ticket denied");
    found->second.phase = next;
}
} // namespace v08_terminal
#endif
