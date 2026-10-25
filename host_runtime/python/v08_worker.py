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
import threading
import time
import traceback
import tempfile

# The installed frozen GPL bridge and the exact candidate authority client are
# mounted separately; user source never participates in Python module lookup.
sys.path.insert(0, "/opt/host")
sys.path.insert(0, "/v08/server/src")
from native import NativeSession
from openbexi_spell_dss.relay import Relay
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as driver_proto
from openbexi_spell_server.contracts import Fault, canonical, decode, exact, fingerprint
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.snapshots import verify_directory
from openbexi_spell_server.transport import Route, tls_context
from openbexi_spell_server.worker import preflight, protect_runtime


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


def drain_native_notifications(session, children, child_gate, execution_id, count):
    # The real session queue holds at most 256 events. Bound work per pump so
    # a notification stream cannot starve the RPC reply or command poll. Total
    # lifetime traffic is not queue occupancy and must not terminate a normal
    # procedure merely because its source emits more than 2048 notifications.
    for _ in range(64):
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            break
        count += 1
        if event.get("event") == "connectionError":
            emit("native-notification-channel-failed", notifications_seen=count)
            raise RuntimeError("Native notification connection failed")
        message = event.get("message", {})
        fields = message.get("fields", {})
        if (
            message.get("id") == "MSG_EXEC_OP"
            and fields.get("ExecOp") == "OPEN"
            and fields.get("ProcId") != session.instance
        ):
            if child_gate is None or fields.get("ProcId") not in child_gate.started:
                raise RuntimeError("Native child admission is not qualified")
            emit("native-child-open", execution_id=execution_id)
        if children is not None:
            children.observe(message)
    return count


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


def owner_fixture_variables(session):
    answer = session.request("REQ_GET_VARIABLES")
    if answer.get("TotalChunks") not in {"0", "1"}:
        raise RuntimeError("Owner fixture variable response is chunked or invalid")
    names = answer.get("VarName", "").split("\4")
    values = answer.get("VarValue", "").split("\4")
    if len(names) != len(values):
        raise RuntimeError("Owner fixture variable response differs")
    return dict(zip(names, values))


def verify_disabled_native_mutations(session, controls, admission, pump):
    script = (
        "__import__('pathlib').Path('/workspace/mutation-bypass').write_text('unsafe')"
    )
    commands = (
        ("CMD_SCRIPT", {"Script": script}),
        ("CMD_GOTO", {"GotoLine": "2"}),
        ("CMD_STEP_OVER", {}),
        ("CMD_SKIP", {}),
        ("CMD_INTERRUPT", {}),
        ("CMD_FINISH", {}),
        ("CMD_ACTION", {}),
        ("CMD_RELOAD", {}),
        ("MSG_ANSWER", {"ReturnValue": "unsafe"}),
        ("MSG_CANCEL", {}),
        ("CMD_ABORT", {}),
        ("CMD_BLOCK", {}),
        ("CMD_CLOSE", {}),
    )
    requests = (
        ("REQ_SET_CONFIG", {}),
        ("REQ_SET_BREAKPOINT", {}),
        ("REQ_CLEAR_BREAKPOINT", {}),
        (
            "REQ_CHANGE_VARIABLE",
            {"VarName": "FIRST", "VarValue": script, "VarGlobal": "True"},
        ),
        ("REQ_CHANGE_RESOURCE", {}),
        ("REQ_UPD_DICTIONARY", {}),
    )
    for operation, fields in commands + requests:
        if operation.startswith("REQ_"):
            try:
                controls.original(operation, fields)
            except RuntimeError as error:
                if "V08_NATIVE_MUTATION_DENIED" not in str(error):
                    raise RuntimeError(
                        "Native request did not reach its closed mutation boundary"
                    ) from None
            else:
                raise RuntimeError("Unqualified native request was not rejected")
        else:
            controls.original(operation, fields, send=True)
        until = time.monotonic() + 3
        while (session.instance, operation) not in admission.disabled_mutations:
            pump()
            if time.monotonic() >= until:
                raise TimeoutError("Missing original-Executor mutation denial")
            time.sleep(0.01)
        values = owner_fixture_variables(session)
        if (
            values.get("FIRST") != "1"
            or "SECOND" in values
            or Path("/workspace/mutation-bypass").exists()
            or session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
            != "PAUSED"
        ):
            raise RuntimeError(
                "Disabled native mutation changed the fixture or execution state"
            )
    emit(
        "native-disabled-mutations-held",
        operations=len(commands) + len(requests),
        original_executor_denials=True,
        variables_unchanged=True,
        script_marker_absent=True,
        native_status="PAUSED",
        quiescence_proven=False,
    )
    management = (
        "REQ_GUI_LOGIN",
        "REQ_GUI_LOGOUT",
        "REQ_OPEN_EXEC",
        "REQ_CLOSE_EXEC",
        "REQ_KILL_EXEC",
        "REQ_ATTACH_EXEC",
        "REQ_DETACH_EXEC",
        "REQ_RECOVER_EXEC",
        "REQ_DELETE_RECOVERY",
        "REQ_REMOVE_CONTROL",
        "REQ_SET_BACKGROUND",
        "REQ_SET_SHARED_DATA",
        "REQ_DEL_SHARED_DATA",
        "REQ_ADD_SHARED_DATA_SCOPE",
        "REQ_DEL_SHARED_DATA_SCOPE",
        "REQ_SET_CTX_EXEC_DFLT",
        "REQ_INSTANCE_ID",
        "REQ_FUTURE_UNREVIEWED",
    )
    for operation in management:
        try:
            controls.original(operation, {}, context=True)
        except RuntimeError as error:
            if "V08_CONTEXT_MUTATION_DENIED" not in str(error):
                raise RuntimeError(
                    "Native Context mutation boundary not reached"
                ) from None
        else:
            raise RuntimeError("Unqualified native Context mutation was accepted")
        if operation not in admission.gui.denied:
            raise RuntimeError("Missing authenticated Context management denial")
        if (
            owner_fixture_variables(session).get("FIRST") != "1"
            or "SECOND" in owner_fixture_variables(session)
            or session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
            != "PAUSED"
        ):
            raise RuntimeError("Disabled Context mutation changed the native fixture")
    roster_messages = (
        "MSG_ADD_CLIENT",
        "MSG_REMOVE_CLIENT",
        "MSG_BACKGROUND",
        "MSG_SHOW_NODE_DEPTH",
        "MSG_WVARIABLES_ENABLE",
        "MSG_WVARIABLES_DISABLE",
        "MSG_DRESOURCES_ENABLE",
        "MSG_DRESOURCES_DISABLE",
    )
    for operation in roster_messages:
        controls.original(operation, {}, send=True)
        until = time.monotonic() + 3
        while operation not in admission.gui.denied:
            pump()
            if time.monotonic() >= until:
                raise TimeoutError("Missing native Context roster-message denial")
            time.sleep(0.01)
    emit(
        "native-context-mutations-held",
        operations=len(management),
        roster_messages=len(roster_messages),
        original_context_denials=True,
        variables_unchanged=True,
        native_status="PAUSED",
        quiescence_proven=False,
    )


def verify_startup_run_retired(controls):
    try:
        controls.route.call(
            {
                **controls.request,
                "request_id": str(uuid.uuid4()),
                "target_admission_id": None,
                "command": "CMD_RUN",
            },
            path="/v1/worker/control-admit",
            schema="openbexi.worker/2",
        )
    except Fault as error:
        if error.status == 403:
            emit("native-startup-run-retired", status=403)
            return
        raise
    raise RuntimeError("Unused startup RUN remained available after an owner command")


def owner_resume_paused_guard(session, controls):
    """Check the pause fence without confusing a committed RUN with stale state.

    The final native consume RPC may be committed before its receipt returns to
    the worker. A real Executor can transition out of PAUSED while that callback
    is in flight. Never query paused-only variables in that interval. The
    original consumption receipt is still mandatory before reporting success.
    """
    state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
    if state != "PAUSED":
        if len(controls.owner_consume_attempted) >= 3:
            return False  # In-flight final admission; NOT a completion proof.
        raise RuntimeError(
            "Native fixture resumed before third owner consumption attempt"
        )
    try:
        values = owner_fixture_variables(session)
    except RuntimeError:
        # A successful final admission can race a status read and make the
        # paused-only variable API unavailable. Never suppress earlier errors.
        if len(controls.owner_consume_attempted) >= 3:
            return False
        raise
    if (
        values.get("FIRST") != "1"
        or "SECOND" in values
        or Path("/workspace/owner-resumed").exists()
    ):
        raise RuntimeError("Native fixture resumed without its fresh owner RUN")
    return True


def owner_pause_resume_probe(session, controls, pump):
    """Main-Executor pause and same-owner resume, never a family barrier."""
    emit("native-owner-resume-ready", native_status="PAUSED")
    until = time.monotonic() + 40
    while True:
        controls.poll_owner()
        pump()
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if (
            len(controls.owner_consumed) == 1
            and state == "RUNNING"
            and Path("/workspace/owner-running").is_file()
        ):
            break
        if time.monotonic() >= until:
            raise TimeoutError("Fresh owner RUN did not start its native fixture")
        time.sleep(0.02)
    verify_startup_run_retired(controls)
    emit("native-owner-run-started", native_status="RUNNING")
    until = time.monotonic() + 40
    while True:
        controls.poll_owner()
        pump()
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if len(controls.owner_consumed) == 2 and state == "PAUSED":
            break
        if time.monotonic() >= until:
            raise TimeoutError(
                "Fresh owner PAUSE did not pause the native main Executor"
            )
        time.sleep(0.02)
    values = owner_fixture_variables(session)
    if values.get("FIRST") != "1" or "SECOND" in values:
        raise RuntimeError("Native PAUSE fixture advanced beyond its barrier")
    emit("native-owner-paused", native_status="PAUSED", quiescence_proven=False)
    until = time.monotonic() + 40
    opened_at = None
    while len(controls.owner_consumed) == 2:
        if Path("/control/owner-resume").is_file() and opened_at is None:
            opened_at = time.monotonic()
        delivered = controls.poll_owner()
        pump()
        if delivered == "command":
            # IPC send acknowledgement can precede the native consumption
            # callback. The resumed Executor may already reject variable reads;
            # stop paused-only observations as soon as RUN is dispatched.
            while len(controls.owner_consumed) != 3:
                pump()
                if time.monotonic() >= until:
                    raise TimeoutError(
                        "Fresh owner resume consumption was not confirmed"
                    )
                time.sleep(0.02)
        if len(controls.owner_consumed) == 3:
            if opened_at is None or time.monotonic() - opened_at < 4:
                raise RuntimeError(
                    "Owner resume was not independently held behind native PAUSE"
                )
            break
        owner_resume_paused_guard(session, controls)
        if time.monotonic() >= until:
            raise TimeoutError("Fresh same-owner resume was not delivered")
        time.sleep(0.02)
    until = time.monotonic() + 15
    while True:
        pump()
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        if state == "FINISHED":
            break
        if time.monotonic() >= until:
            raise TimeoutError("Fresh owner resume did not finish the native fixture")
        time.sleep(0.02)
    if (
        not Path("/workspace/owner-resumed").is_file()
        or len(controls.owner_consumed) != 3
        or controls.consumed
    ):
        raise RuntimeError("Owner resume effect or original grant accounting differs")
    emit(
        "native-owner-resume-finished",
        native_status="FINISHED",
        fresh_owner_grants=3,
        startup_run_grants_used=0,
        quiescence_proven=False,
        effective_transfer=False,
        hold_retained=True,
    )


def owner_step_probe(session, controls, admission, consume_fenced, pump):
    """Two real STEP commands; the second must fail after durable disconnect.

    Only fixed fixture predicates leave the worker. Native variable values and
    grants are never emitted. A PAUSED status alone cannot satisfy this probe.
    """

    def variables():
        return owner_fixture_variables(session)

    if "FIRST" in variables() or "SECOND" in variables():
        raise RuntimeError("Owner fixture advanced before its first grant")
    emit("native-owner-ready", native_status="PAUSED")
    until = time.monotonic() + 40
    while len(controls.owner_consumed) != 1:
        if time.monotonic() >= until:
            raise TimeoutError("Owner first STEP was not consumed")
        controls.poll_owner()
        pump()
        time.sleep(0.02)
    until = time.monotonic() + 10
    while True:
        pump()
        state = session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
        values = variables() if state == "PAUSED" else {}
        if state == "PAUSED" and values.get("FIRST") == "1" and "SECOND" not in values:
            break
        if time.monotonic() >= until:
            raise TimeoutError("Owner first STEP lacks its exact native fixture effect")
        time.sleep(0.02)
    verify_startup_run_retired(controls)
    verify_disabled_native_mutations(session, controls, admission, pump)
    emit(
        "native-owner-first-step",
        first_assignment_proven=True,
        second_assignment_absent=True,
    )
    until = time.monotonic() + 40
    while not Path("/workspace/owner-awaiting").is_file():
        if time.monotonic() >= until:
            raise TimeoutError("Owner second STEP did not reach final consumption hold")
        controls.poll_owner()
        pump()
        time.sleep(0.02)
    emit("native-owner-awaiting-fence")
    if not admission.consume_denials.wait(40) or not consume_fenced.is_set():
        raise RuntimeError("Owner second STEP lacks real authority denial")
    until = time.monotonic() + 35
    while True:
        pump()
        values = variables()
        if (
            session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"] != "PAUSED"
            or values.get("FIRST") != "1"
            or "SECOND" in values
            or len(controls.owner_consumed) != 1
            or controls.consumed
        ):
            raise RuntimeError("Stale owner STEP advanced or bypassed its fresh grant")
        if Path("/control/owner-probe-stop").is_file():
            return
        if time.monotonic() >= until:
            raise TimeoutError("Owner probe host observation expired")
        if not Path("/workspace/owner-held").exists():
            Path("/workspace/owner-held").write_text("held\n")
            emit(
                "native-stale-owner-step-held",
                first_assignment_proven=True,
                second_assignment_absent=True,
                native_status="PAUSED",
                hold_retained=True,
            )
        time.sleep(0.05)


def run(config):
    fields = {"preflight", "grant", "start_barrier"}
    probe_enabled = type(config) is dict and "pause_probe" in config
    thread_probe = type(config) is dict and "thread_barrier_probe" in config
    child_profile = type(config) is dict and "native_child_gate" in config
    consumption_probe = type(config) is dict and "native_consume_fence_probe" in config
    owner_probe = type(config) is dict and "native_owner_commands_probe" in config
    owner_resume = type(config) is dict and "native_owner_resume_probe" in config
    prompt_profile = type(config) is dict and "native_prompt_gate" in config
    terminal_case = config.get("native_terminal_case") if type(config) is dict else None
    exact(
        config,
        fields
        | ({"pause_probe"} if probe_enabled else set())
        | ({"thread_barrier_probe"} if thread_probe else set())
        | ({"native_child_gate"} if child_profile else set())
        | ({"native_consume_fence_probe"} if consumption_probe else set())
        | ({"native_owner_commands_probe"} if owner_probe else set())
        | ({"native_owner_resume_probe"} if owner_resume else set())
        | ({"native_prompt_gate"} if prompt_profile else set())
        | ({"native_terminal_case"} if terminal_case is not None else set()),
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
    if consumption_probe and (
        config["native_consume_fence_probe"] is not True or not child_profile
    ):
        raise ValueError(
            "Consumption probe requires the private native child candidate"
        )
    if owner_probe and (
        config["native_owner_commands_probe"] is not True
        or not child_profile
        or consumption_probe
    ):
        raise ValueError(
            "Owner commands require their separate private native candidate"
        )
    if owner_resume and (
        config["native_owner_resume_probe"] is not True
        or not child_profile
        or owner_probe
        or consumption_probe
    ):
        raise ValueError("Owner resume requires its separate private native candidate")
    if prompt_profile and (
        config["native_prompt_gate"] is not True
        or not child_profile
        or consumption_probe
        or owner_probe
        or owner_resume
    ):
        raise ValueError("Native prompts require a separate private child profile")
    if prompt_profile:
        build_receipt = json.loads(Path("/opt/v08-native-home/build.json").read_text())
        if build_receipt.get("native_prompt_hooks") is not True:
            raise ValueError("Native prompt hooks are absent from the checked build")
    if terminal_case is not None:
        from terminal_probe import CASES

        if (
            type(terminal_case) is not str
            or terminal_case not in CASES
            or not prompt_profile
            or build_receipt.get("native_terminal_hooks") is not True
        ):
            raise ValueError("Native terminal profile/build differs")
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
        if canonical(reply) != canonical(expected):
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
    lifecycle = None

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
            if lifecycle is not None:
                lifecycle.acknowledge(original.message, list(child_gate.started))
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
                consume_fence_probe=consumption_probe,
                owner_step_probe=owner_probe,
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
    prompts = None
    children = None
    if child_profile:
        sys.path.insert(0, "/v08")
        from child_gate import (
            NativeAdmissionServer,
            NativeChildGate,
            NativeLifecycleReceipts,
        )
        from control_journal import NativeRunJournal
        from children import ChildProcedures

        child_gate = NativeChildGate(
            request,
            route,
            challenge["manifest"]["entrypoint"],
            session.instance,
            session.arguments,
            lambda: rpc("check"),
        )
        lifecycle = NativeLifecycleReceipts()
        children = ChildProcedures(session.instance, admit_hidden=True)
        controls = NativeRunJournal(session, request, route, child_gate)
        if prompt_profile:
            from prompt_replies import NativePromptAgent

            prompts = NativePromptAgent(controls)
        if consumption_probe or owner_probe:
            final_consume = controls.consume
            consume_fenced = threading.Event()

            def observe_consume(body):
                # The C++ probe hold is before opening the Unix channel. This
                # wrapper only records a real HTTP 403 from final admission.
                try:
                    final_consume(body)
                except Fault as error:
                    if error.status == 403:
                        consume_fenced.set()
                        emit(
                            "native-owner-authority-denied"
                            if owner_probe
                            else "native-consumption-authority-denied",
                            status=403,
                        )
                    raise

            controls.consume = observe_consume
        session.request = controls.dispatch
        admission = NativeAdmissionServer(
            options["admission_socket"],
            "/opt/v08-native-home/bin/SPELL-Context",
            lambda: session.process,
            child_gate,
            controls=controls,
            prompts=prompts,
            executor="/opt/v08-native-home/bin/SPELL-Executor",
            report=emit,
        )
        session.gui_binding_callback = admission.gui.bind

    def pump():
        nonlocal count
        count = drain_native_notifications(
            session, children, child_gate, grant.execution_id, count
        )

    try:
        try:
            session.start()
        except Exception:
            if child_gate is not None:
                # Fixed protocol milestones survive cleanup. Never emit the
                # native log, variable values, launch proof, PID or arguments.
                markers = {}
                try:
                    session.log.flush()
                    with Path(session.log.name).open("rb") as native_log:
                        native_log.seek(0, 2)
                        native_log.seek(max(0, native_log.tell() - 65536))
                        tail = native_log.read()
                    markers = {
                        label: literal in tail
                        for label, literal in (
                            (
                                "interpreter_initializing",
                                b"[*] Initializing interpreter",
                            ),
                            ("objects_preparing", b"[***] Preparing objects"),
                            ("python_initializing", b"Initializing Python interface"),
                            (
                                "framework_loading",
                                b"Loading execution framework functions",
                            ),
                            ("executor_initializing", b"Initializing executor"),
                            ("controller_starting", b"Starting controller"),
                            ("objects_ready", b"[***] Objects ready"),
                            ("executor_binding", b"Installing executor binding"),
                            ("fatal_cif", b"[FATAL] Failed to setup CIF"),
                            ("python_traceback", b"Traceback (most recent call last)"),
                            ("native_run_denied", b"V08_NATIVE_RUN_DENIED:"),
                        )
                    }
                except (AttributeError, OSError, ValueError):
                    pass
                emit(
                    "native-startup-incomplete",
                    root_admitted=session.instance in child_gate.started,
                    members_attempted=len(controls.member_attempted),
                    members_registered=len(controls.bound_members),
                    original_native_context_pinned=admission.context_pid is not None,
                    listener_process_alive=session.process is not None
                    and session.process.poll() is None,
                    bounded_tail_markers=markers,
                    hold_retained=True,
                    runtime_enabled=False,
                )
            raise
        # NativeSession.start owns its startup PAUSED notification. Installing
        # the runtime consumer early can steal that notification during an
        # info request and leave startup waiting despite a PAUSED Executor.
        session.pump = pump
        if child_gate is not None and session.instance not in child_gate.started:
            raise RuntimeError("Native before-spawn root hook was bypassed")
        if child_gate is not None:
            # Deliberately bypass the Python wrapper with an unregistered ID.
            # Only an actual native Context callback/denial satisfies this probe.
            controls.original(
                "CMD_RUN", {"V08ControlRequest": str(uuid.uuid4())}, send=True
            )
            if not admission.control_denials.wait(2):
                raise RuntimeError("Native unadmitted RUN bypassed the forwarding hook")
            if (
                session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
                != "PAUSED"
            ):
                raise RuntimeError("Native unadmitted RUN advanced the Executor")
            emit("native-unadmitted-run-denied", execution_id=grant.execution_id)
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
        if consumption_probe:
            # Docker must provision this probe's tmpfs for the actual worker
            # UID. Prove writability before relying on absence of a body marker.
            workspace = Path("/workspace")
            if workspace.stat().st_uid != os.getuid():
                raise RuntimeError("Consumption probe workspace owner differs")
            with tempfile.TemporaryFile(dir=workspace) as writable:
                writable.write(b"probe")
                writable.flush()
            emit("native-consumption-probe-ready", writable_marker_directory=True)
        if owner_probe:
            owner_step_probe(session, controls, admission, consume_fenced, pump)
            return
        if owner_resume:
            owner_pause_resume_probe(session, controls, pump)
            return
        if terminal_case is not None:
            from terminal_probe import run_terminal_probe

            run_terminal_probe(
                terminal_case,
                session,
                controls,
                admission,
                prompts,
                children,
                pump,
                lifecycle,
                emit,
            )
            return
        session.request("CMD_RUN", send=True)
        if consumption_probe:
            until = time.monotonic() + 10
            while not Path("/workspace/consume-awaiting").is_file():
                if time.monotonic() >= until:
                    # Publish only a fixed native failure category, never the
                    # underlying log, variable values, arguments or capability.
                    session.log.flush()
                    with Path(session.log.name).open("rb") as native_log:
                        native_log.seek(0, 2)
                        native_log.seek(max(0, native_log.tell() - 65536))
                        tail = native_log.read()
                    for reason in (
                        "Native RUN consumption has no admission identity",
                        "Native consumption probe configuration differs",
                        "Native consumption probe marker unavailable",
                        "Native consumption probe marker uncertain",
                        "Native consumption probe hold expired",
                    ):
                        if ("V08_NATIVE_RUN_DENIED:" + reason).encode() in tail:
                            emit("native-consumption-probe-denied", reason=reason)
                    raise TimeoutError(
                        "Native Executor did not reach its consumption hold"
                    )
                time.sleep(0.02)
            emit("native-consumption-awaiting-fence", execution_id=grant.execution_id)
            if not admission.consume_denials.wait(40) or not consume_fenced.is_set():
                raise RuntimeError(
                    "Stale native RUN did not reach final authority denial"
                )
            if (
                session.request("REQ_EXEC_INFO", context=True)["ExecutorStatus"]
                != "PAUSED"
                or controls.consumed
                or Path("/workspace/consume-probe-ran").exists()
            ):
                raise RuntimeError("Stale native RUN advanced after controller fencing")
            emit("native-stale-run-held", native_status="PAUSED", hold_retained=True)
            until = time.monotonic() + 35
            while not Path("/control/consume-probe-stop").is_file():
                if time.monotonic() >= until:
                    raise TimeoutError("Consumption probe host observation expired")
                if Path("/workspace/consume-probe-ran").exists():
                    raise RuntimeError(
                        "Stale native RUN executed during host observation"
                    )
                time.sleep(0.02)
            return  # Native cleanup/termination is never a reservation-release proof.
        running = False
        attempted_pause = {}
        pause_channel_failed = False
        next_poll = 0
        next_prompt_poll = 0
        child_running = set()
        previous_state = None
        next_position = 0
        position_count = 0
        while time.monotonic() < deadline:
            pump()
            if prompts is not None and time.monotonic() >= next_prompt_poll:
                # A bounded read cadence avoids ten idle workers saturating
                # the authority while actual native prompt callbacks commit.
                # Any failed delivery still exits; there is no mutation retry.
                next_prompt_poll = time.monotonic() + 0.2
                prompts.poll()
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
            information = session.request("REQ_EXEC_INFO", context=True)
            state = information["ExecutorStatus"]
            if (
                child_profile
                and position_count < 64
                and time.monotonic() >= next_position
            ):
                # Bounded fixture diagnostics: field names and code position,
                # never variables, procedure arguments, credentials or proofs.
                emit(
                    "native-child-position",
                    csp=str(information.get("Csp", ""))[:256],
                    code_name=str(information.get("CodeName", ""))[:256],
                )
                next_position = time.monotonic() + 1
                position_count += 1
            if child_profile and state != previous_state:
                emit("native-child-parent-status", native_status=state)
                previous_state = state
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
        if state == "FINISHED" and lifecycle is not None:
            # The legacy controller publishes FINISHED before setEndTime's
            # synchronous RaiseEvent. Keep the original processes/relay alive
            # until their real Context audit receipts arrive; never replay or
            # manufacture a missing event or treat this as a family barrier.
            lifecycle.wait(lambda: list(child_gate.started), pump)
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
            native_lifecycle_receipts_settled=lifecycle is not None,
            notifications_seen=count,
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
        protect_runtime()
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
