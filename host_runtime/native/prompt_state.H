// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_PROMPT_STATE_H
#define OPENBEXI_V08_PROMPT_STATE_H
#include <chrono>
#include <stdexcept>
#include <string>

// All methods are called under the original CIF's m_promptAnswerLock. This
// object is NOT a new scheduler or an authorization authority. It binds one
// original mailbox generation and prevents a lost RPC reply becoming a retry.
struct V08PromptState {
    using Clock = std::chrono::steady_clock;
    std::string id;
    std::string outcome;
    bool active = false;
    bool attempted = false;
    bool timed = false;
    unsigned opened = 0;
    Clock::time_point deadline{};

    static bool uuid(const std::string& value) {
        if (value.size() != 36) return false;
        for (size_t n = 0; n < value.size(); ++n) {
            if (n == 8 || n == 13 || n == 18 || n == 23) {
                if (value[n] != '-') return false;
            } else if (!((value[n] >= '0' && value[n] <= '9') ||
                         (value[n] >= 'a' && value[n] <= 'f'))) return false;
        }
        return true;
    }
    void open(const std::string& prompt) {
        if (active || !uuid(prompt) || prompt == id || opened >= 512)
            throw std::runtime_error("Native prompt generation unavailable");
        ++opened;
        id = prompt; outcome.clear(); active = true; attempted = false; timed = false;
    }
    void bound_deadline(Clock::time_point value) {
        if (!active || timed) throw std::runtime_error("Native prompt deadline differs");
        deadline = value; timed = true;
    }
    bool pending(Clock::time_point now) const {
        return active && outcome.empty() && (!timed || now < deadline);
    }
    void begin(const std::string& prompt, const std::string& reply,
               const std::string& action, Clock::time_point now) {
        if (!pending(now) || attempted || prompt != id || !uuid(reply) ||
            (action != "ANSWER" && action != "CANCEL"))
            throw std::runtime_error("Native prompt reply scope or deadline differs");
        attempted = true; // Before the first RPC byte; never undo on failure.
    }
    void selected(const std::string& action, Clock::time_point now) {
        if (!pending(now) || !attempted || (action != "ANSWER" && action != "CANCEL"))
            throw std::runtime_error("Native prompt selection unavailable");
        outcome = action == "ANSWER" ? "ANSWER_SELECTED" : "CANCEL_SELECTED";
    }
    void timeout() {
        if (!active || !outcome.empty())
            throw std::runtime_error("Native timeout cannot replace selected reply");
        outcome = "TIMEOUT";
    }
    void internal_cancel() {
        if (active && outcome.empty()) outcome = "UNKNOWN";
    }
    void finish() { active = false; }
};
#endif
