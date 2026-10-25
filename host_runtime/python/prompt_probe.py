"""Private original-native prompt cohort; no runtime or handoff approval."""

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import time


def run_prompt_probe(
    session,
    controls,
    prompts,
    admission,
    pump,
    children,
    child_gate,
    lifecycle,
    emit,
    mode,
):
    emit("native-prompt-ready", mode=mode, runtime_enabled=False)
    deadline = time.monotonic() + 90
    examined = set()
    previous = None
    while time.monotonic() < deadline:
        pump()
        children.service(session)
        controls.poll_owner()
        prompts.poll()
        # Exercise a real unsupported wire reply before any legitimate owner
        # reply. Its absence of admission identity must never wake a prompt.
        for identity, registration in list(prompts.registrations.items()):
            if identity in examined:
                continue
            examined.add(identity)
            instance = registration[0]
            admission.disabled_mutations.discard((instance, "MSG_ANSWER"))
            controls.original(
                "MSG_ANSWER",
                {"ReturnValue": "UNAUTHORIZED"},
                procedure=instance,
                send=True,
            )
            until = time.monotonic() + 3
            while (instance, "MSG_ANSWER") not in admission.disabled_mutations:
                pump()
                if time.monotonic() >= until:
                    raise RuntimeError(
                        "Native prompt identity-less denial not observed"
                    )
                time.sleep(0.01)
            emit("native-prompt-denial-observed", mode=mode)
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if state != previous:
            emit("native-prompt-status", native_status=state, mode=mode)
            previous = state
        if mode == "fenced" and Path("/control/prompt-observed").exists():
            if (
                Path("/workspace/prompt-UNSAFE").exists()
                or len(prompts.active) != 1
                or len(prompts.consume_attempted) != 1
                or state in {"FINISHED", "ABORTED", "ERROR"}
            ):
                raise RuntimeError(
                    "Fenced native prompt changed execution or pending generation"
                )
            emit(
                "native-prompt-fenced-held",
                mode=mode,
                native_status=state,
                hold_retained=True,
                runtime_enabled=False,
            )
            return
        if state in {"FINISHED", "ABORTED", "ERROR"}:
            expected = "ABORTED" if mode == "cancel" else "FINISHED"
            if state != expected:
                raise RuntimeError("Native prompt terminal status differs: " + state)
            if mode == "complete":
                lifecycle.wait(lambda: list(child_gate.started), pump)
                if (
                    Path("/workspace/prompt-complete").read_text() != "verified"
                    or Path("/workspace/prompt-child").read_text() != "42"
                ):
                    raise RuntimeError(
                        "Native prompt selected value or child result differs"
                    )
            elif Path("/workspace/prompt-UNSAFE").exists():
                raise RuntimeError("Native cancelled prompt resumed its next effect")
            until = time.monotonic() + 5
            while prompts.active:
                pump()
                if time.monotonic() >= until:
                    raise RuntimeError("Original native prompt close receipt missing")
                time.sleep(0.02)
            emit(
                "native-prompt-finished",
                mode=mode,
                native_status=state,
                prompts=len(prompts.registrations),
                consumed=len(prompts.consume_attempted),
                hold_retained=True,
                runtime_enabled=False,
                full_v08_qualified=False,
            )
            return
        time.sleep(0.03)
    raise TimeoutError("Native prompt cohort deadline expired")
