"""Native reconnection preserves owner/epoch and requires independent host proof."""

from dataclasses import asdict
import json
import uuid

import pytest

from openbexi_spell_server.contracts import Actor, Fault, envelope
from test_services import request
from test_launch import call
import test_live_handoff as live
import test_owner_commands as owners
import test_preflight as helpers
import test_repeated_handoff as repeated
import test_terminal_settlement as terminal

source, setup, ledger, dss = live.source, live.setup, live.ledger, terminal.dss


def rpc(ledger, pki, method, body, *, subject="alice", key=None):
    return request(
        ledger["server"],
        pki["listener"]["client"],
        "/v1/rpc",
        subject=None,
        payload=envelope("A", subject, method, body, key or str(uuid.uuid4())),
    )


def prepare(ledger, pki, *, subject="alice"):
    controller = ledger["controller"]
    connection = controller("session.open", {}, subject=subject)["connection_id"]
    body = dict(
        execution_id=ledger["grant"].execution_id,
        connection_id=connection,
        expected_epoch=ledger["grant"].control_epoch,
    )
    key = str(uuid.uuid4())
    pending = controller("execution.rebind", body, subject=subject, key=key)
    assert pending["rebind_pending"] and "capability" not in pending
    assert pending["control_state"] == "PAUSING" and not pending["effective_transfer"]
    assert controller("execution.rebind", body, subject=subject, key=key) == dict(
        pending, replayed=True
    )
    state = live.host(ledger, pki, "status")
    assert state["operation"] == "rebind" and not state["effective_transfer"]
    assert "claim_id" not in state
    return body, state, live.evidence(ledger, state)


def resumed(ledger, pki, *, subject="alice"):
    body, state, evidence = prepare(ledger, pki, subject=subject)
    completed = live.host(
        ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=evidence
    )
    assert completed["connection_rebound"] and completed["quiescence_proven"]
    assert not completed["effective_transfer"]
    assert (
        live.host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=evidence)
        == completed
    )
    bound = ledger["controller"]("execution.rebind", body, subject=subject)
    status, answer = owners.enqueue(
        ledger,
        pki,
        "CMD_RUN",
        subject=subject,
        body=dict(helpers.proof(bound), target_admission_id=None, command="CMD_RUN"),
    )
    assert status == 200, answer
    permission = live.host(
        ledger,
        pki,
        "resume",
        barrier_id=state["barrier_id"],
        resume_id=answer["result"]["command_id"],
        evidence=evidence,
    )
    return state, evidence, bound, permission["runtime_epoch"]


@pytest.mark.parametrize("disconnect", [False, True])
def test_same_owner_rebind_keeps_epoch_rotates_generation_and_fences_old_requests(
    ledger, pki, disconnect
):
    old = ledger["grant"]
    old_capability = ledger["runtime_capabilities"][old.execution_id]
    original = ledger["app"].settlement._roster(old.execution_id)
    if disconnect:
        ledger["controller"]("session.close", dict(connection_id=old.connection_id))
        assert live.observe(ledger, pki)["control_state"] == "CONTROLLER_DISCONNECTED"
        assert call(ledger, pki, old, "check")[0] == 403
    _, _, bound, epoch = resumed(ledger, pki)
    view = live.observe(ledger, pki)
    assert (view["owner"], view["epoch"], view["connection_generation"]) == ("alice", 1, 2)
    assert view["control_state"] == "HANDOFF_PAUSED"
    assert owners.enqueue(ledger, pki)[0] == 403
    result = live.activate(ledger, pki, epoch)
    assert result["activation_kind"] == "rebind"
    repeated.remember(ledger, result)
    assert ledger["grant"].control_epoch == old.control_epoch
    assert ledger["grant"].connection_generation == old.connection_generation + 1
    assert ledger["grant"].connection_id == bound["connection_id"] != old.connection_id
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200
    assert call(ledger, pki, old, "check", runtime_capability=old_capability)[0] == 403
    assert ledger["app"].settlement._roster(old.execution_id) == original
    if not disconnect:
        ledger["controller"]("session.close", dict(connection_id=old.connection_id))
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200
    assert terminal.held(ledger) == 1
    assert ledger["store"].db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
    assert ledger["store"].db.execute("PRAGMA user_version").fetchone()[0] == 21


def test_rebind_after_transfer_preserves_original_family_and_later_transfer(ledger, pki, tmp_path):
    worker, path = live.runtime(ledger, pki, tmp_path)
    origin = worker.origin
    _, _, b, first = live.resumed(ledger, pki)
    path.write_text(first)
    worker.ensure(first, native=True)
    repeated.remember(ledger, worker.request)
    ledger["controller"]("session.close", dict(connection_id=b["connection_id"]), subject="bob")
    _, _, rebound, second = resumed(ledger, pki, subject="bob")
    path.write_text(second)
    with pytest.raises(ValueError, match="Original native operation epoch"):
        worker.ensure(first, native=True)
    worker.ensure(second, native=True)
    repeated.remember(ledger, worker.request)
    assert worker.request["grant"]["control_epoch"] == 2
    assert worker.request["grant"]["connection_generation"] == 3
    _, _, _, third = repeated.next_resume(ledger, pki, rebound, "bob", "alice")
    path.write_text(third)
    worker.ensure(third, native=True)
    repeated.remember(ledger, worker.request)
    assert worker.request["grant"]["control_epoch"] == 3
    assert worker.request["grant"]["connection_generation"] == 4
    assert worker.origin == origin and worker.rotations == 3
    history = (
        ledger["store"]
        .db.execute("SELECT handoff FROM live_handoff_history ORDER BY rowid")
        .fetchall()
    )
    assert [json.loads(h[0])["kind"] for h in history] == ["transfer", "rebind"]
    fence = terminal.begin(ledger, pki, "FINISHED")
    status, settled = terminal.complete(ledger, pki, fence)
    assert status == 200 and settled["result"]["state"] == "SETTLED"
    assert terminal.release(ledger, pki, settled["result"])[0] == 200


@pytest.mark.parametrize(
    "invalid", ["foreign_owner", "old_epoch", "same_connection", "role_revoked"]
)
def test_rebind_admission_does_not_change_authority_on_invalid_request(ledger, pki, invalid):
    controller = ledger["controller"]
    subject = "bob" if invalid == "foreign_owner" else "alice"
    connection = controller("session.open", {}, subject=subject)["connection_id"]
    body = dict(
        execution_id=ledger["grant"].execution_id, connection_id=connection, expected_epoch=1
    )
    if invalid == "old_epoch":
        body["expected_epoch"] = 2
    if invalid == "same_connection":
        body["connection_id"] = ledger["connection"]
    if invalid == "role_revoked":
        permissions = ledger["app"].subjects["alice"].permissions - {"execution:start"}
        ledger["app"].subjects["alice"] = Actor("alice", permissions)
    status, _ = rpc(ledger, pki, "execution.rebind", body, subject=subject)
    assert status in {403, 409}
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
    assert ledger["store"].db.execute("SELECT COUNT(*) FROM native_rebindings").fetchone()[0] == 0


@pytest.mark.parametrize(
    "failure", ["target_closed", "expired", "false_freeze", "wrong_host", "role_revoked"]
)
def test_rebind_requires_live_target_and_real_host_barrier_at_completion(ledger, pki, failure):
    body, state, evidence = prepare(ledger, pki)
    if failure == "target_closed":
        ledger["controller"]("session.close", dict(connection_id=body["connection_id"]))
    elif failure == "expired":
        ledger["app"].authority.clock = lambda: state["deadline"] + 1
    elif failure == "false_freeze":
        evidence["frozen"] = False
    elif failure == "role_revoked":
        ledger["app"].subjects["alice"] = Actor(
            "alice", frozenset({"execution:read", "context:read"})
        )
    with pytest.raises(Fault):
        live.host(
            ledger,
            pki,
            "complete",
            barrier_id=state["barrier_id"],
            evidence=evidence,
            certificate="worker" if failure == "wrong_host" else "host",
        )
    view = live.observe(ledger, pki)
    assert (view["owner"], view["epoch"], view["connection_generation"]) == ("alice", 1, 1)
    assert view["control_state"] in {"PAUSING", "RECOVERY_REQUIRED"}
    assert terminal.held(ledger) == 1


def test_rebind_lost_activation_cannot_retry_or_restore_old_proof(ledger, pki, tmp_path):
    worker, path = live.runtime(ledger, pki, tmp_path)
    _, _, _, epoch = resumed(ledger, pki)
    path.write_text(epoch)
    original = worker.route.call
    calls = []

    def lose(*args, **kwargs):
        calls.append(1)
        original(*args, **kwargs)
        raise TimeoutError("Lost rebind activation")

    worker.route.call = lose
    with pytest.raises(TimeoutError):
        worker.ensure()
    with pytest.raises(ValueError, match="uncertain"):
        worker.ensure()
    assert calls == [1] and worker.failed
    assert worker.request["grant"] == asdict(ledger["grant"])
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert terminal.held(ledger) == 1


def test_failed_rebind_rolls_back_history_request_and_fencing(ledger, pki):
    _, _, _, epoch = live.resumed(ledger, pki)
    repeated.remember(ledger, live.activate(ledger, pki, epoch))
    connection = ledger["controller"]("session.open", {}, subject="bob")["connection_id"]
    store = ledger["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    status, _ = rpc(
        ledger,
        pki,
        "execution.rebind",
        dict(execution_id=ledger["grant"].execution_id, connection_id=connection, expected_epoch=2),
        subject="bob",
    )
    assert status == 503
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
    assert store.db.execute("SELECT COUNT(*) FROM native_rebindings").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM live_handoff_history").fetchone()[0] == 0


def test_eight_reconnections_keep_epoch_and_deny_ninth_before_revoking_owner(ledger, pki):
    original = ledger["app"].settlement._roster(ledger["grant"].execution_id)
    for index in range(8):
        _, _, _, epoch = resumed(ledger, pki)
        repeated.remember(ledger, live.activate(ledger, pki, epoch))
        assert ledger["grant"].control_epoch == 1
        assert ledger["grant"].connection_generation == index + 2
        assert ledger["app"].settlement._roster(ledger["grant"].execution_id) == original
    with pytest.raises(AssertionError, match="handoff_transfer_capacity_reached"):
        prepare(ledger, pki)
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200
    assert ledger["store"].db.execute("SELECT COUNT(*) FROM native_rebindings").fetchone()[0] == 8


@pytest.mark.parametrize(
    "wrong", ["activation_kind", "control_epoch", "connection_generation", "connection_id"]
)
def test_worker_rejects_inconsistent_rebind_activation_without_retry(ledger, pki, tmp_path, wrong):
    worker, path = live.runtime(ledger, pki, tmp_path)
    _, _, _, epoch = resumed(ledger, pki)
    path.write_text(epoch)
    original = worker.route.call
    calls = []

    def altered(*args, **kwargs):
        calls.append(1)
        result = original(*args, **kwargs)
        if wrong == "activation_kind":
            result[wrong] = "transfer"
        elif wrong == "connection_id":
            result["grant"][wrong] = worker.request["grant"][wrong]
        else:
            result["grant"][wrong] += 1
        return result

    worker.route.call = altered
    with pytest.raises(ValueError, match="Rotated runtime receipt differs"):
        worker.ensure()
    with pytest.raises(ValueError, match="uncertain"):
        worker.ensure()
    assert calls == [1] and worker.failed
    assert terminal.held(ledger) == 1


@pytest.mark.parametrize("source", ["simulator"], indirect=True)
@pytest.mark.parametrize("uncertain", [False, True])
def test_same_epoch_rebind_fences_actual_send_and_requires_independent_settlement(
    ledger, pki, dss, tmp_path, uncertain
):
    from openbexi_spell_server.effects import DriverGate, EffectAdmission

    gate = DriverGate(ledger["app"].authority, tmp_path / "driver", {"simulator": dss.tc_address})
    ledger["store"].db.execute("CREATE TABLE native_driver_calls(execution_id TEXT,state TEXT)")
    try:
        old = ledger["grant"]
        ok, receipts = terminal.effects.command(
            dss, EffectAdmission(gate, old, "simulator", str(uuid.uuid4()))
        )
        assert ok and len(receipts) == 5
        if uncertain:
            for db in (gate.db, ledger["store"].db):
                db.execute("UPDATE effect_intents SET state='UNCERTAIN' WHERE stage='RELEASE'")
            with pytest.raises(AssertionError, match="handoff_effects_unresolved"):
                prepare(ledger, pki)
            assert live.observe(ledger, pki)["control_state"] == "OWNED"
        else:
            _, _, _, epoch = resumed(ledger, pki)
            repeated.remember(ledger, live.activate(ledger, pki, epoch))
            with pytest.raises(Fault):
                terminal.effects.command(
                    dss, EffectAdmission(gate, old, "simulator", str(uuid.uuid4()))
                )
            ok, receipts = terminal.effects.command(
                dss, EffectAdmission(gate, ledger["grant"], "simulator", str(uuid.uuid4()))
            )
            assert ok and len(receipts) == 5
            rows = (
                ledger["store"].db.execute("SELECT provenance,state FROM effect_intents").fetchall()
            )
            assert len(rows) == 10 and all(r["state"] == "ACKED" for r in rows)
            assert {json.loads(r["provenance"])["control_epoch"] for r in rows} == {1}
            assert {json.loads(r["provenance"])["connection_generation"] for r in rows} == {1, 2}
            assert dss.get("state")["core"]["commands_executed"] == 2
        assert terminal.held(ledger) == 1
    finally:
        gate.close()
