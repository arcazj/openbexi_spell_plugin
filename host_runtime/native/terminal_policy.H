// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_POLICY_H
#define OPENBEXI_V08_TERMINAL_POLICY_H
#include <string>

inline bool v08_terminal_uuid(const std::string& value)
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

// No arguments, parent redirection or caller-asserted authorization flag.
// User is transport-added descriptive text, never the authenticated owner.
template<class Fields>
bool v08_terminal_message_valid(const std::string& operation, bool oneway,
                                const Fields& fields, const std::string& instance)
{
    if ((operation != "CMD_ABORT" && operation != "CMD_CLOSE") || !oneway)
        return false;
    if (fields.size() != 2 + fields.count("User") || !fields.count("ProcId") ||
        fields.at("ProcId") != instance || !fields.count("V08ControlRequest"))
        return false;
    return v08_terminal_uuid(fields.at("V08ControlRequest"));
}
#endif
