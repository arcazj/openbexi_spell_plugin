"""Controlled delays through real mTLS, two ledgers and an independent DSS PID.

These reproduce failure signatures under declared faults, not historical causes.
The command's existing two-second option and no-replay policy remain unchanged.
"""

import json
import os
from pathlib import Path
import threading
import time
import uuid
from urllib.request import Request, urlopen

import pytest

import test_native_driver as native
from test_effects import dss as dss_fixture

driver_setup = native.driver_setup


@pytest.fixture
def independent_dss(tmp_path, fault):
    for dss in dss_fixture.__wrapped__(tmp_path):
        faults = {
            "receipt_delay": {"command_delay_ms": 2400},
            "receipt_drop": {"lost_ack": True},
        }.get(fault, {})
        if faults:
            state = dss.get("state")
            request = Request(
                dss.url + "/api/v1/scenarios/reset",
                json.dumps(
                    dict(
                        scenario_id="fault-reproduction",
                        expected_epoch=state["epoch"],
                        faults=faults,
                    )
                ).encode(),
                {"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=3) as response:
                assert response.status == 200
        # ContextDriver is constructed only after the explicit scenario reset.
        yield dss


@pytest.mark.parametrize(
    "fault", ["ledger_queue", "ledger_commit", "receipt_delay", "receipt_drop"]
)
def test_declared_fault_retains_receipts_holds_and_never_replays(
    driver_setup, pki, monkeypatch, fault
):
    setup = driver_setup
    gate, store = setup["driver"].gate, setup["store"]
    original_send = gate.send
    deadline = None
    attempted_stages, holders = [], []
    injected = threading.Event()
    commit_armed = False

    def hold_writer(until, ready):
        with gate.lock:
            ready.set()
            threading.Event().wait(max(0, until - time.monotonic()) + 0.2)

    def send(grant, binding, operation, stage, connection, packet, **options):
        nonlocal deadline
        deadline = options["deadline"]
        attempted_stages.append(stage)
        if fault == "ledger_queue" and stage == "RELEASE":
            ready = threading.Event()
            holder = threading.Thread(target=hold_writer, args=(deadline, ready))
            holders.append(holder)
            holder.start()
            assert ready.wait(1), "Writer barrier was not reached"
            injected.set()
        return original_send(grant, binding, operation, stage, connection, packet, **options)

    def delay_commit(statement):
        nonlocal commit_armed
        if (
            fault == "ledger_commit"
            and not injected.is_set()
            and "UPDATE effect_intents SET state='ACKED'" in statement
            and "stage='LOADING'" in statement
        ):
            commit_armed = True
        if commit_armed and statement == "COMMIT" and not injected.is_set():
            # Stop inside the actual driver ledger transaction, while settlement
            # is timed. No synthetic receipt, state update or weakened fsync.
            injected.set()
            threading.Event().wait(max(0, deadline - time.monotonic()) + 0.2)

    monkeypatch.setattr(gate, "send", send)
    gate.db.set_trace_callback(delay_commit)
    key = str(uuid.uuid4())
    started = time.monotonic()
    try:
        code, _reply = native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=key
        )
    finally:
        for holder in holders:
            holder.join(4)
            assert not holder.is_alive()
        gate.db.set_trace_callback(None)
    elapsed = time.monotonic() - started
    assert code in {500, 503}
    assert elapsed < 5, "Fault exceeded the existing RPC bound"
    if fault.startswith("ledger"):
        assert injected.is_set() and elapsed >= 2
    expected = [("TRANSPORT", "ACKED"), ("LOADING", "ACKED")]
    if fault.startswith("receipt"):
        expected.append(("RELEASE", "UNCERTAIN"))
    for db in (store.db, gate.db):
        actual = [
            tuple(row)
            for row in db.execute("SELECT stage,state FROM effect_intents ORDER BY rowid")
        ]
        assert actual == expected
    assert store.db.execute("SELECT state FROM native_driver_calls").fetchall()[0][0] == "UNCERTAIN"
    execution = store.db.execute(
        "SELECT control_state FROM executions WHERE id=?", (setup["grant"].execution_id,)
    ).fetchone()
    assert execution[0] == "RECOVERY_REQUIRED"
    event = json.loads(
        store.db.execute(
            "SELECT body FROM events WHERE type='NATIVE_DRIVER_CALL_FAILED'"
        ).fetchone()[0]
    )
    timing = event["error_chain"][0]["command_timing"]
    steps = timing["steps"]
    if fault == "ledger_queue":
        assert steps[-1]["phase"] == "send" and steps[-1]["stage"] == "RELEASE"
        assert steps[-1]["failed"] and steps[-1]["elapsed_ms"] >= 1000
    elif fault == "ledger_commit":
        assert any(
            s["phase"] == "settle" and s["stage"] == "LOADING" and s["elapsed_ms"] >= 1000
            for s in steps
        )
        assert steps[-1]["stage"] == "RELEASE" and steps[-1]["failed"]
    else:
        assert steps[-1]["phase"] == "receipt" and steps[-1]["stage"] == "RELEASE"
        assert steps[-1]["failed"]
        if fault == "receipt_delay":
            assert steps[-1]["elapsed_ms"] >= 1000
    executed = setup["dss"].get("state")["core"]["commands_executed"]
    assert executed == int(fault.startswith("receipt"))
    attempts = list(attempted_stages)
    for retry_key in (key, str(uuid.uuid4())):
        assert native.native_call(
            setup, pki, native.PREFIX + "TC/SendCommand", native.command(2), key=retry_key
        )[0] in {403, 409}
    assert attempted_stages == attempts
    assert setup["dss"].get("state")["core"]["commands_executed"] == executed
    assert store.db.execute("SELECT COUNT(*) FROM native_driver_calls").fetchone()[0] == 1
    assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    evidence = os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR")
    if evidence:
        with (Path(evidence) / "reliability-faults.jsonl").open("a") as trace:
            trace.write(
                json.dumps(
                    dict(
                        fault=fault,
                        passed=True,
                        elapsed_ms=round(elapsed * 1000),
                        command_timing=timing,
                        ledger_states=expected,
                        external_commands_executed=executed,
                        replay_denied=True,
                        holds_retained=True,
                        historical_cause_established=False,
                    )
                )
                + "\n"
            )
