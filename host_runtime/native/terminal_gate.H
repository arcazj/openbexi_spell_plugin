// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_GATE_H
#define OPENBEXI_V08_TERMINAL_GATE_H
#include "admission_ipc.H"
#include "terminal_policy.H"

static void v08_terminal_authorize(const std::string& instance,
                                  const std::string& operation,
                                  const std::string& request,
                                  const std::string& stage)
{
    if ((operation != "CMD_ABORT" && operation != "CMD_CLOSE") ||
        !v08_terminal_uuid(request) ||
        (stage != "preprocess" && stage != "execute"))
        throw std::runtime_error("Native terminal operation identity differs");
    // SO_PEERCRED pins the protected agent. The agent authenticates this
    // exact Executor PID/executable/incarnation and supplies its memory-only
    // original worker capability and owner-command token over pinned mTLS.
    // ALLOW is returned only AFTER Context's durable one-shot transaction.
    // Timeout, malformed response, denial or lost ACK never yields permission.
    v08_native_request({{"schema", "openbexi.native-terminal/1"},
                        {"instance_id", instance}, {"command", operation},
                        {"request_id", request}, {"stage", stage}});
}
#endif
