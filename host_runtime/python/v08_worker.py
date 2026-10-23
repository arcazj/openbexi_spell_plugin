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
import importlib.util
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
from openbexi_spell_server.contracts import Fault, decode, exact, fingerprint
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


def native_pause_probe(session, pump, status, *, timeout=3, prior=None):
    """Observe main-Executor pause; never synthesize family quiescence.

    The frozen provider cannot acknowledge all threads/children or drain all
    prompt/control queues. In particular, Python background threads can run
    while the main native execution model reports PAUSED.
    """
    if prior is not None:
        return prior  # Receipt loss is not permission to repeat a native command.
    result = dict(
        provider="legacy-status-only/1",
        native_status=status,
        quiescence_proven=False,
        reason="non_running_state_unqualified",
    )
    if status != "RUNNING":
        return result
    try:
        session.request("CMD_PAUSE", send=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pump()
            state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
            result["native_status"] = state
            if state == "PAUSED":
                result["reason"] = "thread_child_queue_proof_unavailable"
                return result
            if state != "RUNNING":
                return result
            time.sleep(0.02)
        result["reason"] = "pause_timeout"
    except Exception:
        result.update(native_status="UNKNOWN", reason="native_channel_failure")
    return result


def cooperative_thread_pause(session, pump, status, barrier_id):
    """Hold observed background Python lines, retaining the unproved fence."""
    from thread_barrier import provider_call

    try:
        answer = provider_call(36991, barrier_id)
        emit("native-thread-barrier", **answer)
    except Exception:
        emit("native-thread-barrier-unavailable", barrier_id=barrier_id)
    return native_pause_probe(session, pump, status)


def run(config):
    fields = {"preflight", "grant", "start_barrier"}
    probe_enabled = type(config) is dict and "pause_probe" in config
    thread_probe = type(config) is dict and "thread_barrier_probe" in config
    child_profile = type(config) is dict and "native_child_gate" in config
    exact(
        config,
        fields
        | ({"pause_probe"} if probe_enabled else set())
        | ({"thread_barrier_probe"} if thread_probe else set())
        | ({"native_child_gate"} if child_profile else set()),
    )
    if probe_enabled and config["pause_probe"] is not True:
        raise ValueError("Native pause probe requires explicit true")
    if thread_probe and (
        config["thread_barrier_probe"] is not True or not probe_enabled
    ):
        raise ValueError("Thread barrier requires the explicit fenced pause probe")
    if child_profile and (
        config["native_child_gate"] is not True or probe_enabled or thread_probe
    ):
        raise ValueError("Native children require their separate explicit profile")
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
        schema="openbexi.worker/2", context_id=worker["context_id"], grant=asdict(grant)
    )

    def rpc(action):
        reply = route.call(
            request, path="/v1/worker/" + action, schema="openbexi.worker/2"
        )
        capability = None
        if action == "consume":
            capability = fingerprint(reply.pop("runtime_capability", None))
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
        if capability is not None:
            # The sole winner retains this proof only in memory, never in the
            # original configuration, logs or a replayable receipt response.
            request["runtime_capability"] = capability

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
                    schema="openbexi.worker/2",
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
                schema="openbexi.worker/2",
            )
            if answer != dict(
                recorded=True, request_id=request_id, execution_id=grant.execution_id
            ):
                raise RuntimeError("Driver event receipt mismatch")
            # Original RaiseEvent returns Empty, only after durable Context commit.
            relay.reply({"id": body["id"], "payload": ""})
        except Exception as error:
            denied.add(body["path"])
            emit(
                "native-driver-denied",
                path=body["path"],
                error_type=type(error).__name__,
                status=error.status if isinstance(error, Fault) else None,
                code=error.code
                if isinstance(error, Fault)
                else "driver_response_invalid",
            )
            relay.reply({"id": body["id"], "error": "native_driver_request_denied"})

    relay = Relay(dispatch)
    session_type, options = NativeSession, {}
    if thread_probe or child_profile:
        # The published v0.7 image and its default host session stay intact.
        # Only this explicit profile loads the candidate read-only session and
        # the fixed operator library, never procedure-selected startup code.
        sys.path.insert(0, "/v08")
        spec = importlib.util.spec_from_file_location(
            "v08_native_candidate", "/v08/native_candidate.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        session_type = module.NativeSession
        if thread_probe:
            options["user_library"] = "/v08/native-userlib"
        if child_profile:
            options.update(
                native_home="/opt/v08-native-home",
                admission_socket="/tmp/native-admission.sock",
            )
    session = session_type(
        root,
        root / challenge["manifest"]["entrypoint"],
        {},
        driver_port=relay.port,
        **options,
    )
    count = 0
    admission = None
    child_gate = None
    children = None
    if child_profile:
        sys.path.insert(0, "/v08")
        from child_gate import NativeAdmissionServer, NativeChildGate
        from children import ChildProcedures

        child_gate = NativeChildGate(
            request,
            route,
            challenge["manifest"]["entrypoint"],
            session.instance,
            session.arguments,
            lambda: rpc("check"),
        )
        children = ChildProcedures(session.instance)
        admission = NativeAdmissionServer(
            options["admission_socket"],
            "/opt/v08-native-home/bin/SPELL-Context",
            lambda: session.process,
            child_gate,
        )

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
                if child_gate is None or fields.get("ProcId") not in child_gate.started:
                    raise RuntimeError("Native child admission is not qualified")
                emit("native-child-open", execution_id=grant.execution_id)
            if children is not None:
                children.observe(message)

    session.pump = pump
    try:
        session.start()
        if child_gate is not None and session.instance not in child_gate.started:
            raise RuntimeError("Native before-spawn root hook was bypassed")
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
        attempted_pause = {}
        pause_channel_failed = False
        next_poll = 0
        child_running = set()
        while time.monotonic() < deadline:
            pump()
            if children is not None:
                children.service(session)
                for instance in list(children.children):
                    info = session.request(
                        "REQ_EXEC_INFO", context=True, procedure=instance
                    )
                    if (
                        info.get("ExecutorStatus") == "RUNNING"
                        and instance not in child_running
                    ):
                        child_running.add(instance)
                        emit("native-child-running", execution_id=grant.execution_id)
            state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
            if state == "RUNNING" and not running:
                running = True
                emit("native-running", execution_id=grant.execution_id)
            if probe_enabled and time.monotonic() >= next_poll:
                next_poll = time.monotonic() + 0.2
                try:
                    action = route.call(
                        request,
                        path="/v1/worker/pause-poll",
                        schema="openbexi.worker/2",
                    )
                    if action.get("execution_id") != grant.execution_id:
                        raise RuntimeError("Native pause command assignment differs")
                    if action.get("action") == "pause":
                        barrier = str(uuid.UUID(action["barrier_id"]))
                        if barrier not in attempted_pause:
                            attempted_pause[barrier] = (
                                cooperative_thread_pause(session, pump, state, barrier)
                                if thread_probe
                                else native_pause_probe(session, pump, state)
                            )
                        diagnostic = attempted_pause[barrier]
                        # Repeating this exact diagnostic after response loss is
                        # harmless. Never repeat consumption, pause, or a TC.
                        answer = route.call(
                            {**request, "barrier_id": barrier, **diagnostic},
                            path="/v1/worker/pause-report",
                            schema="openbexi.worker/2",
                        )
                        if (
                            answer.get("barrier_id") != barrier
                            or answer.get("quiescence_proven") is not False
                            or answer.get("effective_transfer") is not False
                        ):
                            raise RuntimeError("Native pause receipt differs")
                        emit(
                            "native-pause-unproven",
                            execution_id=grant.execution_id,
                            barrier_id=barrier,
                            **diagnostic,
                        )
                    elif action.get("action") not in {"none", "hold"}:
                        raise RuntimeError("Native pause action differs")
                except Exception:
                    if not pause_channel_failed:
                        # An unavailable/restarted authority is not permission
                        # to kill or resume a procedure. Attempt a local pause,
                        # retain the family, and await independent host recovery.
                        prior = next(iter(attempted_pause.values()), None)
                        diagnostic = (
                            cooperative_thread_pause(
                                session, pump, state, str(uuid.uuid4())
                            )
                            if thread_probe and prior is None
                            else native_pause_probe(session, pump, state, prior=prior)
                        )
                        emit(
                            "native-pause-channel-unavailable",
                            execution_id=grant.execution_id,
                            **diagnostic,
                        )
                        pause_channel_failed = True
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
            native_children_admitted=0
            if child_gate is None
            else len(child_gate.started) - 1,
            full_family_qualified=False,
        )
    finally:
        # This is best-effort native cleanup, never a quiescence/hold-release
        # proof. The independent host must confirm whole-container termination.
        try:
            session.close()
        finally:
            try:
                if admission is not None:
                    admission.close()
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
