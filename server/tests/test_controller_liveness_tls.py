"""Abrupt controller PID death and lost heartbeat ACKs over production mTLS.

The worker/host pause evidence is explicitly a fixture; native family continuity
is established separately by the hosted Docker handoff cohorts.
"""

from functools import partial
import json
import select
import subprocess
import sys
import time

import pytest

from openbexi_spell_server.services import Context
from test_launch import call
from test_services import request
from openbexi_spell_server.contracts import envelope
import test_live_handoff as live
import test_native_rebind as rebind
import test_preflight as helpers
from test_controller_network_recovery import cut_reply, observer_survives, record

source, ledger = live.source, live.ledger


@pytest.fixture
def setup(tmp_path, pki, source, monkeypatch):
    monkeypatch.setattr(helpers, "Context", partial(Context, controller_liveness_seconds=5))
    for setup in helpers.worker_setup.__wrapped__(tmp_path, pki, source):
        session = setup["controller"]("session.open", {})
        execution = setup["controller"](
            "execution.rebind",
            dict(
                execution_id=setup["execution"]["id"],
                connection_id=session["connection_id"],
                expected_epoch=1,
            ),
        )
        setup.update(connection=session["connection_id"], execution=execution, lease=session)
        yield setup


CLIENT = """import json,sys,ssl,http.client,time,uuid
from openbexi_spell_server.contracts import envelope
c=json.load(sys.stdin)
t=ssl.create_default_context(cafile=c['ca']);t.load_cert_chain(c['cert'],c['key'])
nonce=c['nonce']
while True:
 h=http.client.HTTPSConnection('localhost',c['port'],context=t,timeout=2)
 body=envelope('A','alice','session.heartbeat',{'connection_id':c['connection'],'heartbeat_nonce':nonce},str(uuid.uuid4()))
 h.request('POST','/v1/rpc',json.dumps(body),{'Content-Type':'application/json'})
 r=h.getresponse();data=json.loads(r.read());h.close()
 if r.status!=200:sys.exit(2)
 nonce=data['result']['heartbeat_nonce']
 print('renewed',flush=True)
 time.sleep(data['result']['lease_seconds']/3)
"""


@pytest.mark.parametrize("fault", ["client_death", "heartbeat_reply_loss", "heartbeat_stall"])
def test_abrupt_loss_is_automatically_fenced_then_requires_explicit_recovery(
    ledger, pki, monkeypatch, fault
):
    child = subprocess.Popen(
        [sys.executable, "-c", CLIENT],
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
                    connection=ledger["connection"],
                    nonce=ledger["lease"]["heartbeat_nonce"],
                )
            ).encode()
        )
        child.stdin.close()
        assert select.select([child.stdout], [], [], 3)[0], "Client did not renew its lease"
        assert child.stdout.readline() == b"renewed\n", (
            child.stderr.read() if child.poll() is not None else "no ACK"
        )
        if fault == "client_death":
            child.kill()
            child.wait(timeout=2)
            until_fenced(ledger, pki)
        else:
            with cut_reply(monkeypatch, ledger, "/v1/rpc", stall=fault == "heartbeat_stall") as (
                committed,
                release,
                attempts,
            ):
                assert committed.wait(3)
                until_fenced(ledger, pki)
                release.set()
                assert len(attempts) == 1
        assert call(ledger, pki, ledger["grant"], "check")[0] == 403
        status, _ = request(
            ledger["server"],
            pki["listener"]["client"],
            "/v1/rpc",
            subject=None,
            payload=envelope(
                "A",
                "alice",
                "session.heartbeat",
                dict(
                    connection_id=ledger["connection"],
                    heartbeat_nonce=ledger["lease"]["heartbeat_nonce"],
                ),
                "late-heartbeat",
            ),
        )
        assert status == 403
        # Original host-proof fixture remains necessary after automatic detection.
        state, evidence, bound, epoch = rebind.resumed(ledger, pki)
        assert bound["epoch"] == ledger["grant"].control_epoch
        assert bound["connection_generation"] == ledger["grant"].connection_generation + 1
        assert live.activate(ledger, pki, epoch)
        record(
            fault + "-automatic",
            automatic_disconnect_detection=True,
            explicit_close_sent=False,
            holds_retained=True,
            automatic_resume=False,
            controller_pid=child.pid,
        )
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        child.stdout.close()
        child.stderr.close()


def until_fenced(ledger, pki):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        row = observer_survives(ledger, pki)
        if row["control_state"] == "CONTROLLER_DISCONNECTED":
            assert not row["pause_barrier"]["quiescence_proven"]
            return
        time.sleep(0.05)
    raise AssertionError("Controller loss was not automatically fenced")
