"""Original native family continuation across a separately attested host freeze."""
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
import time


def run_handoff_probe(
    session, controls, child_gate, children, prompts, pump, runtime, lifecycle, emit
):
    session.request("CMD_RUN", send=True)
    deadline = time.monotonic() + 120
    ready = rotated = False
    while time.monotonic() < deadline:
        runtime.ensure()
        pump()
        children.service(session)
        if runtime.rotated:
            controls.poll_owner()
            if not rotated:
                rotated = True
                emit("native-handoff-activated", runtime_identity_rotated=True)
        if not ready and all(
            Path("/workspace/" + name).is_file()
            for name in ("handoff-root", "handoff-background", "handoff-child")
        ):
            ready = True
            emit(
                "native-handoff-ready",
                members=len(child_gate.started),
                background_thread=True,
            )
        if (
            Path("/workspace/handoff-after").is_file()
            and not Path("/workspace/handoff-reported").exists()
        ):
            if (
                not runtime.rotated
                or not Path("/workspace/handoff-stale-denied").is_file()
            ):
                raise RuntimeError("Native handoff lost its delayed-operation fence")
            Path("/workspace/handoff-reported").write_text("reported")
            emit(
                "native-handoff-continued",
                stale_native_driver_denied=True,
                new_owner_driver_completed=True,
            )
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if state in {"FINISHED", "ERROR", "ABORTED"}:
            if state != "FINISHED" or not rotated:
                raise RuntimeError(
                    "Native handoff fixture terminated before continuation"
                )
            lifecycle.wait(lambda: list(child_gate.started), pump)
            emit(
                "native-handoff-finished",
                native_status=state,
                members=len(child_gate.started),
            )
            return
        time.sleep(0.05)
    raise TimeoutError("Native handoff fixture expired")
