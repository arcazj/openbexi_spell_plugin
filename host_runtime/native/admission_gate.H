// SPDX-License-Identifier: GPL-3.0-or-later
// Private local native provider. Context RPC remains certificate authenticated.
#include "admission_ipc.H"
#include "mutation_policy.H"

static void v08_admit_native_start(SPELLexecutorModel& model, bool reconnecting)
{
    // Recovery/reconnect is never a fresh admission. Check before IPC setup,
    // process replacement/kill, spawning, or automatic hidden-child execution.
    if (reconnecting || !model.getWsFilename().empty()
        || !model.getCondition().empty())
        throw std::runtime_error("Native recovery/conditional start is unqualified");
    const int mode = static_cast<int>(model.getOpenMode());
    const int supported = OPEN_MODE_AUTOMATIC | OPEN_MODE_BLOCKING | OPEN_MODE_VISIBLE;
    if (mode & ~supported) throw std::runtime_error("Native open mode unqualified");
    const nlohmann::json body = {
        {"schema", "openbexi.native-start/1"},
        {"instance_id", model.getInstanceId()},
        {"parent_instance_id", model.getParentInstanceId()},
        {"entrypoint", model.getProcId() + ".py"},
        {"arguments", model.getArguments()},
        {"mode", {{"automatic", bool(mode & OPEN_MODE_AUTOMATIC)},
                  {"blocking", bool(mode & OPEN_MODE_BLOCKING)},
                  {"visible", bool(mode & OPEN_MODE_VISIBLE)}}}
    };
    v08_native_request(body);
}


static void v08_admit_native_run(SPELLexecutorModel& model, const SPELLipcMessage& message)
{
    const std::string command = message.getId();
    // Close alternate native peer paths before a mutating command or prompt
    // response reaches the Executor. Ordinary lifecycle traffic is unchanged.
    if (v08_context_forward_disabled(command))
        throw std::runtime_error("Native Context forwarding mutation denied");
    if (command != "CMD_RUN" && command != "CMD_STEP" && command != "CMD_PAUSE") return;
    if (!message.hasField("V08ControlRequest"))
        throw std::runtime_error("Native RUN has no immutable admission identity");
    // The Executor can redirect commands bearing ParentId to a child. Fresh
    // grants name one member, so never admit this alternative target path.
    if (message.hasField("ParentId") && !message.get("ParentId").empty())
        throw std::runtime_error("Native command redirection is unqualified");
    v08_native_request({
        {"schema", "openbexi.native-control/1"},
        {"instance_id", model.getInstanceId()},
        {"request_id", message.get("V08ControlRequest")},
        {"command", command}
    });
}

static void v08_bind_native_executor(SPELLexecutorModel& model)
{
    v08_native_request({
        {"schema", "openbexi.native-member/1"},
        {"instance_id", model.getInstanceId()},
        {"pid", model.getPID()}
    });
}
