"""Real subprocess/pipe checks for native bridge startup and command fencing.

The subprocess implements only the bridge JSON wire. These tests exercise the
actual Python Bridge; they do not claim execution of the SPELL native binaries.
"""

import json
from pathlib import Path
import queue
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from native_bridge_test_support import NORMAL, native, peer


def take(events, expected):
    item = events.get(timeout=2)
    assert item.get("event") == expected, item
    return item


@pytest.mark.parametrize("home", [None, Path("/opt/v08-native-home")])
def test_session_selects_bridge_from_its_checked_native_home(home):
    # NativeSession validates this operator mount at construction. This test
    # exercises its actual connection dispatch without launching a listener.
    session = native.NativeSession.__new__(native.NativeSession)
    session.native_home = home
    session.process = SimpleNamespace(poll=lambda: None)
    session.log, session.events = None, queue.Queue()
    with patch.object(native, "Bridge") as bridge:
        session.connect_bridge(9980, {}, time.monotonic() + 5)
    kwargs = bridge.call_args.kwargs
    assert str(kwargs["executable"]) == (
        "/opt/v08-native-home/bin/spell-host-ipc" if home else "/bridge/spell-host-ipc"
    )
    assert 0 < kwargs["connect_timeout"] <= 5


def test_notification_between_connected_and_constructor_return_is_not_lost():
    published = threading.Event()
    real_thread = threading.Thread

    class ReadyBeforeStartReturns(real_thread):
        def start(self):
            super().start()
            assert published.wait(2), "reader never received startup notification"

    class ObservedBridge(native.Bridge):
        def publish(self, item):
            super().publish(item)
            if item.get("event") == "notification":
                published.set()

    substitute = SimpleNamespace(
        Thread=ReadyBeforeStartReturns, Event=threading.Event, Lock=threading.Lock
    )
    with patch.object(native, "threading", substitute):
        with peer(
            "print(json.dumps({'event':'notification','ordinal':1}), flush=True)\n" + NORMAL,
            bridge_class=ObservedBridge,
        ) as (bridge, events):
            assert take(events, "notification")["ordinal"] == 1
            assert bridge.exchange("READ", "ROOT") == {"value": "42"}


def test_pre_handshake_notification_keeps_receive_order():
    preamble = "\n".join(
        (
            "print(json.dumps({'event':'notification','ordinal':0}), flush=True)",
            "print(json.dumps({'event':'connected'}), flush=True)",
            "print(json.dumps({'event':'notification','ordinal':1}), flush=True)",
        )
    )
    with peer(preamble=preamble) as (bridge, events):
        assert [take(events, "notification")["ordinal"] for _ in range(2)] == [0, 1]
        assert bridge.exchange("READ", "ROOT") == {"value": "42"}


def test_failed_connection_does_not_leave_failure_in_shared_session_queue():
    events = queue.Queue(maxsize=256)
    with pytest.raises(native.BridgeConnectionError):
        with peer(script="raise SystemExit(1)", preamble="", events=events):
            pytest.fail("failed child was accepted as connected")
    assert events.empty()
    with peer(events=events) as (bridge, _):
        assert bridge.exchange("READ", "ROOT") == {"value": "42"}
        assert events.empty()


def test_eof_after_connection_is_exposed_without_waiting_for_another_request():
    with peer("time.sleep(.10)\nraise SystemExit(0)") as (bridge, events):
        take(events, "connectionError")
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")


def test_explicit_connection_closed_prevents_further_command_writes():
    with peer(
        "time.sleep(.03)\nprint(json.dumps({'event':'connectionClosed'}),flush=True)\n" + NORMAL
    ) as (bridge, events):
        take(events, "connectionClosed")
        with pytest.raises(RuntimeError, match="unavailable|closed|failed"):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == 0


def test_valid_native_denial_does_not_disable_other_diagnostics():
    script = """
for line in sys.stdin:
    r=json.loads(line)
    if r['id']=='DENIED':
        print(json.dumps({'seq':r['seq'],'ok':False,'message':{
            'fields':{'ErrorMsg':'V08_NATIVE_MUTATION_DENIED'}}}),flush=True)
    else:
        print(json.dumps({'seq':r['seq'],'ok':True,'message':{'fields':{'value':'42'}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="V08_NATIVE_MUTATION_DENIED"):
            bridge.exchange("DENIED", "ROOT")
        assert bridge.exchange("READ", "ROOT") == {"value": "42"}


@pytest.mark.parametrize("wrong_seq", ["True", "'1'", "2", "None"])
def test_wrong_response_identity_fences_channel_and_never_replays(wrong_seq):
    script = f"""
for line in sys.stdin:
    r=json.loads(line)
    print(json.dumps({{'seq':{wrong_seq},'ok':True,'message':{{'fields':{{}}}}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        before = bridge.sequence
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == before, "uncertain request was retransmitted"


def test_timed_out_operation_is_not_retried_even_if_late_reply_arrives():
    script = """
for line in sys.stdin:
    r=json.loads(line)
    time.sleep(.15)
    print(json.dumps({'seq':r['seq'],'ok':True,'message':{'fields':{}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="timed out"):
            bridge.exchange("CMD_RUN", "ROOT", timeout=0.04)
        time.sleep(0.20)
        before = bridge.sequence
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == before == 1


def test_concurrent_exchange_is_rejected_before_second_wire_send():
    with tempfile.TemporaryDirectory() as directory:
        release = Path(directory) / "release"
        script = f"""
from pathlib import Path
for line in sys.stdin:
    r=json.loads(line)
    print(json.dumps({{'event':'request-observed','index':r['seq']}}),flush=True)
    deadline=time.monotonic()+2
    while not Path({str(release)!r}).exists() and time.monotonic()<deadline:
        time.sleep(.002)
    print(json.dumps({{'seq':r['seq'],'ok':True,'message':{{'fields':{{'value':'42'}}}}}}),flush=True)
"""
        with peer(script) as (bridge, events):
            result, errors = [], []

            def exchange():
                try:
                    result.append(bridge.exchange("FIRST", "ROOT"))
                except Exception as error:
                    errors.append(error)

            worker = threading.Thread(target=exchange)
            worker.start()
            try:
                take(events, "request-observed")
                with pytest.raises(RuntimeError, match="in flight"):
                    bridge.exchange("SECOND", "ROOT")
                assert bridge.sequence == 1
            finally:
                release.touch()
                worker.join(timeout=3)
            assert not worker.is_alive() and not errors
            assert result == [{"value": "42"}]
            assert events.empty()


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 11, "1"])
def test_invalid_timeout_rejected_before_sending(timeout):
    with peer() as (bridge, _):
        with pytest.raises(ValueError):
            bridge.exchange("CMD_RUN", "ROOT", timeout=timeout)
        assert bridge.sequence == 0


def test_malformed_wire_fails_closed_without_restarting_process():
    with peer("time.sleep(.03)\nprint('not JSON',flush=True)\n" + NORMAL) as (bridge, events):
        take(events, "connectionError")
        before = bridge.process.pid
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.process.pid == before and bridge.sequence == 0


def test_reentrant_pump_cannot_send_a_second_command():
    attempts = []
    with peer() as (bridge, _):

        def pump():
            with pytest.raises(RuntimeError, match="in flight"):
                bridge.exchange("NESTED", "ROOT")
            attempts.append(1)

        assert bridge.exchange("FIRST", "ROOT", pump=pump) == {"value": "42"}
        assert attempts and bridge.sequence == 1


def test_blocked_pipe_write_has_deadline_and_cannot_be_repeated():
    with peer("time.sleep(.6)") as (bridge, _):
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="write uncertain"):
            bridge.exchange("CMD_RUN", "ROOT", {"value": "x" * 1000000}, timeout=0.04)
        assert time.monotonic() - started < 0.5
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == 1


def test_transport_sequence_exhaustion_cannot_wrap():
    with peer() as (bridge, _):
        bridge.sequence = 2**32 - 1
        with pytest.raises(RuntimeError, match="sequence exhausted"):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == 2**32 - 1


def test_preconnect_notification_flood_fails_bounded_without_polluting_session():
    events = queue.Queue(maxsize=256)
    preamble = "\n".join(
        (
            "for i in range(257): print(json.dumps({'event':'notification','index':i}),flush=True)",
            "print(json.dumps({'event':'connected'}),flush=True)",
        )
    )
    with pytest.raises(native.BridgeConnectionError):
        with peer(preamble=preamble, events=events):
            pytest.fail("startup flood passed connection admission")
    assert events.empty()


def test_response_flood_is_bounded_and_fences_before_a_new_command():
    script = (
        """
time.sleep(.03)
for i in range(1000):
    print(json.dumps({'seq':i+10,'ok':True}),flush=True)
"""
        + NORMAL
    )
    with peer(script) as (bridge, events):
        take(events, "connectionError")
        assert bridge.replies.qsize() <= 2
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == 0


def test_oversized_frame_fences_without_retaining_its_payload():
    script = f"time.sleep(.03)\nprint('x'*{native.Bridge.MAX_FRAME + 1},flush=True)\n" + NORMAL
    with peer(script) as (bridge, events):
        failure = take(events, "connectionError")
        assert len(json.dumps(failure)) < 256
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")


def test_full_event_queue_does_not_hide_permanent_failure_latch():
    events = queue.Queue(maxsize=1)
    script = "\n".join(
        (
            "print(json.dumps({'event':'notification'}),flush=True)",
            "time.sleep(.03)",
            "raise SystemExit(0)",
        )
    )
    with peer(script, events=events) as (bridge, _):
        assert bridge.failed.wait(2)
        assert events.qsize() == 1
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == 0


def notification(procedure, status):
    return {
        "event": "message",
        "message": {
            "fields": {"ProcId": procedure, "DataType": "STATUS", "ExecutorStatus": status}
        },
    }


def test_only_exact_root_paused_notification_can_complete_startup():
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    for procedure in ("other#1", "root#10", "child#1", None):
        events.put(notification(procedure, "PAUSED"))
    observed.drain(events)
    assert not observed.paused({"ProcId": "root#1", "ExecutorStatus": "PAUSED"})
    events.put(notification("root#1", "PAUSED"))
    observed.drain(events)
    assert observed.paused({"ProcId": "root#1", "ExecutorStatus": "PAUSED"})
    assert not observed.paused({"ProcId": "root#1", "ExecutorStatus": "LOADED"})


def test_newer_running_notification_rejects_stale_paused_reply():
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    events.put(notification("root#1", "PAUSED"))
    events.put(notification("root#1", "RUNNING"))
    observed.drain(events)
    assert not observed.paused({"ProcId": "root#1", "ExecutorStatus": "PAUSED"})


@pytest.mark.parametrize("status", ["ERROR", "ABORTED", "FINISHED"])
def test_terminal_root_notification_cannot_be_overwritten_by_stale_read(status):
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    events.put(notification("root#1", "PAUSED"))
    events.put(notification("root#1", status))
    with pytest.raises(RuntimeError, match="terminal during startup"):
        observed.drain(events)
    assert observed.status == status
    assert not observed.paused({"ProcId": "root#1", "ExecutorStatus": "PAUSED"})


@pytest.mark.parametrize("event", ["connectionError", "connectionClosed"])
def test_startup_connection_failures_are_not_treated_as_status_progress(event):
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    events.put({"event": event, "error": "private-data-that-must-not-be-logged"})
    with pytest.raises(RuntimeError, match="Native startup connection failed") as error:
        observed.drain(events)
    assert "private-data" not in str(error.value)


def test_startup_notification_work_yields_and_has_no_lifetime_limit():
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    for i in range(3072):
        events.put({"event": "message", "message": {"fields": {"value": str(i)}}})
    observed.drain(events)
    assert events.qsize() == 3072 - 64
    while not events.empty():
        observed.drain(events)
    assert observed.notifications == 3072
    assert not observed.paused({"ProcId": "root#1", "ExecutorStatus": "PAUSED"})


def test_native_session_request_explicit_startup_pump_is_used_without_replacing_worker_pump():
    session = native.NativeSession.__new__(native.NativeSession)
    calls = []

    def worker_pump():
        return None

    def startup_pump():
        return None

    session.pump = worker_pump
    session.instance = "root#1"
    session.context = SimpleNamespace(exchange=lambda *args, **kw: calls.append((args, kw)))
    session.request("REQ_OPEN_EXEC", context=True, pump=startup_pump)
    session.request("REQ_EXEC_INFO", context=True)
    assert calls[0][1]["pump"] is startup_pump
    assert calls[1][1]["pump"] is worker_pump
    assert session.pump is worker_pump


def test_startup_status_inventory_matches_original_native_enum():
    import re
    import zipfile

    archive = Path(__file__).resolve().parents[2] / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as bundle:
        header = bundle.read("include/SPELL_EXC/SPELLexecutorStatus.H").decode()
    assert native.StartupObservation.STATUSES == set(re.findall(r"\bSTATUS_([A-Z]+)\b", header))


@pytest.mark.parametrize("status", [None, True, 1, {}, [], "READY", "invented"])
def test_malformed_or_non_native_startup_status_reply_is_rejected(status):
    observed = native.StartupObservation("root#1")
    with pytest.raises(RuntimeError, match="Invalid native startup status response"):
        observed.paused({"ProcId": "root#1", "ExecutorStatus": status})


def test_utf8_byte_frame_bound_cannot_be_evaded_with_multibyte_characters():
    # Far fewer than MAX_FRAME characters, but more than MAX_FRAME bytes.
    script = (
        "time.sleep(.03)\n"
        f"print(json.dumps({{'event':'message','text':'€'*{native.Bridge.MAX_FRAME // 3}}},"
        "ensure_ascii=False),flush=True)\n" + NORMAL
    )
    with peer(script) as (bridge, events):
        failure = take(events, "connectionError")
        assert len(json.dumps(failure)) < 256
        assert bridge.failed.is_set()
        assert bridge.sequence == 0


def test_startup_pump_can_drain_burst_before_open_reply_without_sending_run():
    script = """
for line in sys.stdin:
    r = json.loads(line)
    if r['id'] == 'REQ_OPEN_EXEC':
        for i in range(900):
            print(json.dumps({'event':'message','message':{
                'fields':{'ProcId':'other#1','DataType':'STATUS','ExecutorStatus':'PAUSED'}}}),flush=True)
        print(json.dumps({'event':'message','message':{
            'fields':{'ProcId':'root#1','DataType':'STATUS','ExecutorStatus':'PAUSED'}}}),flush=True)
    print(json.dumps({'seq':r['seq'],'ok':True,
        'message':{'fields':{'ProcId':'root#1','ExecutorStatus':'PAUSED'}}}),flush=True)
"""
    with peer(script) as (bridge, events):
        observed = native.StartupObservation("root#1")
        result = bridge.exchange("REQ_OPEN_EXEC", "CTX", pump=lambda: observed.drain(events))
        while not events.empty():
            observed.drain(events)
        assert observed.notifications == 901
        assert observed.paused(result)
        assert bridge.sequence == 1
        assert not bridge.failed.is_set()


def test_interrupted_in_flight_command_permanently_fences_transport():
    with peer("time.sleep(.15)\n" + NORMAL) as (bridge, _):

        def interrupted():
            raise KeyboardInterrupt("injected interrupted operator")

        with pytest.raises(KeyboardInterrupt):
            bridge.exchange("CMD_RUN", "root#1", send=True, pump=interrupted)
        assert bridge.failed.is_set()
        with pytest.raises(RuntimeError, match="unavailable"):
            bridge.exchange("CMD_RUN", "root#1", send=True)
        assert bridge.sequence == 1


@pytest.mark.parametrize("procedure", [None, True, "other#1", "root#10", "child#1"])
def test_status_poll_for_another_member_cannot_complete_root_startup(procedure):
    observed = native.StartupObservation("root#1")
    events = queue.Queue()
    events.put(notification("root#1", "PAUSED"))
    observed.drain(events)
    with pytest.raises(RuntimeError, match="scope differs"):
        observed.paused({"ProcId": procedure, "ExecutorStatus": "PAUSED"})


def test_real_session_start_with_worker_wrapper_drains_burst_before_ready(tmp_path):
    """Actual Python startup path and real pipes, not native SPELL binaries."""
    from contextlib import ExitStack
    import importlib.util

    project = tmp_path / "project"
    project.mkdir()
    script_path = project / "root.py"
    script_path.write_text("FIRST = 1\n")
    session = native.NativeSession(project, script_path, {})
    skeleton = Path(session.directory.name) / "session"
    (skeleton / "config/contexts").mkdir(parents=True)
    server_file = skeleton / "config/server.xml"
    server_file.write_text("<server><context/></server>")
    (skeleton / "config/contexts/context_example.xml").write_text(
        "<context><procpath/><driver/><libpath/></context>"
    )
    example = json.dumps({"config": str(server_file), "environment": {}})
    wire_log = tmp_path / "wire.jsonl"
    bridge_script = f"""
from pathlib import Path
for line in sys.stdin:
    req = json.loads(line)
    with Path({str(wire_log)!r}).open('a') as log:
        log.write(json.dumps({{'id':req['id'],'fields':req['fields']}})+'\\n')
    if req['id'] == 'REQ_OPEN_EXEC':
        for i in range(900):
            print(json.dumps({{'event':'message','message':{{'fields':{{
                'ProcId':'other#1','DataType':'STATUS','ExecutorStatus':'FINISHED'}}}}}}),flush=True)
        print(json.dumps({{'event':'message','message':{{'fields':{{
            'ProcId':'root#1','DataType':'STATUS','ExecutorStatus':'PAUSED'}}}}}}),flush=True)
    print(json.dumps({{'seq':req['seq'],'ok':True,'message':{{'fields':{{
        'ProcId':'root#1','ExecutorStatus':'PAUSED'}}}}}}),flush=True)
"""
    wrapper_path = Path(__file__).resolve().parents[2] / "host_runtime/python/control_journal.py"
    spec = importlib.util.spec_from_file_location("native_startup_journal_wiring", wrapper_path)
    journal_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(journal_module)
    wrapper = journal_module.NativeRunJournal.__new__(journal_module.NativeRunJournal)
    wrapper.original = session.request
    session.request = wrapper.dispatch
    listener_calls = []

    def listener_exchange(identifier, receiver, fields=None, **kwargs):
        listener_calls.append(identifier)
        kwargs["pump"]()
        return {"ContextStatus": "RUNNING", "ContextPort": "9981"}

    listener = SimpleNamespace(exchange=listener_exchange)
    try:
        with peer(bridge_script, events=session.events) as (bridge, _):
            session.connect_bridge = lambda port, *_: listener if port == 9980 else bridge
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(native.subprocess, "check_output", return_value=example)
                )
                stack.enter_context(
                    patch.object(native.subprocess, "Popen", return_value=SimpleNamespace())
                )
                session.start()
            assert session.opened
            assert session.events.empty()
            assert not bridge.failed.is_set()
            assert listener_calls == ["REQ_GUI_LOGIN", "REQ_CTX_INFO"]
        wire = [json.loads(line) for line in wire_log.read_text().splitlines()]
        assert [entry["id"] for entry in wire[:2]] == ["REQ_GUI_LOGIN", "REQ_OPEN_EXEC"]
        # Read-only status polls may repeat while bounded notification batches
        # drain; mutations must not. This is not retry of an uncertain OPEN.
        assert wire[2:] and all(entry["id"] == "REQ_EXEC_INFO" for entry in wire[2:])
        assert sum(entry["id"] == "REQ_OPEN_EXEC" for entry in wire) == 1
        assert all(entry["fields"]["ProcId"] == "root#1" for entry in wire[1:])
        assert not any(entry["id"] == "CMD_RUN" for entry in wire)
    finally:
        if session.log is not None:
            session.log.close()
        session.directory.cleanup()


@pytest.mark.parametrize(
    "failure", ["Native request timed out", "IPC channel disconnected", "bad native field"]
)
def test_bridge_exception_without_native_response_permanently_fences(failure):
    script = f"""
for line in sys.stdin:
    r=json.loads(line)
    print(json.dumps({{'seq':r['seq'],'ok':False,'error':{failure!r}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="outcome uncertain"):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.failed.is_set()
        previous = bridge.sequence
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == previous


@pytest.mark.parametrize("message", [None, [], {"fields": []}])
def test_malformed_negative_native_response_cannot_restore_channel(message):
    script = f"""
for line in sys.stdin:
    r=json.loads(line)
    print(json.dumps({{'seq':r['seq'],'ok':False,'message':{message!r}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="fields differ"):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.failed.is_set()
        previous = bridge.sequence
        with pytest.raises(RuntimeError):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.sequence == previous


def test_native_denial_combined_with_transport_error_is_uncertain():
    script = """
for line in sys.stdin:
    r=json.loads(line)
    print(json.dumps({'seq':r['seq'],'ok':False,'error':'lost channel','message':{
        'fields':{'ErrorMsg':'V08_NATIVE_MUTATION_DENIED'}}}),flush=True)
"""
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="outcome uncertain"):
            bridge.exchange("CMD_RUN", "ROOT")
        assert bridge.failed.is_set()
