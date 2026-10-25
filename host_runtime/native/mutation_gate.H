// SPDX-License-Identifier: GPL-3.0-or-later
#include "mutation_policy.H"
#include "admission_ipc.H"

static void v08_note_disabled_mutation(const std::string& instance,
                                      const std::string& operation) noexcept
{
    // This is a denial-only diagnostic. Neither an unavailable helper nor an
    // ALLOW reply can turn an unsupported operation into effect authority.
    try {
        std::string label = "UNSUPPORTED";
        bool bounded = !operation.empty() && operation.size() <= 64;
        if (bounded)
            for (const unsigned char ch: operation)
                if (!((ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_'))
                    bounded = false;
        if (bounded) label = operation;
        v08_native_request({{"schema", "openbexi.native-denied/1"},
                            {"instance_id", instance}, {"operation", label}});
    } catch (...) { }
}
