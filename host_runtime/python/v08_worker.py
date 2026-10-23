"""Retained one-shot native worker. No general runtime or quiescence claim.

Only an operator-provisioned, read-only worker uses this entry point. A controller
must have admitted the original grant before provisioning its private config.
The worker never creates/restamps grants, retries consumption, releases a logical
hold, reuses a container, accepts children or enables the example driver.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import base64
import uuid
from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import sys
import time
import traceback

# The installed frozen GPL bridge and the exact candidate authority client are
# mounted separately; user source never participates in Python module lookup.
sys.path.insert(0, "/opt/host")
sys.path.insert(0, "/v08/server/src")
from native import NativeSession
from openbexi_spell_dss.relay import Relay
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as driver_proto
from openbexi_spell_server.contracts import Fault, decode, exact
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.snapshots import verify_directory
from openbexi_spell_server.transport import Route, tls_context
from openbexi_spell_server.worker import preflight


def readonly_tree(directory):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir() or not os.statvfs(root).f_flag & os.ST_RDONLY:
        raise RuntimeError("Worker source must be a read-only mount")
    # Reject writable nested mounts as well. Mount names needing escapes are
    # outside the fixed operator profile, rather than partially parsed.
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        parts = line.split()
        if len(parts) < 7 or "\\" in parts[4]:
            raise RuntimeError("Unsupported worker mount inventory")
        mount = Path(parts[4])
        if mount.is_relative_to(root) and "ro" not in parts[5].split(","):
            raise RuntimeError("Writable mount beneath worker source")
    return root


def emit(event, **values):
    print(json.dumps(dict(event=event, **values)), flush=True)


def run(config):
    exact(config, {"preflight", "grant", "start_barrier"})
    grant = start_grant(config["grant"])
    worker = config["preflight"]
    root = readonly_tree(worker["snapshot_directory"])
    if not os.statvfs("/").f_flag & os.ST_RDONLY:
        raise RuntimeError("Worker image root must be read-only")
    receipt, challenge = preflight(worker, details=True)
    if (
        grant.execution_id != worker["execution_id"]
        or grant.worker_slot != worker["worker_slot"]
        or grant.worker_incarnation != worker["worker_incarnation"]
    ):
        raise RuntimeError("Worker grant/assignment mismatch")
    # Verify again after preflight, immediately before consumption. The source
    # mount remains read-only for the complete native lifetime.
    if verify_directory(root, challenge["manifest"]) != receipt["source_sha256"]:
        raise RuntimeError("Worker source binding changed")
    route = Route(
        worker["context_url"],
        worker["context_fingerprint"],
        tls_context(worker["ca"], worker["certificate"], worker["key"]),
    )
    request = dict(
        schema="openbexi.worker/1", context_id=worker["context_id"], grant=asdict(grant)
    )

    def rpc(action):
        reply = route.call(
            request, path="/v1/worker/" + action, schema="openbexi.worker/1"
        )
        expected = dict(
            consumed=action == "consume",
            checked=action == "check",
            execution_id=grant.execution_id,
            request_id=grant.request_id,
            authority_incarnation=grant.authority_incarnation,
            hold_retained=True,
            runtime_enabled=False,
        )
        if reply != expected:
            raise RuntimeError("Worker launch receipt mismatch")

    # Exactly ONE consumption attempt. A lost reply must prevent native launch.
    rpc("consume")
    # Force the real proxy. Only procedure-scoped audit events are journalled
    # by Context; unqualified methods never fall back to ExampleDriver.
    denied = set()
    driver_methods = set()
    relay = None

    def dispatch(event, **body):
        if event != "openbexi/driverRequest":
            raise RuntimeError("Unexpected driver relay event")
        try:
            raw = base64.b64decode(body["payload"], validate=True)
            if len(raw) > 32768:
                raise ValueError("Native driver request exceeds bounds")
            request_id = str(uuid.UUID(body["id"]))
            if body["path"] != "/spell.driver.SPELLDriverInterface_EV/RaiseEvent":
                answer = route.call(
                    {
                        **request,
                        "request_id": request_id,
                        "path": body["path"],
                        "payload": body["payload"],
                    },
                    path="/v1/worker/driver",
                    schema="openbexi.worker/1",
                )
                exact(answer, {"request_id", "execution_id", "payload"})
                if (
                    answer["request_id"] != request_id
                    or answer["execution_id"] != grant.execution_id
                    or type(answer["payload"]) is not str
                    or len(answer["payload"]) > 43692
                    or len(base64.b64decode(answer["payload"], validate=True)) > 32768
                ):
                    raise RuntimeError("Native driver response binding differs")
                driver_methods.add(body["path"])
                relay.reply({"id": body["id"], "payload": answer["payload"]})
                return
            original = driver_proto.Event.FromString(raw)
            settings = unpack(original.config)
            if type(settings) is not dict or set(settings) - {"Severity", "Scope"}:
                raise ValueError("Driver event modifiers differ")
            answer = route.call(
                {
                    **request,
                    "request_id": request_id,
                    "message": original.message,
                    "severity": settings.get("Severity", 8),
                    "scope": settings.get("Scope", 1),
                },
                path="/v1/worker/event",
                schema="openbexi.worker/1",
            )
            if answer != dict(
                recorded=True, request_id=request_id, execution_id=grant.execution_id
            ):
                raise RuntimeError("Driver event receipt mismatch")
            # Original RaiseEvent returns Empty, only after durable Context commit.
            relay.reply({"id": body["id"], "payload": ""})
        except Exception:
            denied.add(body["path"])
            relay.reply({"id": body["id"], "error": "native_driver_request_denied"})

    relay = Relay(dispatch)
    session = NativeSession(
        root, root / challenge["manifest"]["entrypoint"], {}, driver_port=relay.port
    )
    count = 0

    def pump():
        nonlocal count
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                return
            count += 1
            if count > 2048 or event.get("event") == "connectionError":
                raise RuntimeError("Native notification capacity/connection failed")
            message = event.get("message", {})
            fields = message.get("fields", {})
            if (
                message.get("id") == "MSG_EXEC_OP"
                and fields.get("ExecOp") == "OPEN"
                and fields.get("ProcId") != session.instance
            ):
                raise RuntimeError("Native child admission is not qualified")

    session.pump = pump
    try:
        session.start()
        emit(
            "native-ready",
            execution_id=grant.execution_id,
            namespace_pid=os.getpid(),
            native_status="PAUSED",
            quiescence_proven=False,
        )
        deadline = time.monotonic() + 180
        barrier = Path(config["start_barrier"])
        while not barrier.is_file():
            if time.monotonic() >= deadline:
                raise TimeoutError("Native start barrier expired")
            time.sleep(0.05)
        rpc("check")
        session.request("CMD_RUN", send=True)
        running = False
        while time.monotonic() < deadline:
            pump()
            state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
            if state == "RUNNING" and not running:
                running = True
                emit("native-running", execution_id=grant.execution_id)
            if state in {"FINISHED", "ERROR", "ABORTED"}:
                break
            time.sleep(0.05)
        else:
            raise TimeoutError("Native execution deadline expired")
        if state != "FINISHED" or denied:
            terminal = session.request("REQ_EXEC_STATUS")
            emit(
                "native-terminal-failure",
                native_status=state,
                denied_driver_methods=sorted(denied)[:16],
                error_message=str(terminal.get("ErrorMsg", ""))[:1024],
                error_reason=str(terminal.get("ErrorReason", ""))[:1024],
            )
            raise RuntimeError("Native execution/driver profile failed")
        emit(
            "native-finished",
            execution_id=grant.execution_id,
            native_status=state,
            hold_retained=True,
            external_driver_effects_enabled=(
                "/spell.driver.SPELLDriverInterface_TC/SendCommand" in driver_methods
            ),
            native_driver_methods=sorted(driver_methods),
            context_audit_events_enabled=True,
            runtime_enabled=False,
        )
    finally:
        # This is best-effort native cleanup, never a quiescence/hold-release
        # proof. The independent host must confirm whole-container termination.
        try:
            session.close()
        finally:
            relay.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        run(decode(args.config.read_bytes()))
    except Exception as error:
        causes = []
        current = error
        for _ in range(3):
            if current is None:
                break
            causes.append(
                dict(
                    type=type(current).__name__,
                    message=current.code
                    if isinstance(current, Fault)
                    else str(current)[:512],
                    stack=[
                        dict(
                            file=Path(frame.filename).name,
                            line=frame.lineno,
                            function=frame.name,
                        )
                        for frame in traceback.extract_tb(current.__traceback__)
                    ][-8:],
                )
            )
            current = current.__context__ or current.__cause__
        emit(
            "native-worker-failed",
            error=error.code if isinstance(error, Fault) else type(error).__name__,
            hold_retained=True,
            runtime_enabled=False,
            causes=causes,
            stack=[
                dict(
                    file=Path(frame.filename).name,
                    line=frame.lineno,
                    function=frame.name,
                )
                for frame in traceback.extract_tb(error.__traceback__)
            ][-8:],
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
