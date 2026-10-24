// SPDX-License-Identifier: GPL-3.0-or-later
// Private candidate only. Original v0.7 binaries are preserved.
#include "admission_ipc.H"

static void v08_consume_native_run(const std::string& instance, const ExecutorCommand& command)
{
    if (command.id != "CMD_RUN") return;
    if (command.v08Request.empty())
        throw std::runtime_error("Native RUN consumption has no admission identity");
    v08_native_request({
        {"schema", "openbexi.native-consume/1"},
        {"instance_id", instance},
        {"request_id", command.v08Request},
        {"command", "CMD_RUN"}
    });
}
