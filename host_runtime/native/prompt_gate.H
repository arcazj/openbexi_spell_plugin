// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_PROMPT_GATE_H
#define OPENBEXI_V08_PROMPT_GATE_H
#include "admission_ipc.H"
#include <fstream>
#include <cstdio>

static bool v08_prompt_enabled()
{
    const char* enabled = std::getenv("OPENBEXI_V08_PROMPT_PROTOCOL");
    return enabled && std::string(enabled) == "1";
}

static bool v08_prompt_uuid(const std::string& id)
{
    if (id.size() != 36) return false;
    for (size_t i = 0; i < id.size(); ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (id[i] != '-') return false;
        } else if (!((id[i] >= '0' && id[i] <= '9') ||
                     (id[i] >= 'a' && id[i] <= 'f'))) return false;
    }
    return true;
}

static std::string v08_prompt_identity()
{
    // Kernel-generated, single-use prompt identity. Never a controller token.
    std::ifstream random("/proc/sys/kernel/random/uuid");
    std::string value;
    if (!(random >> value) || !v08_prompt_uuid(value))
        throw std::runtime_error("Native prompt identity unavailable");
    return value;
}

static void v08_open_prompt(const std::string& instance, const std::string& prompt,
                           const nlohmann::json& definition)
{
    v08_native_request({{"schema", "openbexi.native-prompt-open/2"},
                        {"instance_id", instance}, {"prompt_id", prompt},
                        {"definition", definition}});
}

static void v08_consume_prompt(const std::string& instance,
                              const std::string& prompt, const SPELLipcMessage& msg)
{
    const bool answer = msg.getId() == "MSG_ANSWER";
    if ((!answer && msg.getId() != "MSG_CANCEL") || msg.getType() != MSG_TYPE_ONEWAY
        || !v08_prompt_uuid(prompt) || msg.get("V08PromptId") != prompt
        || !msg.hasField("V08PromptRequest")
        || !v08_prompt_uuid(msg.get("V08PromptRequest"))
        || msg.get(MessageField::FIELD_PROC_ID) != instance
        || (msg.hasField("ParentId") && !msg.get("ParentId").empty())
        || (answer && (!msg.hasField(MessageField::FIELD_RVALUE)
            || msg.get(MessageField::FIELD_RVALUE).size() > 4096
            || msg.get(MessageField::FIELD_RVALUE).find('\0') != std::string::npos))
        || (!answer && msg.hasField(MessageField::FIELD_RVALUE)))
        throw std::runtime_error("Native prompt reply scope denied");
    const char* hold = std::getenv("OPENBEXI_V08_PROMPT_CONSUME_PROBE");
    if (hold && std::string(hold) == "1") {
        std::ofstream marker("/workspace/prompt-awaiting");
        marker << "before-native-consumption"; marker.close();
        if (!marker) throw std::runtime_error("Native prompt probe marker failed");
        const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(12);
        while (access("/control/prompt-release", F_OK) != 0) {
            if (std::chrono::steady_clock::now() >= until)
                throw std::runtime_error("Native prompt probe release expired");
            usleep(10000);
        }
    }
    nlohmann::json payload = nullptr;
    if (answer) payload = msg.get(MessageField::FIELD_RVALUE);
    v08_native_request({{"schema", "openbexi.native-prompt-consume/1"},
                        {"instance_id", instance}, {"prompt_id", prompt},
                        {"reply_id", msg.get("V08PromptRequest")},
                        {"action", answer ? "ANSWER" : "CANCEL"}, {"answer", payload}});
}

static void v08_close_prompt(const std::string& instance, const std::string& prompt,
                            const std::string& outcome) noexcept
{
    if (prompt.empty()) return;
    try {
        v08_native_request({{"schema", "openbexi.native-prompt-close/1"},
                            {"instance_id", instance}, {"prompt_id", prompt},
                            {"outcome", outcome}});
    } catch (...) {
        // A lost close is not retried or treated as procedure/driver settlement.
        std::fprintf(stderr, "V08_NATIVE_PROMPT_CLOSE_UNCERTAIN\n");
    }
}
#endif
