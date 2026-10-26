"""Real DSS death/restart and post-commit stream failures retain original holds.

Single-execution cases use worker mTLS. The ten-execution case uses the actual
authority/driver gate directly; it does not claim native worker or Pod identity.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import time
import uuid
from urllib.request import Request, urlopen

import pytest

from openbexi_spell_server.contracts import Fault
import test_effects as effects
import test_native_driver as native

from openbexi_spell_dss.fenced_transport import Transport
from openbexi_spell_dss.journal import UncertainEffect

ROOT = Path(__file__).resolve().parents[2]
STAGES = ("TRANSPORT", "LOADING", "RELEASE", "ACKNOWLEDGEMENT", "ONBOARD_EXECUTION")
driver_setup = native.driver_setup
authority = effects.authority


class DssProcess:
    def __init__(self, path, mode="none", stage="RELEASE"):
        self.path = path
        self.child = self.transport = None
        self.tcp_port = self.http_port = 0
        try:
            self.start(mode, stage)
        except BaseException:
            if self.child:
                if self.child.poll() is None:
                    self.child.kill()
                self.child.communicate(timeout=5)
            if self.transport:
                self.transport.close()
            raise

    def event(self):
        assert select.select([self.child.stdout], [], [], 5)[0], "DSS process event timed out"
        raw = self.child.stdout.readline(4097)
        assert raw and len(raw) <= 4096, "DSS process event missing or oversized"
        return json.loads(raw)

    def start(self, mode="none", stage="RELEASE"):
        assert self.child is None or self.child.poll() is not None
        self.child = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "server/tests/dss_lifecycle_process.py"),
                str(self.path),
                str(self.tcp_port),
                str(self.http_port),
                stage,
                mode,
            ],
            env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        info = self.event()
        assert info["event"] == "ready" and info["pid"] != os.getpid()
        self.tc_address = tuple(info["tcp"])
        self.tcp_port, self.http_port = self.tc_address[1], info["http"]
        self.url = "http://127.0.0.1:" + str(self.http_port)
        if self.transport is None:
            self.transport = Transport(self.url, self.tc_address)
        self.database = self.transport.database

    def get(self, path):
        return self.transport.get(path)

    def stop(self, expected=0):
        _out, error = self.child.communicate(b"x", timeout=8)
        assert self.child.returncode == expected, error.decode()

    def close(self):
        if self.child and self.child.poll() is None:
            try:
                self.stop()
            finally:
                if self.child.poll() is None:
                    self.child.kill()
                    self.child.communicate(timeout=5)
        elif self.child:
            self.child.communicate(timeout=5)
        if self.transport:
            self.transport.close()

    def deliveries(self, operation):
        with closing(sqlite3.connect(self.path, timeout=2)) as db:
            return db.execute(
                "SELECT stage,delivery_count FROM ingress_deliveries WHERE operation_id=? ORDER BY rowid",
                (operation,),
            ).fetchall()


@pytest.fixture
def independent_dss(tmp_path, request):
    mode = getattr(request.node, "callspec", None)
    params = mode.params if mode else {}
    child = DssProcess(
        tmp_path / "lifecycle-dss.sqlite",
        params.get("fault", "none"),
        params.get("stage", "RELEASE"),
    )
    try:
        yield child
    finally:
        child.close()


def record(**values):
    if root := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
        with (Path(root) / "dss-lifecycle.log").open("a") as trace:
            trace.write(
                json.dumps(dict(passed=True, historical_cause_established=False, **values)) + "\n"
            )


@pytest.mark.parametrize("fault", ["crash", "cut", "stall"])
@pytest.mark.parametrize("stage", STAGES)
def test_dss_post_commit_fault_and_restart_never_replay(driver_setup, pki, fault, stage):
    setup = driver_setup
    child, store, driver = setup["dss"], setup["store"], setup["driver"]
    original_epoch = child.get("state")["epoch"]
    original_pid = child.child.pid
    key = str(uuid.uuid4())
    started = time.monotonic()
    code, _ = native.native_call(
        setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
    )
    elapsed = time.monotonic() - started
    assert code in {500, 503} and elapsed < 5
    assert child.event() == dict(event="committed_before_ack", stage=stage, mode=fault)
    if fault == "crash":
        child.stop(expected=73)
    else:
        child.stop()
    # Reopen the same durable DB at the same endpoints. Endpoint availability
    # does not authorize retry of the original execution or request identity.
    child.start()
    assert child.child.pid != original_pid and child.get("state")["epoch"] == original_epoch
    position = STAGES.index(stage)
    expected = [(s, "ACKED") for s in STAGES[:position]] + [(stage, "UNCERTAIN")]
    for db in (store.db, driver.gate.db):
        assert [
            tuple(r) for r in db.execute("SELECT stage,state FROM effect_intents ORDER BY rowid")
        ] == expected
    assert child.deliveries(key) == [(s, 1) for s in STAGES[: position + 1]]
    executed = int(position >= 2)
    assert child.get("state")["core"]["commands_executed"] == executed
    row = store.db.execute(
        "SELECT control_state FROM executions WHERE id=?", (setup["grant"].execution_id,)
    ).fetchone()
    assert row[0] == "RECOVERY_REQUIRED"
    assert store.db.execute("SELECT state FROM native_driver_calls").fetchone()[0] == "UNCERTAIN"
    for retry_key in (key, str(uuid.uuid4())):
        assert native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=retry_key
        )[0] in {403, 409}
    assert child.deliveries(key) == [(s, 1) for s in STAGES[: position + 1]]
    assert child.get("state")["core"]["commands_executed"] == executed
    assert store.db.execute("SELECT COUNT(*) FROM native_driver_calls").fetchone()[0] == 1
    assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    record(
        case="post_commit_restart",
        fault=fault,
        stage=stage,
        elapsed_ms=round(elapsed * 1000),
        dss_pid_changed=True,
        epoch_preserved=True,
        ledger_states=expected,
        ingress_deliveries=[(s, 1) for s in STAGES[: position + 1]],
        external_commands=executed,
        old_and_new_key_denied=True,
        holds_retained=True,
        worker_mtls=True,
    )


def test_completed_call_survives_dss_restart_without_replay(driver_setup, pki):
    setup = driver_setup
    child, key = setup["dss"], str(uuid.uuid4())
    epoch, pid = child.get("state")["epoch"], child.child.pid
    assert (
        native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
        )[0]
        == 200
    )
    child.stop()
    child.start()
    assert child.child.pid != pid and child.get("state")["epoch"] == epoch
    assert (
        native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
        )[0]
        == 409
    )
    assert child.get("state")["core"]["commands_executed"] == 1
    new_key = str(uuid.uuid4())
    assert (
        native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=new_key
        )[0]
        == 200
    )
    assert child.get("state")["core"]["commands_executed"] == 2
    assert child.deliveries(key) == child.deliveries(new_key) == [(s, 1) for s in STAGES]
    record(
        case="completed_restart",
        dss_pid_changed=True,
        epoch_preserved=True,
        duplicate_denied=True,
        distinct_new_command_completed=True,
        external_commands=2,
        worker_mtls=True,
    )


def test_scenario_reset_cannot_implicitly_rebind_existing_driver(driver_setup, pki):
    setup = driver_setup
    child = setup["dss"]
    epoch = child.get("state")["epoch"]
    request = Request(
        child.url + "/api/v1/scenarios/reset",
        json.dumps(dict(scenario_id="explicit-lifecycle-reset", expected_epoch=epoch)).encode(),
        {"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=3) as response:
        assert response.status == 200
    assert child.get("state")["epoch"] != epoch
    keys = [str(uuid.uuid4()) for _ in range(2)]
    for key in keys:
        assert native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
        )[0] in {500, 503}
        assert (
            native.native_call(
                setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
            )[0]
            == 409
        )
        assert child.deliveries(key) == []
    for db in (setup["store"].db, setup["driver"].gate.db):
        assert db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0] == 0
    assert setup["driver"].transport.epoch == epoch
    assert child.get("state")["core"]["commands_executed"] == 0
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    record(
        case="scenario_reset",
        old_binding_retained=True,
        implicit_rebind_denied=True,
        binary_deliveries=0,
        external_commands=0,
        holds_retained=True,
        worker_mtls=True,
    )


@pytest.mark.parametrize("fault,stage", [("stall", "RELEASE")])
def test_one_uncertain_execution_does_not_block_nine_other_grants(
    authority, independent_dss, tmp_path, fault, stage
):
    child = independent_dss
    driver = effects.DriverGate(authority, tmp_path / "ten-driver", {"simulator": child.tc_address})
    try:
        operations = [effects.admission(driver, "procedure-" + str(n))[2] for n in range(10)]

        def send(bound):
            return child.transport.command(
                "CMD1",
                [],
                effects.identity(bound),
                bound.operation,
                lambda: authority.validate_start_grant(bound.grant),
                admission=bound,
                timeout=2,
            )

        with ThreadPoolExecutor(max_workers=10) as pool:
            uncertain = pool.submit(send, operations[0])
            assert child.event() == dict(event="committed_before_ack", stage=stage, mode=fault)
            started = time.monotonic()
            peers = list(pool.map(send, operations[1:]))
            duration = time.monotonic() - started
            assert all(ok and len(receipts) == 5 for ok, receipts in peers) and duration < 2
            with pytest.raises(UncertainEffect):
                uncertain.result(timeout=3)
        for bound in (operations[0], replace(operations[0], operation=str(uuid.uuid4()))):
            with pytest.raises(Fault):
                send(bound)
        rows = authority.list_executions("alice")["executions"]
        assert sum(r["control_state"] == "RECOVERY_REQUIRED" for r in rows) == 1
        for bound in operations[1:]:
            authority.validate_start_grant(bound.grant)
            assert child.deliveries(bound.operation) == [(s, 1) for s in STAGES]
        assert child.deliveries(operations[0].operation) == [(s, 1) for s in STAGES[:3]]
        assert child.get("state")["core"]["commands_executed"] == 10
        assert authority.store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 10
        assert authority.store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 10
        record(
            case="ten_independent_executions",
            uncertain=1,
            completed=9,
            peer_elapsed_ms=round(duration * 1000),
            external_commands=10,
            holds_retained=10,
            original_grants_preserved=True,
            admission_scope="direct real authority/driver gate; no worker mTLS or native identity claim",
        )
    finally:
        driver.close()
