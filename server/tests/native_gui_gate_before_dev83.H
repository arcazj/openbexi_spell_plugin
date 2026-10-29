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
    // Build each final member directly. Initializer-list construction creates
    // temporary JSON arrays and copies the complete field tree. These objects
    // have one local owner; transfer the fields into the synchronous request.
    nlohmann::json body = nlohmann::json::object();
    body["schema"] = "openbexi.native-gui/1";
    body["key"] = message.getKey();
    body["operation"] = message.getId();
    body["request"] = request;
    body["fields"] = std::move(fields);
    v08_native_request(std::move(body));
}
