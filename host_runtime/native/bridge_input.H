// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <nlohmann/json.hpp>
#include <string>

// The request owns the returned string. Native transfer methods copy it before
// returning; neither a message nor a callback may retain this reference.
inline const std::string& v08BridgeString(const nlohmann::json& value)
{
    // get_ref has a different invalid-type exception. Preserve the original
    // get<string>() error id and text for every non-string JSON value.
    if (!value.is_string()) static_cast<void>(value.get<std::string>());
    return value.get_ref<const std::string&>();
}
