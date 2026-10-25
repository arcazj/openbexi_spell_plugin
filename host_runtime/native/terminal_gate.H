// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_GATE_H
#define OPENBEXI_V08_TERMINAL_GATE_H
#include "admission_ipc.H"
#include "prompt_policy.H"
#include "terminal_ticket.H"

inline bool v08_terminal_command(const std::string& command) {
    return command == "CMD_ABORT" || command == "CMD_CLOSE";
}
template<class Fields>
bool v08_terminal_message_valid(const std::string& command, bool oneway,
                                const Fields& fields, const std::string& instance) {
    return v08_terminal_command(command) && oneway &&
        fields.size() == 2 + fields.count("User") &&
        fields.count("ProcId") && fields.at("ProcId") == instance &&
        fields.count("V08ControlRequest") &&
        v08_prompt_uuid(fields.at("V08ControlRequest"));
}
inline void v08_admit_terminal_cif(const std::string& instance,
                                   const SPELLipcMessage& msg,
                                   const std::string& status,
                                   const std::string& prompt) {
    if (!v08_terminal_message_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                   msg.v08Fields(), instance))
        throw std::runtime_error("Native terminal scope/fields denied");
    const std::string request = msg.get("V08ControlRequest");
    v08_terminal::begin(instance, msg.getId(), request);
    nlohmann::json promptId = nullptr;
    if (!prompt.empty()) promptId = prompt;
    // SO_PEERCRED pins this request to the original native Executor; the agent
    // resolves this UUID to its independently delivered cryptographic grant.
    // Context verifies token hash + exact binding under mTLS and commits the
    // single-use transition and effect fence BEFORE ALLOW can return here.
    v08_native_request({{"schema", "openbexi.native-terminal-consume/1"},
                        {"instance_id", instance}, {"request_id", request},
                        {"command", msg.getId()}, {"native_status", status},
                        {"prompt_id", promptId}});
    v08_terminal::advance(instance, msg.getId(), request,
                         v08_terminal::Phase::ATTEMPTED,
                         v08_terminal::Phase::ADMITTED);
}
inline void v08_queue_terminal(const std::string& instance,
                               const std::string& command,
                               const std::string& request) {
    v08_terminal::advance(instance, command, request,
                         v08_terminal::Phase::ADMITTED,
                         v08_terminal::Phase::QUEUED);
}
inline void v08_claim_terminal(const std::string& instance,
                               const std::string& command,
                               const std::string& request) {
    v08_terminal::advance(instance, command, request,
                         v08_terminal::Phase::QUEUED,
                         v08_terminal::Phase::CLAIMED);
}
inline void v08_terminal_prompt_handled(const std::string& instance,
                                        const SPELLipcMessage& msg) noexcept {
    try {
        v08_terminal::advance(instance, msg.getId(), msg.get("V08ControlRequest"),
                             v08_terminal::Phase::ADMITTED,
                             v08_terminal::Phase::HANDLED);
        v08_native_request({{"schema", "openbexi.native-disposition/1"},
                            {"instance_id", instance},
                            {"request_id", msg.get("V08ControlRequest")},
                            {"command", msg.getId()},
                            {"disposition", "HANDLER_RETURNED"}});
    } catch (...) {
        // This is only a diagnostic. Never replay the terminal operation or
        // infer termination/effect settlement from a lost handler receipt.
        std::fprintf(stderr, "V08_NATIVE_TERMINAL_DISPOSITION_UNCERTAIN\n");
    }
}
#endif
