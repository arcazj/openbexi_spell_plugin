"""Authority protocol checks; no native runtime or authenticated worker is simulated as qualified."""

import json
import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from openbexi_spell_server.authority import ExecutionAuthority, StartGrant
from openbexi_spell_server.contracts import Actor, Fault, policy
from openbexi_spell_server.store import ContextStore

PERMISSIONS = [
    "execution:read",
    "execution:start",
    "execution:control",
    "execution:request_control",
]
SLOTS = {"slot-" + str(n): "incarnation-" + str(n) for n in range(10)}


class Client:
    def __init__(self, authority, subject):
        self.authority, self.subject = authority, subject
        self.connection = self.call("session.open", {})["connection_id"]

    def call(self, method, payload, key=None):
        return self.authority.mutate(self.subject, method, key or str(uuid.uuid4()), payload)

    def reserve(self, name="procedure"):
        return self.call(
            "execution.reserve",
            dict(
                procedure_id=name,
                connection_id=self.connection,
                source_revision="a" * 40,
                source_sha256="b" * 64,
                runtime_image="sha256:" + "c" * 64,
                driver_binding="simulator",
            ),
        )

    def claim(self, execution):
        return self.call(
            "execution.claim",
            dict(
                execution_id=execution["id"],
                connection_id=self.connection,
                expected_epoch=execution["epoch"],
            ),
        )

    def decision(self, execution, claim, decision="accept"):
        return dict(
            execution_id=execution["id"],
            connection_id=execution["connection_id"],
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
            claim_id=claim["claim_id"],
            decision=decision,
        )

    def rebind(self, execution_id, epoch):
        return self.call(
            "execution.rebind",
            dict(execution_id=execution_id, connection_id=self.connection, expected_epoch=epoch),
        )


@pytest.fixture
def authority(tmp_path):
    store = ContextStore(tmp_path, "A")
    actors = policy({name: PERMISSIONS for name in ("alice", "bob", "carol")})
    service = ExecutionAuthority(store, actors, worker_slots=SLOTS)
    try:
        yield service
    finally:
        store.close()


def admit_start(authority, execution):
    return authority.admit_start(
        execution["owner"],
        dict(
            execution_id=execution["id"],
            connection_id=execution["connection_id"],
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
        ),
    )


def worker_start(authority, execution):
    grant = admit_start(authority, execution)
    authority.consume_start(grant, grant.worker_slot, grant.worker_incarnation)
    return grant


def public(authority, execution):
    return next(
        r for r in authority.list_executions("alice")["executions"] if r["id"] == execution["id"]
    )


def test_one_of_100_concurrent_duplicate_reservations_and_context_scoped_identity(
    authority, tmp_path
):
    alice = Client(authority, "alice")

    def attempt(_):
        try:
            return alice.reserve()["id"]
        except Fault as error:
            return error.code

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(100)))
    assert results.count("procedure_reserved") == 99
    assert len(authority.list_executions("alice")["executions"]) == 1
    other_store = ContextStore(tmp_path / "other", "B")
    try:
        other = ExecutionAuthority(other_store, authority.subjects, worker_slots=SLOTS)
        assert Client(other, "alice").reserve()["id"] not in results
    finally:
        other_store.close()


def test_ten_distinct_single_use_slots_and_bounded_capacity(authority):
    alice = Client(authority, "alice")
    executions = [alice.reserve("procedure-" + str(n)) for n in range(10)]
    grants = [worker_start(authority, execution) for execution in executions]
    assert len({g.worker_incarnation for g in grants}) == 10
    assert all(authority.validate_start_grant(g) for g in grants)
    with pytest.raises(Fault, match="worker_capacity_unavailable"):
        alice.reserve("eleventh")
    with pytest.raises(Fault, match="procedure_reserved"):
        alice.reserve("procedure-0")


def test_transfer_only_b_of_a_b_c_and_capability_is_delivered_only_to_new_owner(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    a, b, c = [alice.reserve(name) for name in ("A", "B", "C")]
    before = [public(authority, e) for e in (a, c)]
    claim = bob.claim(b)
    payload = alice.decision(b, claim)
    accepted = alice.call("execution.decide", payload, "accept-once")
    assert accepted["state"] == "ACCEPTED" and accepted["epoch"] == 2
    assert "capability" not in accepted
    assert alice.call("execution.decide", payload, "accept-once") == {**accepted, "replayed": True}
    assert [public(authority, e) for e in (a, c)] == before
    assert public(authority, b)["owner"] == "bob"
    with pytest.raises(Fault, match="controller_fenced"):
        alice.rebind(b["id"], 2)
    # Acceptance does not disclose the new controller's secret to the former owner.
    with pytest.raises(Fault, match="controller_fenced"):
        worker_start(authority, b)
    bound = bob.rebind(b["id"], 2)
    assert len(bound["capability"]) == 64 and bound["capability"] != b["capability"]
    assert worker_start(authority, bound).control_epoch == 2
    with pytest.raises(Fault, match="controller_fenced"):
        alice.call("execution.decide", payload)


def test_claim_races_have_one_pending_and_accept_races_one_effective_transfer(authority):
    alice, bob, carol = [Client(authority, name) for name in ("alice", "bob", "carol")]
    execution = alice.reserve()

    def claim(n):
        client = bob if n % 2 else carol
        try:
            return client.claim(execution)
        except Fault as error:
            return error.code

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(claim, range(30)))
    assert results.count("claim_pending") == 29
    pending = next(r for r in results if isinstance(r, dict))
    body = alice.decision(execution, pending)

    def accept(_):
        try:
            return alice.call("execution.decide", body)["state"]
        except Fault as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(accept, range(20)))
    assert decisions.count("ACCEPTED") == 1
    assert decisions.count("controller_fenced") == 19
    assert public(authority, execution)["epoch"] == 2


@pytest.mark.parametrize(
    "field,value", [("expected_epoch", 2), ("connection_generation", 2), ("capability", "f" * 64)]
)
def test_forged_owner_proofs_cannot_accept(authority, field, value):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    body = alice.decision(execution, bob.claim(execution))
    body[field] = value
    with pytest.raises(Fault, match="controller_fenced"):
        alice.call("execution.decide", body)
    assert public(authority, execution)["owner"] == "alice"


def test_read_only_account_and_live_revocation_precede_replay_and_target_acceptance(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    claim = bob.claim(execution)
    authority.subjects["bob"] = Actor("bob", frozenset({"execution:read"}))
    with pytest.raises(Fault, match="permission_denied"):
        alice.call("execution.decide", alice.decision(execution, claim))
    with pytest.raises(Fault, match="permission_denied"):
        bob.claim(execution)
    body = dict(execution_id=execution["id"], connection_id=alice.connection, expected_epoch=1)
    first = alice.call("execution.rebind", body, "rebind")
    authority.subjects["alice"] = Actor("alice", frozenset({"execution:read"}))
    with pytest.raises(Fault, match="permission_denied"):
        alice.call("execution.rebind", body, "rebind")
    assert "capability" in first


def test_reject_cancel_and_server_time_expiry_never_transfer(authority):
    now = [1000.0]
    authority.clock = lambda: now[0]
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    rejected = alice.call(
        "execution.decide", alice.decision(execution, bob.claim(execution), "reject")
    )
    assert rejected["state"] == "REJECTED"
    claim = bob.claim(execution)
    assert (
        bob.call(
            "execution.cancel",
            dict(
                execution_id=execution["id"],
                connection_id=bob.connection,
                claim_id=claim["claim_id"],
            ),
        )["state"]
        == "CANCELLED"
    )
    claim = bob.claim(execution)
    now[0] = claim["expires_at"]
    assert alice.call("execution.decide", alice.decision(execution, claim))["state"] == "EXPIRED"
    assert bob.claim(execution)["state"] == "PENDING"
    assert public(authority, execution)["epoch"] == 1


def test_changed_idempotency_payload_and_method_scoping(authority):
    alice = Client(authority, "alice")
    first = alice.call("session.open", {}, "same-key")
    replay = alice.call("session.open", {}, "same-key")
    assert replay == {**first, "replayed": True}
    execution = alice.reserve()
    body = dict(execution_id=execution["id"], connection_id=alice.connection, expected_epoch=1)
    alice.call("execution.rebind", body, "same-key")
    other = alice.reserve("other-procedure")
    assert (
        alice.call("execution.rebind", {**body, "execution_id": other["id"]}, "same-key")["id"]
        == other["id"]
    )
    with pytest.raises(Fault, match="idempotency_payload_conflict"):
        alice.call("execution.rebind", {**body, "expected_epoch": 2}, "same-key")


def test_lost_capability_response_requires_rebind_and_never_reveals_plaintext_in_state(authority):
    alice = Client(authority, "alice")
    execution = alice.reserve()
    body = dict(execution_id=execution["id"], connection_id=alice.connection, expected_epoch=1)
    first = alice.call("execution.rebind", body, "lost")
    replay = alice.call("execution.rebind", body, "lost")
    assert (
        "capability" not in replay and replay["capability_delivery"] == "rebind_required_on_replay"
    )
    second = alice.call("execution.rebind", body)
    assert second["connection_generation"] > first["connection_generation"]
    with authority.store.transaction(write=False):
        all_rows = [
            list(row)
            for table in ("executions", "events", "authority_requests")
            for row in authority.store.db.execute("SELECT * FROM " + table)
        ]
    serialized = json.dumps(all_rows) + json.dumps(authority.list_executions("alice"))
    assert all(
        token not in serialized
        for token in (first["capability"], second["capability"], execution["capability"])
    )


def test_rebind_invalidates_claim_and_delayed_close_cannot_fence_new_connection(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    old_claim = bob.claim(execution)
    replacement = Client(authority, "alice")
    rebound = replacement.rebind(execution["id"], 1)
    alice.call("session.close", {"connection_id": alice.connection})
    assert public(authority, execution)["control_state"] == "OWNED"
    with pytest.raises(Fault, match="connection_denied"):
        alice.call("execution.decide", alice.decision(execution, old_claim))
    assert (
        worker_start(authority, rebound).connection_generation == rebound["connection_generation"]
    )


def test_closed_claimant_connection_cannot_receive_ownership(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    claim = bob.claim(execution)
    bob.call("session.close", {"connection_id": bob.connection})
    with pytest.raises(Fault, match="connection_denied"):
        alice.call("execution.decide", alice.decision(execution, claim))
    assert public(authority, execution)["owner"] == "alice"


def test_duplicate_worker_start_consumption_has_one_winner_and_lost_response_retains_hold(
    authority,
):
    alice = Client(authority, "alice")
    execution = alice.reserve()

    original = admit_start(authority, execution)

    def start(_):
        try:
            authority.consume_start(original, original.worker_slot, original.worker_incarnation)
            return original
        except Fault as error:
            return error.code

    with ThreadPoolExecutor(max_workers=20) as pool:
        grants = list(pool.map(start, range(100)))
    assert grants.count("worker_start_fenced") == 99
    grant = next(g for g in grants if isinstance(g, StartGrant))
    assert authority.validate_start_grant(grant)
    assert public(authority, execution)["lifecycle"] == "STARTING"
    with pytest.raises(Fault, match="procedure_reserved"):
        alice.reserve()


@pytest.mark.parametrize(
    "field,value",
    [
        ("authority_incarnation", str(uuid.uuid4())),
        ("worker_slot", "other"),
        ("worker_incarnation", "other"),
        ("worker_generation", 2),
        ("control_epoch", 2),
        ("connection_id", str(uuid.uuid4())),
        ("connection_generation", 2),
        ("request_id", str(uuid.uuid4())),
        ("operation_digest", "0" * 64),
        ("token", "0" * 64),
        ("token", "non-ascii-\u2603"),
    ],
)
def test_original_worker_grant_fields_cannot_be_restamped(authority, field, value):
    grant = worker_start(authority, Client(authority, "alice").reserve())
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.validate_start_grant(replace(grant, **{field: value}))
    assert authority.validate_start_grant(grant)


def test_worker_binding_mismatch_does_not_consume_slot(authority):
    execution = Client(authority, "alice").reserve()
    grant = admit_start(authority, execution)
    with pytest.raises(Fault, match="worker_start_fenced"):
        authority.consume_start(grant, grant.worker_slot, "forged-incarnation")
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.consume_start(
            replace(grant, authority_incarnation="old-authority"),
            grant.worker_slot,
            grant.worker_incarnation,
        )
    assert authority.consume_start(grant, grant.worker_slot, grant.worker_incarnation)
    assert authority.validate_start_grant(grant)


def test_native_transfer_and_rebind_fail_closed_preserve_owner_and_reservation(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    grant = worker_start(authority, execution)
    result = alice.call("execution.decide", alice.decision(execution, bob.claim(execution)))
    assert result["state"] == "BLOCKED" and result["recovery_required"]
    state = public(authority, execution)
    assert (
        state["owner"] == "alice"
        and state["epoch"] == 1
        and state["control_state"] == "RECOVERY_REQUIRED"
    )
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.validate_start_grant(grant)
    with pytest.raises(Fault, match="native_rebind_unqualified"):
        alice.rebind(execution["id"], 1)
    with pytest.raises(Fault, match="procedure_reserved"):
        alice.reserve()


def test_worker_start_vs_accept_has_no_old_epoch_start_after_effective_transfer(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    # Ten independent races, using distinct slots; no worker is reused.
    for n in range(10):
        execution = alice.reserve("race-" + str(n))
        claim = bob.claim(execution)
        original = admit_start(authority, execution)
        barrier = threading.Barrier(2)

        def start():
            barrier.wait(timeout=2)
            try:
                authority.consume_start(original, original.worker_slot, original.worker_incarnation)
                return original
            except Fault as error:
                return error.code

        def accept():
            barrier.wait(timeout=2)
            return alice.call("execution.decide", alice.decision(execution, claim))["state"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            s, a = pool.submit(start), pool.submit(accept)
            started, accepted = s.result(timeout=3), a.result(timeout=3)
        assert (isinstance(started, StartGrant) and accepted == "BLOCKED") or (
            started == "worker_grant_fenced" and accepted == "ACCEPTED"
        )
        assert public(authority, execution)["epoch"] == (2 if accepted == "ACCEPTED" else 1)


def test_audit_capacity_failure_rolls_back_transfer_and_both_events(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    claim = bob.claim(execution)
    before = public(authority, execution)
    with authority.store.transaction(write=False):
        events = authority.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    authority.store.max_events = events + 1  # Transfer needs TWO atomic events.
    with pytest.raises(Fault, match="audit_capacity_reached"):
        alice.call("execution.decide", alice.decision(execution, claim))
    assert public(authority, execution) == before
    with authority.store.transaction(write=False):
        assert authority.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == events
        assert (
            authority.store.db.execute(
                "SELECT state FROM claims WHERE id=?", (claim["claim_id"],)
            ).fetchone()[0]
            == "PENDING"
        )


def test_execution_mutex_timeout_is_bounded_and_does_not_block_other_execution(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    a, b = alice.reserve("A"), alice.reserve("B")
    with authority._execution_lock(a["id"]):
        with ThreadPoolExecutor(max_workers=2) as pool:
            blocked = pool.submit(bob.claim, a)
            assert pool.submit(bob.claim, b).result(timeout=0.5)["state"] == "PENDING"
            with pytest.raises(Fault, match="execution_busy"):
                blocked.result(timeout=0.6)


def test_sqlite_failure_prevents_start_grant_and_later_authority_requests(authority):
    execution = Client(authority, "alice").reserve()
    authority.store.db.execute("PRAGMA query_only=ON")
    with pytest.raises(Fault, match="state_unavailable"):
        worker_start(authority, execution)
    with pytest.raises(Fault, match="state_unavailable"):
        authority.list_executions("alice")


def test_restart_fences_every_prior_grant_and_keeps_all_holds(tmp_path):
    store = ContextStore(tmp_path, "A")
    actors = policy({"alice": PERMISSIONS})
    first = ExecutionAuthority(store, actors, worker_slots=SLOTS)
    alice = Client(first, "alice")
    execution = alice.reserve()
    grant = worker_start(first, execution)
    incarnation = store.incarnation
    store.close()
    for expected_epoch in (2, 3):
        store = ContextStore(tmp_path, "A")
        try:
            restored = ExecutionAuthority(store, actors, worker_slots=SLOTS)
            assert store.incarnation != incarnation
            state = public(restored, execution)
            assert state["epoch"] == expected_epoch and state["lifecycle"] == "RECOVERY_REQUIRED"
            with pytest.raises(Fault, match="connection_denied"):
                restored.validate_start_grant(grant)
            owner = Client(restored, "alice")
            with pytest.raises(Fault, match="native_rebind_unqualified"):
                owner.rebind(execution["id"], expected_epoch)
            with pytest.raises(Fault, match="procedure_reserved"):
                owner.reserve()
            assert (
                store.db.execute(
                    "SELECT spent FROM workers WHERE slot=?", (grant.worker_slot,)
                ).fetchone()[0]
                == 1
            )
        finally:
            store.close()


def test_real_process_death_after_start_commit_cannot_create_replacement(tmp_path):
    script = r"""
import json, os, sys
from dataclasses import asdict
from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.contracts import policy
from openbexi_spell_server.store import ContextStore
from test_authority import Client, PERMISSIONS, worker_start
from pathlib import Path
store = ContextStore(sys.argv[1], 'A')
authority = ExecutionAuthority(store, policy({'alice': PERMISSIONS}), worker_slots={'slot-0': 'incarnation-0'})
execution = Client(authority, 'alice').reserve()
grant = worker_start(authority, execution)
Path(sys.argv[2]).write_text(json.dumps({'execution': execution, 'grant': asdict(grant)}))
os._exit(17)
"""
    root = Path(__file__).resolve().parents[1]
    evidence = tmp_path / "private-result.json"
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "state"), str(evidence)],
        env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(root / "src"), str(root / "tests")])),
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 17, result.stderr.decode()
    recorded = json.loads(evidence.read_text())
    store = ContextStore(tmp_path / "state", "A")
    try:
        restored = ExecutionAuthority(
            store, policy({"alice": PERMISSIONS}), worker_slots={"slot-0": "incarnation-0"}
        )
        assert public(restored, recorded["execution"])["lifecycle"] == "RECOVERY_REQUIRED"
        with pytest.raises(Fault):
            restored.validate_start_grant(StartGrant(**recorded["grant"]))
        with pytest.raises(Fault, match="worker_capacity_unavailable"):
            Client(restored, "alice").reserve("replacement")
    finally:
        store.close()


def test_worker_configuration_cannot_silently_replace_or_reuse_container(tmp_path):
    actors = policy({"alice": PERMISSIONS})
    store = ContextStore(tmp_path, "A")
    ExecutionAuthority(store, actors, worker_slots={"one": "old"})
    with pytest.raises(ValueError, match="already has"):
        ExecutionAuthority(store, actors)
    store.close()
    restored = ContextStore(tmp_path, "A")
    try:
        with pytest.raises(ValueError, match="recreation requires"):
            ExecutionAuthority(restored, actors, worker_slots={"one": "new"})
    finally:
        restored.close()


def test_delayed_worker_request_cannot_acquire_new_owner_epoch_after_transfer_and_rebind(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    old = admit_start(authority, execution)
    claim = bob.claim(execution)
    assert alice.call("execution.decide", alice.decision(execution, claim))["state"] == "ACCEPTED"
    bound = bob.rebind(execution["id"], 2)
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.consume_start(old, old.worker_slot, old.worker_incarnation)
    # Only a NEW owner-authorized operation can generate new provenance.
    fresh = admit_start(authority, bound)
    assert fresh.control_epoch == 2 and fresh.request_id != old.request_id
    assert authority.consume_start(fresh, fresh.worker_slot, fresh.worker_incarnation)
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.validate_start_grant(old)
    assert authority.validate_start_grant(fresh)


def test_authorized_user_cannot_use_another_subject_connection_or_owner_secret(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    claim = bob.claim(execution)
    with pytest.raises(Fault, match="connection_denied"):
        bob.call("session.close", {"connection_id": alice.connection})
    with pytest.raises(Fault, match="connection_denied"):
        bob.call("execution.decide", alice.decision(execution, claim))
    assert public(authority, execution)["owner"] == "alice"


def test_revoked_controller_cannot_consume_or_validate_previously_admitted_worker_start(authority):
    alice = Client(authority, "alice")
    grant = admit_start(authority, alice.reserve())
    authority.subjects["alice"] = Actor("alice", frozenset({"execution:read"}))
    with pytest.raises(Fault, match="permission_denied"):
        authority.consume_start(grant, grant.worker_slot, grant.worker_incarnation)
    with pytest.raises(Fault, match="permission_denied"):
        authority.validate_start_grant(grant)


def test_start_consumption_audit_failure_never_spends_worker_or_releases_grant(authority):
    execution = Client(authority, "alice").reserve()
    grant = admit_start(authority, execution)
    count = authority.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    authority.store.max_events = count
    with pytest.raises(Fault, match="audit_capacity_reached"):
        authority.consume_start(grant, grant.worker_slot, grant.worker_incarnation)
    assert public(authority, execution)["lifecycle"] == "RESERVED"
    assert (
        authority.store.db.execute(
            "SELECT spent FROM workers WHERE slot=?", (grant.worker_slot,)
        ).fetchone()[0]
        == 0
    )
    with pytest.raises(Fault, match="worker_grant_fenced"):
        authority.validate_start_grant(grant)


def test_expired_cancel_and_session_quotas_do_not_grant_control(authority):
    alice, bob = Client(authority, "alice"), Client(authority, "bob")
    execution = alice.reserve()
    claim = bob.claim(execution)
    authority.clock = lambda: claim["expires_at"]
    assert (
        bob.call(
            "execution.cancel",
            {
                "execution_id": execution["id"],
                "connection_id": bob.connection,
                "claim_id": claim["claim_id"],
            },
        )["state"]
        == "EXPIRED"
    )
    for _ in range(15):
        alice.call("session.open", {})
    with pytest.raises(Fault, match="subject_session_capacity_reached"):
        alice.call("session.open", {})
    assert bob.call("session.open", {})["connection_id"]
    assert public(authority, execution)["owner"] == "alice"
