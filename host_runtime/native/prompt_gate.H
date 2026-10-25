// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_PROMPT_GATE_H
#define OPENBEXI_V08_PROMPT_GATE_H
#include "admission_ipc.H"
#include "prompt_state.H"
#include <sys/random.h>
#include <cstdio>

static bool v08_prompts_enabled() {
    const char* flag = std::getenv("OPENBEXI_V08_PROMPTS");
    return flag && std::string(flag) == "owner-bound/1";
}

static std::string v08_prompt_uuid() {
    unsigned char bytes[16]; size_t done = 0;
    while (done < sizeof(bytes)) {
        const auto n = getrandom(bytes + done, sizeof(bytes) - done, 0);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) throw std::runtime_error("Native prompt random identity unavailable");
        done += static_cast<size_t>(n);
    }
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const char* digits = "0123456789abcdef"; std::string value;
    for (size_t n = 0; n < sizeof(bytes); ++n) {
        if (n == 4 || n == 6 || n == 8 || n == 10) value += '-';
        value += digits[bytes[n] >> 4]; value += digits[bytes[n] & 15];
    }
    return value;
}

static void v08_register_prompt(const std::string& instance,
                                const V08PromptState& state,
                                const SPELLipcMessage& message) {
    // The pinned agent hashes this complete original definition canonically.
    // Neither a GUI nor the procedure supplies a digest to the registration.
    v08_native_request({{"schema", "openbexi.native-prompt-open/2"},
        {"instance_id", instance}, {"prompt_id", state.id},
        {"definition", message.v08Fields()}});
}

static bool v08_select_prompt(const std::string& instance, V08PromptState& state,
                              const SPELLipcMessage& message,
                              const std::string& action) noexcept {
    try {
        if (!state.active || message.getType() != MSG_TYPE_ONEWAY ||
            message.get("ProcId") != instance ||
            (message.hasField("ParentId") && !message.get("ParentId").empty()) ||
            !message.hasField("V08PromptId") || !message.hasField("V08PromptRequest") ||
            (action == "ANSWER") != message.hasField("ReturnValue"))
            throw std::runtime_error("Native prompt target differs");
        // Do not accept arguments for a different operation or future protocol.
        for (const auto& field : message.v08Fields()) {
            if (field.first != "ProcId" && field.first != "ParentId" &&
                field.first != "V08PromptId" && field.first != "V08PromptRequest" &&
                field.first != "ReturnValue")
                throw std::runtime_error("Native prompt reply fields differ");
        }
        const std::string reply = message.get("V08PromptRequest");
        state.begin(message.get("V08PromptId"), reply, action, V08PromptState::Clock::now());
        nlohmann::json answer = nullptr;
        if (action == "ANSWER") {
            const auto value = message.get("ReturnValue");
            if (value.size() > 4096 || value.find('\0') != std::string::npos)
                throw std::runtime_error("Native prompt answer exceeds bound");
            answer = value;
        }
        v08_native_request({{"schema", "openbexi.native-prompt-consume/1"},
            {"instance_id", instance}, {"prompt_id", state.id},
            {"reply_id", reply}, {"action", action}, {"answer", answer}});
        // The original deadline can pass during the bounded authorization RPC.
        // Consumed-but-late remains uncertain; it must NOT select an answer.
        state.selected(action, V08PromptState::Clock::now());
        return true;
    } catch (...) {
        return false; // No answer selection, wakeup, retry, or outcome invention.
    }
}

static void v08_close_prompt(const std::string& instance,
                             const V08PromptState& state) noexcept {
    if (state.id.empty()) return;
    try {
        v08_native_request({{"schema", "openbexi.native-prompt-close/1"},
            {"instance_id", instance}, {"prompt_id", state.id},
            {"outcome", state.outcome.empty() ? "UNKNOWN" : state.outcome}});
    } catch (...) {
        std::fprintf(stderr, "V08_NATIVE_PROMPT_CLOSE_UNCERTAIN\n");
    }
}
#endif
