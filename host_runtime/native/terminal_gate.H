// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_GATE_H
#define OPENBEXI_V08_TERMINAL_GATE_H
#include "admission_ipc.H"
#include "prompt_policy.H"
#include <map>
#include <mutex>
#include <set>

inline bool v08_terminal_command(const std::string& id)
{
    return id == "CMD_ABORT" || id == "CMD_CLOSE";
}

template<class Fields>
bool v08_terminal_valid(const std::string& id, bool oneway,
                        const Fields& fields, const std::string& instance)
{
    return v08_terminal_command(id) && oneway &&
        fields.size() == 2 + fields.count("User") &&
        fields.count("ProcId") && fields.at("ProcId") == instance &&
        fields.count("V08ControlRequest") &&
        v08_prompt_uuid(fields.at("V08ControlRequest"));
}

// One process-local journal shared by CIF and controller translation units.
// A failed/lost RPC is spent. Only a durable Context acknowledgement creates
// the one-use handoff to the original native controller.
inline std::mutex v08_terminal_mutex;
inline std::set<std::string> v08_terminal_attempts;
inline std::map<std::string, std::pair<std::string, std::string>> v08_terminal_ready;

inline void v08_admit_terminal(const std::string& instance,
                               const std::string& request, const std::string& command)
{
    {
        std::lock_guard<std::mutex> lock(v08_terminal_mutex);
        if (!v08_terminal_command(command) || !v08_prompt_uuid(request) ||
            v08_terminal_attempts.size() >= 512 || !v08_terminal_attempts.insert(request).second)
            throw std::runtime_error("Terminal command already attempted or invalid");
    }
    v08_native_request({{"schema", "openbexi.native-consume/1"},
                        {"instance_id", instance}, {"request_id", request},
                        {"command", command}});
    std::lock_guard<std::mutex> lock(v08_terminal_mutex);
    v08_terminal_ready.emplace(request, std::make_pair(instance, command));
}

inline void v08_take_terminal(const std::string& instance,
                              const std::string& request, const std::string& command)
{
    std::lock_guard<std::mutex> lock(v08_terminal_mutex);
    const auto found = v08_terminal_ready.find(request);
    if (found == v08_terminal_ready.end() ||
        found->second != std::make_pair(instance, command))
        throw std::runtime_error("Terminal command has no consumed CIF grant");
    v08_terminal_ready.erase(found);
}
#endif
