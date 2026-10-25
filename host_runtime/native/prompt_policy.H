// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_PROMPT_POLICY_H
#define OPENBEXI_V08_PROMPT_POLICY_H
#include <string>

inline bool v08_prompt_uuid(const std::string& value)
{
    if (value.size() != 36) return false;
    for (size_t i = 0; i < value.size(); ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (value[i] != '-') return false;
        } else if (!((value[i] >= '0' && value[i] <= '9') ||
                     (value[i] >= 'a' && value[i] <= 'f'))) return false;
    }
    return true;
}

// Transport-added User is descriptive only. No parent redirection or spare
// fields may bypass the exact prompt generation/member check at the mailbox.
template<class Fields>
bool v08_prompt_reply_valid(const std::string& operation, bool oneway,
                            const Fields& fields, const std::string& instance)
{
    const bool answer = operation == "MSG_ANSWER";
    if ((!answer && operation != "MSG_CANCEL") || !oneway) return false;
    const size_t expected = (answer ? 4 : 3) + fields.count("User");
    if (fields.size() != expected || !fields.count("ProcId") ||
        fields.at("ProcId") != instance || !fields.count("V08PromptId") ||
        !v08_prompt_uuid(fields.at("V08PromptId")) ||
        !fields.count("V08PromptRequest") ||
        !v08_prompt_uuid(fields.at("V08PromptRequest"))) return false;
    if (answer) {
        if (!fields.count("ReturnValue")) return false;
        const std::string& value = fields.at("ReturnValue");
        if (value.size() > 4096 || value.find('\0') != std::string::npos) return false;
    } else if (fields.count("ReturnValue")) return false;
    return true;
}
#endif
