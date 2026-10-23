"""Real mTLS/native-protobuf fencing; main status never proves family pause."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import sys
import time
import types
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.contracts import Fault, policy
from openbexi_spell_server.pause import NativePauseBarrier
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.transport import Route
from test_launch import call
import test_native_driver as native
import test_preflight as helpers

driver_setup = native.driver_setup
independent_dss = native.independent_dss


@pytest.fixture
def pause_setup(driver_setup):
    setup = driver_setup
    setup["pause"] = NativePauseBarrier(setup["app"].authority)
    yield setup


def accept(setup, *, key=None):
    bob = setup["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = setup["controller"](
        "execution.claim",
        dict(execution_id=setup["execution"]["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    payload = dict(
        **helpers.proof(setup["execution"]), claim_id=claim["claim_id"], decision="accept"
    )
    decision = setup["controller"]("execution.decide", payload, key=key)
    return decision, payload


def diagnostic(barrier_id, **updates):
    result = dict(
        barrier_id=barrier_id,
        provider="legacy-status-only/1",
        native_status="PAUSED",
        quiescence_proven=False,
        reason="thread_child_queue_proof_unavailable",
    )
    return dict(result, **updates)


def state(setup):
    return setup["app"].authority.list_executions("alice")["executions"][0]


def assert_retained(setup):
    row = state(setup)
    assert row["owner"] == "alice" and row["epoch"] == 1
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_accept_fences_before_worker_poll_and_paused_status_never_transfers(pause_setup, pki):
    setup = pause_setup
    decision, _ = accept(setup)
    assert decision["state"] == "PAUSING" and decision["effective_transfer"] is False
    assert state(setup)["control_state"] == "PAUSING"
    assert call(setup, pki, setup["grant"], "check")[0] == 403
    assert (
        native.native_call(setup, pki, native.PREFIX + "TC/SendCommand", native.command())[0] == 403
    )
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0
    code, reply = call(setup, pki, setup["grant"], "pause-poll")
    assert code == 200 and reply["result"]["action"] == "pause"
    report = diagnostic(decision["barrier_id"])
    code, reply = call(setup, pki, setup["grant"], "pause-report", **report)
    assert code == 200
    assert reply["result"]["state"] == "UNPROVEN"
    assert reply["result"]["effective_transfer"] is False
    assert state(setup)["control_state"] == "RECOVERY_REQUIRED"
    assert state(setup)["pause_barrier"]["report"]["native_status"] == "PAUSED"
    assert call(setup, pki, setup["grant"], "pause-poll")[1]["result"]["action"] == "hold"
    assert_retained(setup)


@pytest.mark.parametrize(
    "updates",
    [
        {"quiescence_proven": True},
        {"quiescence_proven": 0},
        {"native_status": {}},
        {"native_status": "QUIESCED"},
        {"provider": "whole-family/1"},
        {"provider": []},
        {"reason": None},
    ],
)
def test_worker_cannot_assert_an_unqualified_family_proof(pause_setup, pki, updates):
    setup = pause_setup
    decision, _ = accept(setup)
    assert (
        call(
            setup,
            pki,
            setup["grant"],
            "pause-report",
            **diagnostic(decision["barrier_id"], **updates),
        )[0]
        == 403
    )
    assert state(setup)["pause_barrier"]["state"] == "REQUESTED"
    assert_retained(setup)


@pytest.mark.parametrize("action", ["pause-poll", "pause-report"])
def test_original_config_without_consumption_winner_proof_has_no_pause_route_authority(
    pause_setup, pki, action
):
    setup = pause_setup
    decision, _ = accept(setup)
    extras = diagnostic(decision["barrier_id"]) if action == "pause-report" else {}
    assert call(setup, pki, setup["grant"], action, runtime_capability="0" * 64, **extras)[0] == 403
    assert call(setup, pki, setup["grant"], action, certificate="alice", **extras)[0] == 403
    assert call(setup, pki, replace(setup["grant"], control_epoch=2), action, **extras)[0] == 403
    assert_retained(setup)


def test_fenced_worker_can_report_safety_after_controller_role_revocation(pause_setup, pki):
    setup = pause_setup
    decision, _ = accept(setup)
    setup["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert call(setup, pki, setup["grant"], "pause-poll")[0] == 200
    assert call(setup, pki, setup["grant"], "check")[0] == 403
    assert (
        call(setup, pki, setup["grant"], "pause-report", **diagnostic(decision["barrier_id"]))[0]
        == 200
    )
    assert_retained(setup)


def test_dead_worker_expires_without_waiting_or_transferring(pause_setup):
    setup = pause_setup
    clock = [1000.0]
    setup["app"].authority.clock = lambda: clock[0]
    decision, _ = accept(setup)
    assert decision["deadline"] == 1010
    clock[0] = 1010.1
    started = time.monotonic()
    assert state(setup)["pause_barrier"]["state"] == "EXPIRED"
    assert time.monotonic() - started < 0.25
    assert state(setup)["control_state"] == "RECOVERY_REQUIRED"
    assert_retained(setup)


def test_late_pause_report_records_evidence_without_extending_deadline(pause_setup, pki):
    setup = pause_setup
    clock = [1000.0]
    setup["app"].authority.clock = lambda: clock[0]
    decision, _ = accept(setup)
    clock[0] = 1011
    code, answer = call(
        setup, pki, setup["grant"], "pause-report", **diagnostic(decision["barrier_id"])
    )
    assert code == 200 and answer["result"]["state"] == "EXPIRED"
    assert answer["result"]["deadline"] == 1010
    assert_retained(setup)


def test_duplicate_accepts_and_lost_diagnostic_response_never_repeat_transition(pause_setup, pki):
    setup = pause_setup
    key = str(uuid.uuid4())
    first, payload = accept(setup, key=key)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: setup["controller"]("execution.decide", payload, key=key), range(20))
        )
    assert all(result["barrier_id"] == first["barrier_id"] for result in results)
    assert (
        setup["store"].db.execute("SELECT COUNT(*) FROM native_pause_barriers").fetchone()[0] == 1
    )
    report = diagnostic(first["barrier_id"])
    assert call(setup, pki, setup["grant"], "pause-report", **report)[0] == 200
    count = setup["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert call(setup, pki, setup["grant"], "pause-report", **report)[0] == 200
    assert setup["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == count
    assert (
        call(setup, pki, setup["grant"], "pause-report", **dict(report, native_status="UNKNOWN"))[0]
        == 409
    )
    assert_retained(setup)


def test_pause_accept_audit_failure_rolls_back_fence_and_preserves_owner(pause_setup, pki):
    setup = pause_setup
    bob = setup["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = setup["controller"](
        "execution.claim",
        dict(execution_id=setup["execution"]["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    authority, store = setup["app"].authority, setup["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    with pytest.raises(Fault) as denied:
        authority.mutate(
            "alice",
            "execution.decide",
            str(uuid.uuid4()),
            dict(
                **helpers.proof(setup["execution"]), claim_id=claim["claim_id"], decision="accept"
            ),
        )
    assert denied.value.status == 503
    assert state(setup)["control_state"] == "OWNED"
    assert store.db.execute("SELECT COUNT(*) FROM native_pause_barriers").fetchone()[0] == 0
    assert call(setup, pki, setup["grant"], "check")[0] == 200
    assert_retained(setup)


def test_diagnostic_audit_failure_does_not_acknowledge_pause(pause_setup, pki):
    setup = pause_setup
    decision, _ = accept(setup)
    store = setup["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert (
        call(setup, pki, setup["grant"], "pause-report", **diagnostic(decision["barrier_id"]))[0]
        == 503
    )
    assert state(setup)["pause_barrier"]["state"] == "REQUESTED"
    assert state(setup)["pause_barrier"]["report"] is None
    assert call(setup, pki, setup["grant"], "check")[0] == 403
    assert_retained(setup)


def test_barrier_between_real_tc_stages_allows_receipt_but_no_next_write(pause_setup, pki):
    setup = pause_setup
    gate = setup["driver"].gate
    settle = gate.settle
    decisions = []

    def request_pause_after_receipt(original, operation, stage, receipt):
        settle(original, operation, stage, receipt)
        if stage == "TRANSPORT":
            decisions.append(accept(setup)[0])

    gate.settle = request_pause_after_receipt
    assert (
        native.native_call(setup, pki, native.PREFIX + "TC/SendCommand", native.command())[0] == 500
    )
    assert decisions[0]["state"] == "PAUSING"
    assert [r[0] for r in gate.db.execute("SELECT state FROM effect_intents")] == ["ACKED"]
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0
    assert_retained(setup)


def test_real_client_pause_routes_and_secret_redaction(pause_setup, pki):
    setup = pause_setup
    route = Route(
        f"https://localhost:{setup['server'].server_port}",
        pki["context-a"]["pin"],
        pki["worker"]["client"],
    )
    body = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(setup["grant"]),
        runtime_capability=setup["runtime_capabilities"][setup["grant"].execution_id],
    )
    assert (
        route.call(body, path="/v1/worker/pause-poll", schema="openbexi.worker/2")["action"]
        == "none"
    )
    decision, _ = accept(setup)
    reply = route.call(
        {**body, **diagnostic(decision["barrier_id"])},
        path="/v1/worker/pause-report",
        schema="openbexi.worker/2",
    )
    assert reply["state"] == "UNPROVEN"
    dump = "\n".join(setup["store"].db.iterdump())
    assert setup["grant"].token not in dump and body["runtime_capability"] not in dump
    assert setup["store"].db.execute("PRAGMA user_version").fetchone()[0] == 9


def test_authority_restart_fences_pending_pause_and_original_grant(pause_setup):
    setup = pause_setup
    accept(setup)
    directory = Path(setup["store"].db.execute("PRAGMA database_list").fetchone()[2]).parent
    setup["app"].close()
    setup["store"].close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(
            store, setup["app"].subjects, worker_slots={"one": "worker-1", "two": "worker-2"}
        )
        pause = NativePauseBarrier(authority)
        assert pause.snapshot(setup["grant"].execution_id)["state"] == "RESTART_FENCED"
        with pytest.raises(Fault):
            authority._original_grant(setup["grant"])
        row = authority.list_executions("alice")["executions"][0]
        assert row["owner"] == "alice" and row["control_state"] == "RECOVERY_REQUIRED"
        assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        store.close()


def test_pause_routes_remain_absent_without_explicit_profile(driver_setup, pki):
    assert call(driver_setup, pki, driver_setup["grant"], "pause-poll")[0] == 404
    assert (
        call(
            driver_setup,
            pki,
            driver_setup["grant"],
            "pause-report",
            **diagnostic(str(uuid.uuid4())),
        )[0]
        == 404
    )


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setitem(sys.modules, "native", types.SimpleNamespace(NativeSession=object))
    path = Path(__file__).resolve().parents[2] / "host_runtime/python/v08_worker.py"
    spec = importlib.util.spec_from_file_location("native_pause_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status", ["PAUSED", "PROMPT", "WAITING", "FINISHED"])
def test_non_running_status_never_synthesizes_native_family_quiescence(agent, status):
    class Forbidden:
        def request(self, *args, **kwargs):
            raise AssertionError("No interrupt/resume/kill is authorized for an unqualified state")

    result = agent.native_pause_probe(Forbidden(), lambda: None, status)
    assert result["native_status"] == status and result["quiescence_proven"] is False


def test_real_pause_observation_is_still_explicitly_unproven(agent):
    class Session:
        def __init__(self):
            self.calls = []

        def request(self, name, **options):
            self.calls.append(name)
            return {"ExecutorStatus": "PAUSED"}

    session = Session()
    result = agent.native_pause_probe(session, lambda: None, "RUNNING")
    assert session.calls == ["CMD_PAUSE", "REQ_EXEC_INFO"]
    assert result["native_status"] == "PAUSED" and result["quiescence_proven"] is False


def test_lost_pause_report_reply_cannot_repeat_native_command(agent):
    class Forbidden:
        def request(self, *args, **kwargs):
            raise AssertionError("A lost diagnostic reply repeated the admitted native pause")

    prior = diagnostic(str(uuid.uuid4()))
    result = agent.native_pause_probe(Forbidden(), lambda: None, "RUNNING", prior=prior)
    assert result is prior and result["quiescence_proven"] is False
