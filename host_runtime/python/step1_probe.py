"""Operator-owned full-native Step 1 qualification loop, never a public runtime.

Uses only fresh owner/prompt grants from the real Context, the original native
CIF/Executor and pidfds pinned before procedure execution. Does not synthesize
terminal statuses, release reservations or grant ownership transfer.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import select
import time


CASES = frozenset(
    {
        "normal",
        "failure",
        "answer",
        "cancel",
        "timeout",
        "abort-running",
        "abort-prompt",
        "close-running",
        "family",
        "forced-loss",
        "driver",
        "timeout-answer",
        "timeout-cancel",
        "duplicate-prompt",
        "late-prompt",
    }
)
TERMINAL = frozenset({"FINISHED", "ERROR", "ABORTED"})


def run(
    case,
    *,
    session,
    controls,
    prompts,
    admission,
    children,
    child_gate,
    lifecycle,
    pump,
    emit,
    budget=90,
):
    if case not in CASES or not controls.terminal or prompts is None:
        raise ValueError("Explicit terminal-enabled Step 1 qualification required")
    # An operator test instruction may only delay an authenticated callback;
    # it cannot fabricate a grant/receipt, change an action or repeat an effect.
    if case in {"timeout-answer", "timeout-cancel"}:
        original = prompts.consume
        delayed = False

        def delay_consumption(body):
            nonlocal delayed
            if delayed:
                raise ValueError("Step 1 delayed consumption already attempted")
            delayed = True
            emit("step1-prompt-consumption-waiting")
            end = time.monotonic() + 2
            while time.monotonic() < end:
                time.sleep(0.01)
            # Original Context still decides, under the same live-grant checks.
            # Native timeout/close is permitted to win while this call is delayed.
            return original(body)

        prompts.consume = delay_consumption
    if case in {"duplicate-prompt", "late-prompt"}:
        # Retain the exact already-dispatched IPC fields for an adversarial replay.
        # No owner token is exposed; the replay must fail at the native boundary.
        original = controls.original
        sent = []

        def capture(identifier, fields=None, **kwargs):
            answer = original(identifier, fields, **kwargs)
            if identifier in {"MSG_ANSWER", "MSG_CANCEL"}:
                sent.append((identifier, dict(fields or {}), dict(kwargs)))
            return answer

        controls.original = capture
    else:
        sent = []
    statuses, closed, seen_pids = {}, set(), set()
    denied_replayed = False
    end = time.monotonic() + budget
    emit("step1-owner-ready", case=case, native_status="PAUSED")
    while time.monotonic() < end:
        pump()
        controls.poll_owner()
        prompts.poll()
        if children is not None:
            # After a terminal admission no new child or startup RUN may acquire
            # effects. Existing children are retained for explicit owner cleanup.
            with controls.lock:
                stopping = any(
                    grant.command in {"CMD_ABORT", "CMD_CLOSE"}
                    for _, grant in controls.owner_operations.values()
                    if grant.command_id in controls.owner_consumed
                )
            if not stopping:
                children.service(session)
        with controls.lock:
            closes = {
                target
                for identity, (target, grant) in controls.owner_operations.items()
                if grant.command == "CMD_CLOSE" and identity in controls.owner_consumed
            }
        for instance, (pid, handle) in list(admission.members.items()):
            if pid not in seen_pids:
                seen_pids.add(pid)
                emit("step1-member-pinned", member=instance, namespace_pid=pid)
            exited = bool(select.select([handle], [], [], 0)[0])
            if instance in closes:
                if exited and instance not in closed:
                    closed.add(instance)
                    emit(
                        "step1-native-closed",
                        member=instance,
                        prior_status=statuses.get(instance, "UNKNOWN"),
                        original_pidfd_exited=True,
                    )
                continue
            if exited:
                # A real child may be closed by its original native parent.
                # Its original durable finish event is independently required.
                if instance not in closed:
                    with lifecycle.lock:
                        finished = lifecycle.counts.get((instance, "finished")) == 1
                    if instance == session.instance or not finished:
                        raise RuntimeError(
                            "Native member disappeared without original terminal evidence"
                        )
                    closed.add(instance)
                    emit(
                        "step1-native-child-closed",
                        member=instance,
                        original_pidfd_exited=True,
                        original_finish_receipt=True,
                    )
                continue
            # Never address a known closed instance or redirect through ParentId.
            state = session.request("REQ_EXEC_INFO", context=True, procedure=instance)[
                "ExecutorStatus"
            ]
            if state not in {
                "LOADED",
                "PAUSED",
                "RUNNING",
                "WAITING",
                "PROMPT",
                "INTERRUPTED",
                *TERMINAL,
            }:
                raise RuntimeError("Unqualified native lifecycle state")
            if statuses.get(instance) != state:
                statuses[instance] = state
                emit("step1-native-state", member=instance, native_status=state)
        # Probe unauthorized original IPC before any permitted response.
        if Path("/control/inject-unowned").is_file() and not denied_replayed:
            with prompts.lock:
                active = list(prompts.active.items())
            if active:
                instance, prompt = active[0]
                controls.original(
                    "MSG_ANSWER",
                    {
                        "V08PromptId": prompt,
                        "V08PromptRequest": "00000000-0000-4000-8000-000000000001",
                        "ReturnValue": "N",
                    },
                    send=True,
                    procedure=instance,
                )
                denied_replayed = True
                emit("step1-unowned-prompt-dispatched")
        if sent and Path("/control/replay-prompt").is_file() and not denied_replayed:
            # Original fields, exact original generation; no freshly stamped identity.
            identifier, fields, kwargs = sent[0]
            controls.original(identifier, fields, **kwargs)
            denied_replayed = True
            emit("step1-original-prompt-replayed")
        if session.instance in closes and session.instance in closed:
            members = set(admission.members)
            if not members or closed != members:
                # Continue receiving safety-only callbacks and member CLOSEs.
                time.sleep(0.02)
                continue
            lifecycle.wait(lambda: list(child_gate.started), pump)
            with prompts.lock:
                if prompts.active:
                    raise RuntimeError(
                        "Terminal cleanup retained an open native prompt"
                    )
            emit(
                "step1-native-family-exited",
                case=case,
                members=len(members),
                pinned_pids_exited=len(closed),
                lifecycle_receipts=len(lifecycle.counts),
                prompt_generations_closed=True,
                holds_retained=True,
                full_family_quiescence=False,
                worker_reusable=False,
            )
            return
        time.sleep(0.03)
    emit(
        "step1-lifecycle-deadline",
        case=case,
        hold_retained=True,
        worker_reusable=False,
        terminal_outcome="UNKNOWN",
    )
    raise TimeoutError("Step 1 full native lifecycle deadline expired")


def failure_diagnostic(session, request, emit):
    """Bounded synthetic-fixture native tail, with every worker secret redacted."""
    try:
        session.log.flush()
        with Path(session.log.name).open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 32768))
            text = stream.read().decode("utf-8", errors="replace")
        for secret in (
            request["grant"]["token"],
            request.get("runtime_capability", ""),
        ):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        emit("step1-synthetic-native-diagnostic", tail=text)
    except Exception:
        emit("step1-synthetic-native-diagnostic-unavailable")
