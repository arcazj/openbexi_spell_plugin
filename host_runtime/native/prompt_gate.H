// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_PROMPT_GATE_H
#define OPENBEXI_V08_PROMPT_GATE_H
#include "admission_ipc.H"
#include "prompt_policy.H"
#include <sys/random.h>

inline std::string v08_new_prompt_id()
{
    unsigned char bytes[16];
    size_t filled = 0;
    while (filled < sizeof(bytes)) {
        const auto count = getrandom(bytes + filled, sizeof(bytes) - filled, 0);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) throw std::runtime_error("Native prompt entropy unavailable");
        filled += static_cast<size_t>(count);
    }
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const char* hex = "0123456789abcdef";
    std::string id;
    for (size_t i = 0; i < sizeof(bytes); ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) id += '-';
        id += hex[bytes[i] >> 4];
        id += hex[bytes[i] & 15];
    }
    return id;
}

inline void v08_declare_prompt(const std::string& instance, const std::string& id,
                               const SPELLipcMessage& definition)
{
    nlohmann::json fields = nlohmann::json::object();
    for (const auto& field: definition.v08Fields()) fields[field.first] = field.second;
    // Hash the actual native definition in the pinned agent, not a user claim.
    // The raw definition is not inserted into the durable Context ledger.
    v08_native_request({{"schema", "openbexi.native-prompt-declare/1"},
                        {"instance_id", instance}, {"prompt_id", id},
                        {"definition", fields}});
}

inline void v08_consume_prompt(const std::string& instance, const SPELLipcMessage& msg)
{
    if (!v08_prompt_reply_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                msg.v08Fields(), instance))
        throw std::runtime_error("Native prompt reply shape denied");
    const bool answer = msg.getId() == "MSG_ANSWER";
    nlohmann::json value = nullptr;
    if (answer) value = msg.get("ReturnValue");
    v08_native_request({{"schema", "openbexi.native-prompt-consume/1"},
                        {"instance_id", instance}, {"prompt_id", msg.get("V08PromptId")},
                        {"reply_id", msg.get("V08PromptRequest")},
                        {"action", answer ? "ANSWER" : "CANCEL"}, {"answer", value}});
}

inline void v08_close_prompt(const std::string& instance, const std::string& id,
                             const std::string& outcome)
{
    v08_native_request({{"schema", "openbexi.native-prompt-close/1"},
                        {"instance_id", instance}, {"prompt_id", id},
                        {"outcome", outcome}});
}
#endif
