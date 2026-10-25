// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_MUTATION_POLICY_H
#define OPENBEXI_V08_MUTATION_POLICY_H
#include <string>

static bool v08_command_supported(const std::string& id)
{
    return id == "CMD_RUN" || id == "CMD_STEP" || id == "CMD_PAUSE";
}

static bool v08_message_disabled(const std::string& id, bool redirected)
{
    if (id == "MSG_ANSWER" || id == "MSG_CANCEL") return true;
    return id.compare(0, 4, "CMD_") == 0 &&
        (!v08_command_supported(id) || redirected);
}

// Defense in depth for copied/deferred commands marked external by the CIF.
static bool v08_external_command_disabled(const std::string& id, bool external)
{
    return external && !v08_command_supported(id);
}

static bool v08_request_supported(const std::string& id)
{
    // Private agent diagnostics only; this is not an observer read-scope ACL.
    return id == "REQ_GET_CONFIG" || id == "REQ_EXEC_STATUS" ||
        id == "REQ_GET_VARIABLES" || id == "REQ_WVARIABLES_ENABLED" ||
        id == "REQ_GET_RESOURCES" || id == "REQ_DRESOURCES_ENABLED" ||
        id == "REQ_GET_DICTIONARY";
}
#endif
