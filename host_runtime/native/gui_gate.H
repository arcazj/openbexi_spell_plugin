// SPDX-License-Identifier: GPL-3.0-or-later
#include "admission_ipc.H"

static void v08_admit_gui(const SPELLipcMessage& message, bool request)
{
    nlohmann::json fields = nlohmann::json::object();
    for (const auto& field: message.v08Fields()) {
        // The legacy input layer adds this descriptive socket user label.
        // It is neither an owner subject nor a credential.
        if (field.first != "User") fields[field.first] = field.second;
    }
    v08_native_request({{"schema", "openbexi.native-gui/1"},
                        {"key", message.getKey()},
                        {"operation", message.getId()},
                        {"request", request}, {"fields", fields}});
}
