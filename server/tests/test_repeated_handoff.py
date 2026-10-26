"""Each transfer needs new host proof; prior identities and receipts stay fenced."""

import json
import uuid

import pytest

from openbexi_spell_server.contracts import Fault
from openbexi_spell_server.launch import start_grant
import test_live_handoff as live
import test_owner_commands as owners
import test_preflight as helpers
import test_terminal_settlement as terminal
from test_launch import call

source, setup, ledger = live.source, live.setup, live.ledger


def next_resume(ledger, pki, bound, former, target):
    controller = ledger["controller"]
    connection = controller("session.open", {}, subject=target)["connection_id"]
    eid, epoch = ledger["grant"].execution_id, ledger["grant"].control_epoch
    claim = controller(
        "execution.claim",
        dict(
            execution_id=eid,
            connection_id=connection,
            expected_epoch=epoch,
        ),
        subject=target,
    )
    accepted = controller(
        "execution.decide",
        dict(
            helpers.proof(bound),
            claim_id=claim["claim_id"],
            decision="accept",
        ),
        subject=former,
    )
    state = live.host(ledger, pki, "status")
    assert state["barrier_id"] == accepted["barrier_id"]
    evidence = live.evidence(ledger, state)
    live.host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=evidence)
    new_bound = controller(
        "execution.rebind",
        dict(
            execution_id=eid,
            connection_id=connection,
            expected_epoch=epoch + 1,
        ),
        subject=target,
    )
    status, answer = owners.enqueue(
        ledger,
        pki,
        "CMD_RUN",
        subject=target,
        body=dict(helpers.proof(new_bound), target_admission_id=None, command="CMD_RUN"),
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
    return state, evidence, new_bound, permission["runtime_epoch"]


def remember(ledger, result):
    ledger["grant"] = start_grant(result["grant"])
    ledger["runtime_capabilities"][ledger["grant"].execution_id] = result["runtime_capability"]


def test_eight_transfers_keep_original_family_history_and_fence_every_old_epoch(ledger, pki):
    original_roster = ledger["app"].settlement._roster(ledger["grant"].execution_id)
    old_grants, host_proofs = [], []
    state, proof, bound, epoch = live.resumed(ledger, pki)
    subject = "bob"
    for round_number in range(1, 9):
        old_grants.append(
            (ledger["grant"], ledger["runtime_capabilities"][ledger["grant"].execution_id])
        )
        remember(ledger, live.activate(ledger, pki, epoch))
        host_proofs.append((state, proof))
        assert live.observe(ledger, pki)["epoch"] == round_number + 1
        assert ledger["app"].settlement._roster(ledger["grant"].execution_id) == original_roster
        for grant, capability in old_grants:
            assert call(ledger, pki, grant, "check", runtime_capability=capability)[0] == 403
        for old_state, old_proof in host_proofs[:-1]:
            with pytest.raises(Fault):
                live.host(
                    ledger, pki, "complete", barrier_id=old_state["barrier_id"], evidence=old_proof
                )
        if round_number < 8:
            target = "alice" if subject == "bob" else "bob"
            state, proof, bound, epoch = next_resume(ledger, pki, bound, subject, target)
            subject = target
    history = (
        ledger["store"].db.execute("SELECT * FROM live_handoff_history ORDER BY rowid").fetchall()
    )
    assert len(history) == 7
    assert len({json.loads(row["handoff"])["origin_hash"] for row in history}) == 1
    assert all(json.loads(row["handoff"])["state"] == "ACTIVE" for row in history)
    assert all(grant.token not in repr([dict(r) for r in history]) for grant, _ in old_grants)
    target = "alice" if subject == "bob" else "bob"
    with pytest.raises(AssertionError, match="handoff_transfer_capacity_reached"):
        next_resume(ledger, pki, bound, subject, target)
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200
    fence = terminal.begin(ledger, pki, "FINISHED")
    status, result = terminal.complete(ledger, pki, fence)
    assert status == 200 and result["result"]["state"] == "SETTLED", result
    assert terminal.release(ledger, pki, result["result"])[0] == 200
    assert terminal.held(ledger) == 0
    assert (
        ledger["store"].db.execute("SELECT COUNT(*) FROM live_handoff_history").fetchone()[0] == 7
    )


@pytest.mark.parametrize("failure", ["reply_lost", "marker_replay"])
def test_second_worker_rotation_never_retries_or_recovers_from_uncertain_delivery(
    ledger, pki, tmp_path, failure
):
    worker, path = live.runtime(ledger, pki, tmp_path)
    initial = worker.epoch
    _, _, bound, epoch = live.resumed(ledger, pki)
    path.write_text(epoch)
    worker.ensure(epoch, native=True)
    remember(ledger, worker.request)
    _, _, _, second = next_resume(ledger, pki, bound, "bob", "alice")
    calls = []
    original = worker.route.call

    def lost(*args, **kwargs):
        calls.append(1)
        original(*args, **kwargs)
        raise TimeoutError("Lost second activation reply")

    worker.route.call = lost
    path.write_text(second if failure == "reply_lost" else initial)
    with pytest.raises((TimeoutError, ValueError)):
        worker.ensure()
    with pytest.raises(ValueError, match="uncertain"):
        worker.ensure()
    assert len(calls) == (1 if failure == "reply_lost" else 0)
    assert worker.failed and worker.rotations == 1
    assert worker.request["grant"]["control_epoch"] == 2
    assert terminal.held(ledger) == 1


def test_repeated_runtime_rotation_preserves_origin_and_old_packets(ledger, pki, tmp_path):
    worker, path = live.runtime(ledger, pki, tmp_path)
    initial = worker.epoch
    _, _, bound, first = live.resumed(ledger, pki)
    path.write_text(first)
    worker.ensure(first, native=True)
    remember(ledger, worker.request)
    _, _, _, second = next_resume(ledger, pki, bound, "bob", "alice")
    path.write_text(second)
    for stale in (initial, first):
        with pytest.raises(ValueError, match="Original native operation epoch"):
            worker.ensure(stale, native=True)
    worker.ensure(second, native=True)
    assert not worker.failed and worker.rotations == 2
    assert worker.request["grant"]["control_epoch"] == 3
    assert len(worker.seen_epochs) == 3
    assert worker.origin == ledger["app"].authority.family_origin(
        start_grant(worker.request["grant"])
    )


def test_archive_and_next_fence_roll_back_together_on_audit_failure(ledger, pki):
    state, proof, bound, epoch = live.resumed(ledger, pki)
    remember(ledger, live.activate(ledger, pki, epoch))
    controller = ledger["controller"]
    connection = controller("session.open", {}, subject="alice")["connection_id"]
    claim = controller(
        "execution.claim",
        dict(execution_id=ledger["grant"].execution_id, connection_id=connection, expected_epoch=2),
        subject="alice",
    )
    store = ledger["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    with pytest.raises(Fault):
        ledger["app"].authority.mutate(
            "bob",
            "execution.decide",
            str(uuid.uuid4()),
            dict(helpers.proof(bound), claim_id=claim["claim_id"], decision="accept"),
        )
    assert store.db.execute("SELECT COUNT(*) FROM live_handoff_history").fetchone()[0] == 0
    current = ledger["app"].authority.live_handoff.record(ledger["grant"].execution_id)
    assert current["state"] == "ACTIVE" and current["barrier_id"] == state["barrier_id"]
    assert live.observe(ledger, pki)["control_state"] == "OWNED"
