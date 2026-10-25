"""Startup wire/backpressure regressions; these do not emulate native semantics."""

import importlib.util
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def native():
    spec = importlib.util.spec_from_file_location(
        "v08_startup_under_test", ROOT / "host_runtime/python/native.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status(instance="main#1", state="PAUSED"):
    return {
        "event": "message",
        "message": {
            "id": "MSG_NOTIFY",
            "fields": {"DataType": "STATUS", "ProcId": instance, "ExecutorStatus": state},
        },
    }


def test_constructor_cannot_lose_notifications_already_read_after_connected(native, monkeypatch):
    notification = status()
    process = SimpleNamespace(
        stdout=io.StringIO(
            json.dumps({"event": "connected"}) + "\n" + json.dumps(notification) + "\n"
        )
    )

    # Force the legal scheduling: reader handles connected+notification before
    # constructor resumes. A private bootstrap queue must never be swapped out.
    class ImmediateReader:
        def __init__(self, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(native.threading, "Thread", ImmediateReader)
    monkeypatch.setattr(native.subprocess, "Popen", lambda *_a, **_kw: process)
    events = queue.Queue(maxsize=256)
    bridge = native.Bridge(9981, {}, io.StringIO(), events)
    assert bridge.events is events
    assert events.get_nowait() == notification


@pytest.fixture
def wire_session(native, tmp_path, monkeypatch):
    """Real subprocess pipes and real Bridge reader, with a scripted wire peer."""
    helper = tmp_path / "wire_peer.py"
    helper.write_text("""import json, sys
port = int(sys.argv[1])
print(json.dumps({"event":"connected"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    ident = request["id"]
    fields = {}
    if ident == "REQ_CTX_INFO":
        fields = {"ContextStatus":"RUNNING", "ContextPort":"9981"}
    if ident == "REQ_OPEN_EXEC":
        for index in range(640):
            print(json.dumps({"event":"message", "message":{"id":"MSG_NOTIFY", "fields":{
                "DataType":"STATUS", "ExecutorStatus":"LOADED", "ProcId":"main#1"}}}), flush=True)
        print(json.dumps({"event":"message", "message":{"id":"MSG_NOTIFY", "fields":{
            "DataType":"STATUS", "ExecutorStatus":"PAUSED", "ProcId":"main#1"}}}), flush=True)
    if ident == "REQ_EXEC_INFO":
        fields = {"ExecutorStatus":"PAUSED"}
    print(json.dumps({"seq":request["seq"], "ok":True, "message":{"fields":fields}}), flush=True)
""")
    project = tmp_path / "project"
    project.mkdir()
    script = project / "main.py"
    script.write_text("VALUE = 1\n")
    popen = subprocess.Popen
    processes = []

    def spawn(arguments, **options):
        if arguments[0] == "/bridge/spell-host-ipc":
            process = popen([sys.executable, "-u", str(helper), arguments[1]], **options)
            processes.append(process)
            return process
        assert arguments[:2] == ["spell-native", "listener"]
        return SimpleNamespace(poll=lambda: None)

    def initialize(arguments, **_kwargs):
        assert arguments[:2] == ["spell-native", "init-example"]
        home = Path(arguments[2])
        context = home / "config/contexts/context_example.xml"
        context.parent.mkdir(parents=True)
        context.write_text("<context><procpath>old</procpath><libpath>old</libpath></context>")
        server = home / "config/server.xml"
        server.write_text("<server><context/></server>")
        return json.dumps({"config": str(server), "environment": {}})

    monkeypatch.setattr(native.subprocess, "Popen", spawn)
    monkeypatch.setattr(native.subprocess, "check_output", initialize)
    session = native.NativeSession(project, script, {})
    try:
        yield session
    finally:
        for bridge in (session.context, session.listener):
            if bridge:
                bridge.close()
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
        if session.log:
            session.log.close()
        session.directory.cleanup()


def test_actual_start_drains_more_than_queue_capacity_before_open_reply(wire_session):
    # The peer cannot send its OPEN reply until >256 events have crossed the
    # wire. Without a startup-owned pump, the reader blocks on the full queue.
    wire_session.start()
    assert wire_session.opened is True
    assert wire_session.startup_notifications_seen == 641
    assert wire_session.events.maxsize == 256
    assert wire_session.pump is None


def test_runtime_consumer_cannot_steal_startup_pause_and_is_restored(wire_session):
    called = []

    def consumer():
        called.append(True)

    wire_session.pump = consumer
    wire_session.start()
    assert not called
    assert wire_session.pump is consumer


def bare_session(native):
    session = native.NativeSession.__new__(native.NativeSession)
    session.instance = "main#1"
    session.events = queue.Queue(maxsize=256)
    session.startup_notifications_seen = 0
    session._startup_paused_notification = False
    return session


@pytest.mark.parametrize("instance", ["child#0", "main#10", "", None])
def test_other_members_cannot_satisfy_root_startup_pause(native, instance):
    session = bare_session(native)
    session.events.put_nowait(status(instance))
    session._pump_startup_notifications()
    assert not session._startup_paused_notification


def test_startup_pump_is_bounded_and_still_surfaces_channel_failure(native):
    session = bare_session(native)
    for _ in range(200):
        session.events.put_nowait(status(state="LOADED"))
    session._pump_startup_notifications()
    assert session.startup_notifications_seen == 64
    assert session.events.qsize() == 136
    while not session.events.empty():
        session._pump_startup_notifications()
    session.events.put_nowait(status())
    session.events.put_nowait({"event": "connectionError", "error": "injected"})
    with pytest.raises(RuntimeError):
        session._pump_startup_notifications()
    assert session._startup_paused_notification  # readiness cannot swallow failure


def test_failed_start_restores_consumer_and_does_not_retry(native, monkeypatch):
    session = bare_session(native)

    def consumer():
        pass

    session.pump = consumer
    calls = []

    def failed(self):
        calls.append(True)
        assert self.pump == self._pump_startup_notifications
        raise RuntimeError("sent OPEN has uncertain outcome")

    monkeypatch.setattr(native.NativeSession, "_start_owned", failed, raising=False)
    with pytest.raises(RuntimeError, match="uncertain outcome"):
        session.start()
    assert len(calls) == 1 and session.pump is consumer
