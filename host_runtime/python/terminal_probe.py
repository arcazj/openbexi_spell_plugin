"""Private native terminal cohort agent; host verifies whole-container cleanup."""

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import select
import signal
import time

CASES = frozenset(
    {
        "abort-paused",
        "close-paused",
        "abort-running",
        "close-running",
        "abort-prompt",
        "close-prompt",
        "cancel-prompt",
        "normal",
        "error",
        "timeout",
        "abort-thread",
        "abort-child",
        "close-thread",
        "close-child",
        "close-wait",
        "forced-loss",
    }
)


def run_terminal_probe(
    case, session, controls, admission, prompts, children, pump, lifecycle, emit
):
    if case not in CASES:
        raise ValueError("Unknown native terminal case")
    emit("native-terminal-ready", case=case)
    deadline = time.monotonic() + 70
    active = False
    killed = False
    state = "PAUSED"
    while time.monotonic() < deadline:
        controls.poll_owner()
        if prompts is not None:
            prompts.poll()
        with controls.lock:
            commands = [
                grant.command
                for _, grant in controls.owner_operations.values()
                if grant.command_id in controls.owner_consumed
            ]
        _pid, pidfd = admission.members[session.instance]
        if (
            case == "forced-loss"
            and not killed
            and Path("/control/kill-native").exists()
        ):
            # Explicit fault injection only in this isolated native test.
            # Never target a recycled numeric PID: its original pidfd is held.
            if select.select([pidfd], [], [], 0)[0]:
                raise RuntimeError("Native fault injection target already exited")
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            killed = True
        exited = bool(select.select([pidfd], [], [], 0)[0])
        if exited:
            if case == "forced-loss" and killed:
                state = "UNKNOWN"
                break
            if "CMD_CLOSE" not in commands:
                raise RuntimeError("Native process exited without an admitted CLOSE")
            state = "CLOSED"
            break
        try:
            pump()
            if children is not None and not any(
                value in {"CMD_ABORT", "CMD_CLOSE"} for value in commands
            ):
                children.service(session)
            state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        except Exception:
            if case == "forced-loss" and killed:
                if not select.select([pidfd], [], [], 5)[0]:
                    raise RuntimeError("Injected native process loss was not observed")
                state = "UNKNOWN"
                break
            if "CMD_CLOSE" not in commands:
                raise
            # The native process can disappear between the pidfd check and its
            # Context status query. Wait only for that original process's exit.
            if not select.select([pidfd], [], [], 5)[0]:
                raise RuntimeError("CLOSE status lost without native process exit")
            state = "CLOSED"
            break
        if not active:
            ready = (
                state == "WAITING"
                if case == "close-wait"
                else state == "PROMPT"
                if "prompt" in case
                else Path("/workspace/terminal-active").exists()
            )
            if ready:
                active = True
                emit("native-terminal-active", case=case, native_status=state)
        if state in {"FINISHED", "ERROR", "ABORTED"} and not case.startswith("close-"):
            break
        time.sleep(0.03)
    else:
        raise TimeoutError("Native terminal observation deadline expired")
    if state == "FINISHED" and lifecycle is not None:
        lifecycle.wait(lambda: list(controls.children.started), pump)
    until = time.monotonic() + 5
    while prompts is not None and prompts.active:
        if time.monotonic() >= until:
            raise RuntimeError("Native terminal left a prompt outcome unacknowledged")
        # After CLOSE the native channel can be gone; prompt settlement itself
        # was required before native closing and is acknowledged on private IPC.
        if state != "CLOSED":
            pump()
        time.sleep(0.02)
    emit(
        "native-terminal-observed",
        case=case,
        native_status=state,
        consumed_commands=commands,
        native_members=len(admission.members),
        pending_prompts=0,
        hold_retained=True,
        quiescence_proven=False,
    )
    # The independent host fences authority and captures the final family roster
    # before allowing this agent to enter its ordinary native cleanup path.
    deadline = time.monotonic() + 20
    while not Path("/control/terminal-cleanup").is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError("Host terminal settlement fence was not received")
        time.sleep(0.02)
