"""Real DSS sockets, unchanged idle cadence and graceful handler durability."""

import errno
import http.client
import json
import os
from pathlib import Path
import socket
import socketserver
import threading
import time
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dss import server as module  # noqa: E402
from dss.engine import DssEngine  # noqa: E402
from dss.packets import decode_tm, encode_tc, recv_packet  # noqa: E402
from dss.server import ApiServer, DssRuntime, TcServer  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX shutdown pipe qualification")


@pytest.fixture
def runtime(tmp_path):
    engine = DssEngine(tmp_path / "shutdown.sqlite")
    value = DssRuntime(engine, bootstrap_servers="unused.invalid:9092")
    try:
        yield value
    finally:
        engine.close()


def selector_observer(monkeypatch):
    original = socketserver._ServerSelector
    entered = threading.Event()
    waits = []

    class ObservedSelector(original):
        def select(self, timeout=None):
            waits.append(timeout)
            if timeout == 0.5:
                entered.set()
            return super().select(timeout)

    monkeypatch.setattr(socketserver, "_ServerSelector", ObservedSelector)
    return entered, waits


def serving(server):
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    return thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(5)
    assert not thread.is_alive()


@pytest.mark.parametrize("kind", [TcServer, ApiServer])
def test_idle_shutdown_wakes_original_half_second_poll(runtime, monkeypatch, kind):
    entered, waits = selector_observer(monkeypatch)
    measurements = {}
    for baseline in [True, False]:
        server = kind(("127.0.0.1", 0), runtime)
        if baseline:
            server.serve_forever = socketserver.BaseServer.serve_forever.__get__(server)
            server.shutdown = socketserver.BaseServer.shutdown.__get__(server)
        entered.clear()
        thread = serving(server)
        try:
            assert entered.wait(5)
            start = time.monotonic()
            server.shutdown()
            measurements["original" if baseline else "candidate"] = time.monotonic() - start
        finally:
            server.server_close()
            thread.join(5)
            assert not thread.is_alive()
    print(json.dumps(dict(server=kind.__name__, poll_interval=0.5, seconds=measurements)))
    assert measurements["original"] >= 0.35
    assert measurements["candidate"] < 0.20
    assert set(waits) <= {0, 0.5} and 0.5 in waits


def test_wakeup_does_not_add_service_actions_or_change_idle_cadence(runtime, monkeypatch):
    entered, waits = selector_observer(monkeypatch)
    server = TcServer(("127.0.0.1", 0), runtime)
    ticks = []
    second = threading.Event()

    def service_actions():
        ticks.append(time.monotonic())
        if len(ticks) == 2:
            second.set()

    server.service_actions = service_actions
    thread = serving(server)
    try:
        assert entered.wait(5) and second.wait(3)
        server.shutdown()
        assert len(ticks) == 2 and ticks[1] - ticks[0] >= 0.45
        assert set(waits) <= {0, 0.5}
    finally:
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


@pytest.mark.parametrize("kind,capacity", [(TcServer, 16), (ApiServer, 4)])
def test_restart_concurrent_shutdown_retains_slots_and_closes_owned_pipes(
    runtime, monkeypatch, kind, capacity
):
    entered, _ = selector_observer(monkeypatch)
    server = kind(("127.0.0.1", 0), runtime)
    initial = set(os.listdir("/proc/self/fd"))
    try:
        for _ in range(8):
            entered.clear()
            thread = serving(server)
            assert entered.wait(5)
            pipe = server._shutdown_wakeup
            assert pipe is not None
            assert all(not os.get_inheritable(fd) and not os.get_blocking(fd) for fd in pipe)
            callers = [threading.Thread(target=server.shutdown) for _ in range(4)]
            for caller in callers:
                caller.start()
            for caller in callers:
                caller.join(5)
                assert not caller.is_alive()
            thread.join(5)
            assert not thread.is_alive() and server._shutdown_wakeup is None
            for fd in pipe:
                with pytest.raises(OSError) as error:
                    os.fstat(fd)
                assert error.value.errno == errno.EBADF
            # A shutdown arriving after the old loop finished has standard
            # BaseServer semantics: consume that request on the next start.
            if server._BaseServer__shutdown_request:
                server.serve_forever()
            assert all(server.slots.acquire(blocking=False) for _ in range(capacity))
            assert not server.slots.acquire(blocking=False)
            for _ in range(capacity):
                server.slots.release()
            assert set(os.listdir("/proc/self/fd")) == initial
    finally:
        server.server_close()


def command(runtime):
    state = runtime.engine.state()
    return dict(
        schema_version="openbexi.dss.tc/1",
        satellite_id="GENERIC",
        database_revision=state["database_revision"],
        database_digest=state["database_digest"],
        satellite_epoch=state["epoch"],
        scenario_id=state["scenario_id"],
        operation_id="shutdown-transport",
        procedure_id="tcp-test",
        execution_id="execution-1",
        plan_id="plan-1",
        element_id="element-1",
        command_name="CMDNAME",
        command_digest="a" * 64,
        arguments=[],
        stage="TRANSPORT",
    )


def test_tcp_shutdown_drains_accepted_handler_and_preserves_durable_ack(
    runtime, monkeypatch, tmp_path
):
    entered, _ = selector_observer(monkeypatch)
    committed, release, closed = threading.Event(), threading.Event(), threading.Event()
    original = runtime.engine.process_tc

    def held(*args, **kwargs):
        answer = original(*args, **kwargs)
        committed.set()
        assert release.wait(5)
        return answer

    monkeypatch.setattr(runtime.engine, "process_tc", held)
    server = TcServer(("127.0.0.1", 0), runtime)
    thread = serving(server)
    connection = socket.create_connection(server.server_address, timeout=3)
    closer = None
    try:
        assert entered.wait(5)
        connection.sendall(encode_tc(command(runtime), sequence=1))
        assert committed.wait(5)
        server.shutdown()
        thread.join(5)
        assert not thread.is_alive()

        def close():
            server.server_close()
            closed.set()

        closer = threading.Thread(target=close)
        closer.start()
        assert not closed.wait(0.1)
        release.set()
        packet = recv_packet(connection)
        assert decode_tm(packet)["outcome"] == "ACCEPTED"
        connection.close()
        assert closed.wait(5)
        evidence = runtime.engine.evidence(runtime.engine.state()["scenario_id"])
        assert len(evidence["operations"]) == 1
        assert evidence["operations"][0]["acknowledgement"]["outcome"] == "ACCEPTED"
        restored = DssEngine(tmp_path / "shutdown.sqlite")
        try:
            assert restored.evidence(evidence["scenario_id"]) == evidence
        finally:
            restored.close()
    finally:
        release.set()
        connection.close()
        if closer is not None:
            closer.join(5)
            assert not closer.is_alive()
        stop(server, thread)


def test_http_shutdown_drains_active_response(runtime, monkeypatch):
    entered, _ = selector_observer(monkeypatch)
    active, release, closed = threading.Event(), threading.Event(), threading.Event()
    original = runtime.engine.state

    def state():
        result = original()
        active.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(runtime.engine, "state", state)
    server = ApiServer(("127.0.0.1", 0), runtime)
    thread = serving(server)
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    closer = None
    try:
        assert entered.wait(5)
        connection.request("GET", "/api/v1/state")
        assert active.wait(5)
        server.shutdown()
        closer = threading.Thread(target=lambda: (server.server_close(), closed.set()))
        closer.start()
        assert not closed.wait(0.1)
        release.set()
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read()) == {**original(), "transport": runtime.health()}
        connection.close()
        assert closed.wait(5)
    finally:
        release.set()
        connection.close()
        if closer is not None:
            closer.join(5)
            assert not closer.is_alive()
        stop(server, thread)


@pytest.mark.parametrize("failure", ["pipe", "selector", "write", "non-posix"])
def test_unsupported_wakeup_retains_original_polling_shutdown(runtime, monkeypatch, failure):
    entered, _ = selector_observer(monkeypatch)
    real_os = module.os

    class FailingOS:
        def __getattr__(self, name):
            if name == "name" and failure == "non-posix":
                return "nt"
            if name == failure:

                def failed(*args, **kwargs):
                    raise OSError(errno.ENOSYS, "controlled unavailable wakeup")

                return failed
            return getattr(real_os, name)

    monkeypatch.setattr(module, "os", FailingOS())
    if failure == "selector":
        original = socketserver._ServerSelector

        class RefusesPipe(original):
            def register(self, fileobj, events, data=None):
                if isinstance(fileobj, int):
                    raise ValueError("controlled unsupported pipe")
                return super().register(fileobj, events, data)

        monkeypatch.setattr(socketserver, "_ServerSelector", RefusesPipe)
    server = TcServer(("127.0.0.1", 0), runtime)
    thread = serving(server)
    try:
        assert entered.wait(5)
        start = time.monotonic()
        server.shutdown()
        assert 0.35 <= time.monotonic() - start < 2
    finally:
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def test_shutdown_before_pipe_publication_is_not_lost(runtime, monkeypatch):
    opening, publish = threading.Event(), threading.Event()
    original = module.BoundedThreads._open_shutdown_wakeup

    def held(selector):
        result = original(selector)
        opening.set()
        assert publish.wait(5)
        return result

    monkeypatch.setattr(module.BoundedThreads, "_open_shutdown_wakeup", staticmethod(held))
    server = TcServer(("127.0.0.1", 0), runtime)
    thread = serving(server)
    assert opening.wait(5)
    waiting = threading.Event()
    shutdown_event = server._BaseServer__is_shut_down

    class ObservedEvent:
        def wait(self):
            waiting.set()
            return shutdown_event.wait()

        def set(self):
            shutdown_event.set()

    server._BaseServer__is_shut_down = ObservedEvent()
    caller = threading.Thread(target=server.shutdown)
    caller.start()
    try:
        assert waiting.wait(5)
        with server._shutdown_wakeup_lock:
            assert server._BaseServer__shutdown_request
        publish.set()
        caller.join(5)
        thread.join(5)
        assert not caller.is_alive() and not thread.is_alive()
        assert server._shutdown_wakeup is None
    finally:
        publish.set()
        server.server_close()
