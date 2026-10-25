"""Private qualification of original native terminal actions; never release proof."""
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
import select
import time

CASES = frozenset(
    {"abort-paused", "abort-running", "abort-prompt", "normal", "error", "timeout"}
)


def qualify_worker_terminal(case, session, controls, admission, pump, lifecycle, emit):
    if case not in CASES:
        raise ValueError("Unknown native terminal profile")
    root = session.instance
    if set(admission.members) != {root}:
        raise RuntimeError("Single-member terminal fixture inventory differs")
    member_pidfd = admission.members[root][1]
    before_count = len(controls.owner_consumed)
    if before_count != 0:
        raise RuntimeError("Terminal fixture reused owner consumption")
    emit("native-terminal-ready", case=case, native_status="PAUSED")
    terminal_status = (
        "ABORTED"
        if case.startswith("abort-")
        else "ERROR"
        if case == "error"
        else "FINISHED"
    )
    intermediate = False
    until = time.monotonic() + 45
    while True:
        controls.poll_owner()
        pump()
        status = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if not intermediate and case in {"abort-running", "abort-prompt"}:
            expected = "RUNNING" if case == "abort-running" else "PROMPT"
            if status == expected and Path("/workspace/terminal-entered").is_file():
                intermediate = True
                emit("native-terminal-intermediate", case=case, native_status=status)
        if status == terminal_status:
            break
        if status in {"ABORTED", "ERROR", "FINISHED"}:
            raise RuntimeError("Native terminal fixture produced the wrong outcome")
        if time.monotonic() >= until:
            raise TimeoutError("Original native terminal outcome deadline expired")
        time.sleep(0.02)
    expected_commands = (
        ["CMD_ABORT"]
        if case == "abort-paused"
        else ["CMD_RUN", "CMD_ABORT"]
        if case.startswith("abort-")
        else ["CMD_RUN"]
    )
    consumed = [
        grant.command
        for identity, (_, grant) in controls.owner_operations.items()
        if identity in controls.owner_consumed
    ]
    if consumed != expected_commands or controls.consumed:
        raise RuntimeError("Native terminal consumption provenance differs")
    marker = Path("/workspace/terminal-result")
    if case.startswith("abort-"):
        if marker.exists():
            raise RuntimeError(
                "Aborted original procedure executed its forbidden continuation"
            )
        if case == "abort-paused" and Path("/workspace/terminal-entered").exists():
            raise RuntimeError("Paused ABORT executed a user statement")
    elif case == "error":
        if marker.exists() or not Path("/workspace/terminal-entered").is_file():
            raise RuntimeError("Native error fixture continued or never started")
    elif marker.read_text() != ("B" if case == "timeout" else "normal"):
        raise RuntimeError("Original native result differs")
    # The original engine only emits its 'finished' lifecycle event for FINISHED.
    # Do not invent a finish receipt for ABORTED/ERROR or count a status as effects
    # settlement. For FINISHED require the original durable audit acknowledgments.
    if terminal_status == "FINISHED":
        lifecycle.wait(lambda: [root], pump)
    emit(
        "native-terminal-outcome",
        case=case,
        native_status=status,
        admitted_owner_commands=len(consumed),
        outcome_observed=True,
        effects_settled=False,
        hold_retained=True,
        runtime_enabled=False,
    )
    until = time.monotonic() + 35
    while not any(
        identity in controls.owner_consumed and grant.command == "CMD_CLOSE"
        for identity, (_, grant) in controls.owner_operations.items()
    ):
        controls.poll_owner()
        if time.monotonic() >= until:
            raise TimeoutError("Fresh owner CLOSE did not reach original native CIF")
        time.sleep(0.02)
    # Wait for the ORIGINAL pidfd, not a PID/name scan or a worker-provided Boolean.
    # Do this before NativeSession.close() has a chance to terminate a process group.
    if not select.select([member_pidfd], [], [], 15)[0]:
        raise TimeoutError("Original native CLOSE did not terminate its Executor")
    emit(
        "native-terminal-close-exited",
        case=case,
        original_executor_exit_observed=True,
        host_teardown_used_for_executor=False,
        effects_settled=False,
        hold_retained=True,
        runtime_enabled=False,
    )
