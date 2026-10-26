"""Real TLS disconnect, stalled reply and client death at durable recovery boundaries.

Host freeze/process evidence uses existing explicit fixtures. These tests do not
claim native quiescence, browser liveness detection or a deployed node partition.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

import pytest

from openbexi_spell_server.contracts import Fault, envelope
from openbexi_spell_server.transport import Handler
from test_launch import call
from test_services import request
import test_live_handoff as live
import test_native_rebind as rebind
import test_terminal_settlement as terminal

source, setup, ledger = live.source, live.setup, live.ledger


def record(case, **details):
    if directory := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
        with (Path(directory) / "controller-network.log").open("a") as stream:
            stream.write(
                json.dumps(dict(case=case, passed=True, host_proof="fixture", **details)) + "\n"
            )


@contextmanager
def cut_reply(monkeypatch, ledger, path, *, stall=False):
    original = Handler.reply
    committed, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def reply(handler, status, body):
        if handler.server is not ledger["server"] or handler.path != path or calls:
            return original(handler, status, body)
        assert status == 200, body
        calls.append(1)
        committed.set()
        try:
            if stall:
                assert release.wait(8), "Test reply hold did not settle"
            handler.connection.shutdown(socket.SHUT_RDWR)
            handler.close_connection = True
        finally:
            finished.set()

    with monkeypatch.context() as patch:
        patch.setattr(Handler, "reply", reply)
        try:
            yield committed, release, calls
        finally:
            release.set()
            if calls:
                assert finished.wait(2)


def observer_survives(ledger, pki):
    started = time.monotonic()
    view = live.observe(ledger, pki)
    assert time.monotonic() - started < 2
    assert view["owner"] == "alice" and view["epoch"] == 1
    assert terminal.held(ledger) == 1
    assert ledger["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    return view


@pytest.mark.parametrize("fault", ["disconnect", "client_death"])
def test_controller_close_reply_loss_keeps_fence_and_explicit_recovery(
    ledger, pki, monkeypatch, fault
):
    old = ledger["grant"]
    key = str(uuid.uuid4())
    body = dict(connection_id=ledger["connection"])
    payload = envelope("A", "alice", "session.close", body, key)
    with cut_reply(monkeypatch, ledger, "/v1/rpc", stall=fault == "client_death") as (
        committed,
        release,
        attempts,
    ):
        if fault == "client_death":
            code = """import json,sys,ssl,http.client
c=json.load(sys.stdin)
t=ssl.create_default_context(cafile=c['ca']);t.load_cert_chain(c['cert'],c['key'])
h=http.client.HTTPSConnection('localhost',c['port'],context=t,timeout=5)
h.request('POST','/v1/rpc',json.dumps(c['payload']),{'Content-Type':'application/json'})
h.getresponse().read()
"""
            child = subprocess.Popen(
                [sys.executable, "-c", code],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                child.stdin.write(
                    json.dumps(
                        dict(
                            ca=str(pki["ca"]),
                            cert=str(pki["listener"]["cert"]),
                            key=str(pki["listener"]["key"]),
                            port=ledger["server"].server_port,
                            payload=payload,
                        )
                    ).encode()
                )
                child.stdin.close()
                child.stdin = None
                assert committed.wait(4)
                child.kill()
                child.communicate(timeout=3)
                assert child.returncode < 0
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=3)
        else:
            with pytest.raises((OSError, http.client.HTTPException)):
                request(
                    ledger["server"],
                    pki["listener"]["client"],
                    "/v1/rpc",
                    subject=None,
                    payload=payload,
                )
        assert committed.is_set() and attempts == [1]
        assert observer_survives(ledger, pki)["control_state"] == "CONTROLLER_DISCONNECTED"
        assert call(ledger, pki, old, "check")[0] == 403
        release.set()
    # Only the durable close receipt is replayable. It cannot mint authority.
    replay = ledger["controller"]("session.close", body, key=key)
    assert replay["closed"] and "capability" not in replay
    _, _, _, epoch = rebind.resumed(ledger, pki)
    assert call(ledger, pki, old, "check")[0] == 403
    assert live.observe(ledger, pki)["control_state"] == "HANDOFF_PAUSED"
    activated = live.activate(ledger, pki, epoch)
    assert activated["grant"]["control_epoch"] == old.control_epoch
    assert activated["grant"]["connection_generation"] == old.connection_generation + 1
    assert terminal.held(ledger) == 1
    record(
        "controller_close",
        fault=fault,
        client_process_killed=fault == "client_death",
        old_grant_denied=True,
        explicit_host_recovery=True,
    )


@pytest.mark.parametrize("fault", ["disconnect", "timeout"])
def test_rebind_response_loss_cannot_bypass_host_barrier(ledger, pki, monkeypatch, fault):
    connection = ledger["controller"]("session.open", {})["connection_id"]
    body = dict(
        execution_id=ledger["grant"].execution_id, connection_id=connection, expected_epoch=1
    )
    key = str(uuid.uuid4())
    payload = envelope("A", "alice", "execution.rebind", body, key)
    with cut_reply(monkeypatch, ledger, "/v1/rpc", stall=fault == "timeout") as (
        committed,
        release,
        attempts,
    ):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                request,
                ledger["server"],
                pki["listener"]["client"],
                "/v1/rpc",
                subject=None,
                payload=payload,
                timeout=0.25,
            )
            assert committed.wait(3)
            assert observer_survives(ledger, pki)["control_state"] == "PAUSING"
            with pytest.raises((OSError, http.client.HTTPException)):
                future.result(timeout=3)
            release.set()
        assert attempts == [1]
    replay = ledger["controller"]("execution.rebind", body, key=key)
    assert replay["rebind_pending"] and replay["replayed"] and "capability" not in replay
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    state = live.host(ledger, pki, "status")
    assert state["barrier_id"] == replay["barrier_id"]
    live.host(
        ledger,
        pki,
        "complete",
        barrier_id=state["barrier_id"],
        evidence=live.evidence(ledger, state),
    )
    assert live.observe(ledger, pki)["control_state"] == "HANDOFF_PAUSED"
    assert terminal.held(ledger) == 1
    record("rebind_reply", fault=fault, same_barrier=True, automatic_resume=False)


@pytest.mark.parametrize("fault", ["disconnect", "timeout"])
def test_runtime_activation_network_loss_remains_uncertain(
    ledger, pki, tmp_path, monkeypatch, fault
):
    worker, path = live.runtime(ledger, pki, tmp_path)
    old = worker.request.copy()
    _, _, _, epoch = rebind.resumed(ledger, pki)
    path.write_text(epoch)
    with cut_reply(
        monkeypatch, ledger, "/v1/worker/handoff-activate", stall=fault == "timeout"
    ) as (committed, release, attempts):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.ensure)
            assert committed.wait(3)
            observer_survives(ledger, pki)
            with pytest.raises(Fault):
                future.result(timeout=6)
            release.set()
        assert attempts == [1]
    with pytest.raises(ValueError, match="uncertain"):
        worker.ensure()
    assert worker.failed and worker.request == old and worker.rotations == 0
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert terminal.held(ledger) == 1
    record("activation_reply", fault=fault, attempts=1, old_grant_denied=True, holds_retained=True)


def test_unreachable_controller_transport_does_not_claim_native_pause(ledger, pki):
    # A real TCP endpoint accepts but provides no TLS handshake or application
    # response. Restoration alone is not a control grant or a pause proof.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    connected, release = threading.Event(), threading.Event()

    def blackhole():
        with listener.accept()[0]:
            connected.set()
            release.wait(3)

    thread = threading.Thread(target=blackhole)
    thread.start()
    client = http.client.HTTPSConnection(
        "localhost", listener.getsockname()[1], context=pki["listener"]["client"], timeout=0.2
    )
    try:
        with pytest.raises(OSError):
            client.request("POST", "/v1/rpc", b"{}")
        assert connected.is_set()
        assert observer_survives(ledger, pki)["control_state"] == "OWNED"
        assert ledger["store"].db.execute("SELECT COUNT(*) FROM live_handoffs").fetchone()[0] == 0
    finally:
        client.close()
        release.set()
        thread.join(timeout=3)
        listener.close()
        assert not thread.is_alive()
    _, _, _, epoch = rebind.resumed(ledger, pki)
    assert live.observe(ledger, pki)["control_state"] == "HANDOFF_PAUSED"
    assert live.activate(ledger, pki, epoch)["activation_kind"] == "rebind"
    record(
        "transport_partition",
        native_pause_inferred=False,
        explicit_host_recovery=True,
        automatic_disconnect_detection=False,
    )
