"""Deterministic deadline, replay and serialization checks; no native pause claims."""

from contextlib import contextmanager
import json
import threading
import time
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority, secret_hash
from openbexi_spell_server.contracts import Fault, policy
from openbexi_spell_server.store import ContextStore
from test_authority import Client, PERMISSIONS, SLOTS, public, worker_start
from test_preflight import proof


@pytest.fixture
def leased(tmp_path):
    now = [100.0]
    store = ContextStore(tmp_path, "A")
    authority = ExecutionAuthority(
        store,
        policy({name: PERMISSIONS for name in ("alice", "bob")}),
        worker_slots=SLOTS,
        controller_liveness_seconds=5,
        monotonic_clock=lambda: now[0],
    )
    try:
        yield authority, now
    finally:
        store.close()


def open_session(authority, subject="alice", key=None):
    return authority.mutate(subject, "session.open", key or str(uuid.uuid4()), {})


def beat(authority, session, subject="alice", key="heartbeat"):
    return authority.mutate(
        subject,
        "session.heartbeat",
        key,
        {
            "connection_id": session["connection_id"],
            "heartbeat_nonce": session["heartbeat_nonce"],
        },
    )


def test_renewal_rotates_challenge_and_stale_or_duplicate_never_extends(leased):
    authority, now = leased
    session = open_session(authority)
    now[0] += 4
    renewed = beat(authority, session)
    assert renewed["heartbeat_nonce"] != session["heartbeat_nonce"]
    deadline = authority.store.db.execute("SELECT deadline FROM controller_leases").fetchone()[0]
    for key in ("heartbeat", "different-key"):
        with pytest.raises(Fault, match="heartbeat_challenge_denied"):
            beat(authority, session, key=key)
    assert (
        authority.store.db.execute("SELECT deadline FROM controller_leases").fetchone()[0]
        == deadline
    )
    assert authority.store.db.execute("SELECT COUNT(*) FROM authority_requests").fetchone()[0] == 1
    assert authority.store.db.execute("SELECT nonce_hash FROM controller_leases").fetchone()[
        0
    ] == secret_hash(renewed["heartbeat_nonce"])
    now[0] = deadline
    with pytest.raises(Fault, match="controller_lease_expired"):
        beat(authority, dict(session, **renewed))


def test_session_open_replay_cannot_recover_or_persist_nonce(leased):
    authority, _ = leased
    session = open_session(authority, key="open")
    replay = open_session(authority, key="open")
    assert "heartbeat_nonce" not in replay
    assert replay["heartbeat_delivery"] == "new_session_required_on_replay"
    dump = "\n".join(authority.store.db.iterdump())
    assert session["heartbeat_nonce"] not in dump


def test_expiry_fences_final_grant_before_cleanup_and_retains_holds(leased):
    authority, now = leased
    client = Client(authority, "alice")
    execution = client.reserve()
    grant = worker_start(authority, execution)
    now[0] += 5
    with pytest.raises(Fault, match="controller_lease_expired"):
        authority.validate_start_grant(grant)
    authority.liveness.expire()
    assert public(authority, execution)["control_state"] == "CONTROLLER_DISCONNECTED"
    assert public(authority, execution)["lifecycle"] == "STARTING"
    assert authority.store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert authority.store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert authority.store.db.execute("SELECT cap_hash FROM executions").fetchone()[0] is None
    with pytest.raises(Fault):
        authority.admit_start("alice", proof(execution))


def test_cross_subject_challenge_is_not_a_controller_identity(leased):
    authority, now = leased
    session = open_session(authority)
    with pytest.raises(Fault, match="connection_denied"):
        beat(authority, session, subject="bob")
    now[0] += 5
    authority.liveness.expire()
    with pytest.raises(Fault, match="connection_denied"):
        beat(authority, session)


def test_wall_clock_changes_do_not_change_controller_deadline(leased):
    authority, now = leased
    session = open_session(authority)
    authority.clock = lambda: 10**20
    renewed = beat(authority, session)
    authority.clock = lambda: -(10**20)
    now[0] += 5
    with pytest.raises(Fault, match="controller_lease_expired"):
        beat(authority, dict(session, **renewed))


def test_rebind_wins_over_old_connection_cleanup(leased, monkeypatch):
    authority, now = leased
    old = Client(authority, "alice")
    execution = old.reserve()
    now[0] += 5
    fresh = Client(authority, "alice")
    original = authority._execution_lock
    moved = []

    @contextmanager
    def racing(execution_id):
        if not moved:
            moved.append(True)
            with monkeypatch.context() as patch:
                patch.setattr(authority, "_execution_lock", original)
                fresh.rebind(execution["id"], 1)
        with original(execution_id):
            yield

    monkeypatch.setattr(authority, "_execution_lock", racing)
    authority.liveness.expire()
    row = authority.store.db.execute("SELECT * FROM executions").fetchone()
    assert row["connection_id"] == fresh.connection and row["control_state"] == "OWNED"
    assert row["connection_generation"] == 2 and row["cap_hash"]


def test_expiry_does_not_wait_for_execution_mutex_inside_database_transaction(leased):
    authority, now = leased
    client = Client(authority, "alice")
    execution = client.reserve()
    release, entered = threading.Event(), threading.Event()

    def hold():
        with authority._execution_lock(execution["id"]):
            entered.set()
            release.wait(3)

    thread = threading.Thread(target=hold)
    thread.start()
    try:
        assert entered.wait(1)
        now[0] += 5
        authority.liveness.expire()
        assert authority.store.db.execute("SELECT active FROM sessions").fetchone()[0] == 2
        started = time.monotonic()
        public(authority, execution)
        assert time.monotonic() - started < 0.2
        with pytest.raises(Fault, match="connection_denied"):
            authority._session("alice", client.connection)
    finally:
        release.set()
        thread.join(1)
    authority.liveness.expire()
    assert public(authority, execution)["control_state"] == "CONTROLLER_DISCONNECTED"


def test_revoked_subject_is_still_fenced_without_reauthorization(leased):
    authority, now = leased
    execution = Client(authority, "alice").reserve()
    authority.subjects.pop("alice")
    now[0] += 5
    authority.liveness.expire()
    assert (
        authority.list_executions("bob")["executions"][0]["control_state"]
        == "CONTROLLER_DISCONNECTED"
    )
    assert authority.store.db.execute("SELECT id FROM executions").fetchone()[0] == execution["id"]


def test_watchdog_automatically_fences_and_stops_before_store_close(leased):
    authority, now = leased
    execution = Client(authority, "alice").reserve()
    authority.liveness.start()
    now[0] += 5
    deadline = time.monotonic() + 2
    while public(authority, execution)["control_state"] == "OWNED" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert public(authority, execution)["control_state"] == "CONTROLLER_DISCONNECTED"
    authority.store.close()
    assert not authority.liveness.thread.is_alive()


def test_audit_capacity_failure_stops_authority_but_never_renews_expired_session(leased):
    authority, now = leased
    session = open_session(authority)
    authority.store.max_events = authority.store.db.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]
    authority.liveness.start()
    now[0] += 5
    deadline = time.monotonic() + 2
    while not authority.store.failed and time.monotonic() < deadline:
        time.sleep(0.01)
    assert authority.store.failed
    with pytest.raises(Fault, match="state_unavailable"):
        beat(authority, session)


def test_restart_invalidates_challenge_and_preserves_retained_execution(leased, tmp_path):
    authority, _ = leased
    session = open_session(authority)
    client = Client(authority, "alice")
    client.reserve()
    authority.store.close()
    store = ContextStore(tmp_path, "A")
    try:
        restarted = ExecutionAuthority(
            store, authority.subjects, worker_slots=SLOTS, controller_liveness_seconds=5
        )
        with pytest.raises(Fault, match="connection_denied"):
            beat(restarted, session)
        assert store.db.execute("PRAGMA user_version").fetchone()[0] == 23
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert (
            store.db.execute("SELECT control_state FROM executions").fetchone()[0]
            == "RECOVERY_REQUIRED"
        )
    finally:
        store.close()


@pytest.mark.parametrize("seconds", [False, 0, 4, 301, 5.0, "30"])
def test_lease_configuration_cannot_disable_fencing(leased, seconds):
    from openbexi_spell_server.liveness import ControllerLiveness

    authority, _ = leased
    with pytest.raises(ValueError, match="Controller lease"):
        ControllerLiveness(authority, seconds)


def test_many_heartbeats_keep_bounded_rows_and_redacted_audit(leased):
    authority, _ = leased
    session = open_session(authority)
    before = authority.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    for number in range(100):
        session.update(beat(authority, session, key=str(number)))
    assert authority.store.db.execute("SELECT COUNT(*) FROM controller_leases").fetchone()[0] == 1
    assert authority.store.db.execute("SELECT COUNT(*) FROM authority_requests").fetchone()[0] == 1
    assert authority.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
    assert session["heartbeat_nonce"] not in json.dumps(authority.store.snapshot())


def test_expired_session_cleanup_acknowledges_only_its_durable_fence(leased):
    authority, now = leased
    old = Client(authority, "alice")
    execution = old.reserve()
    now[0] += 5
    authority.liveness.expire()
    fresh = Client(authority, "alice")
    fresh.rebind(execution["id"], 1)
    before = dict(authority.store.db.execute("SELECT * FROM executions").fetchone())
    payload = {"connection_id": old.connection}
    with pytest.raises(Fault, match="connection_denied"):
        authority.mutate("bob", "session.close", "wrong-owner", payload)
    closed = old.call("session.close", payload, "close-expired")
    assert closed == {"closed": True, "already_closed": True}
    assert old.call("session.close", payload, "close-expired") == dict(closed, replayed=True)
    assert dict(authority.store.db.execute("SELECT * FROM executions").fetchone()) == before
    assert authority.store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_retained_native_context_requires_default_lease_and_owns_watchdog(tmp_path, source):
    from openbexi_spell_server.services import Context

    store = ContextStore(tmp_path / "native", "A")
    try:
        app = Context(
            store,
            "a" * 64,
            {"alice": PERMISSIONS},
            worker_slots=SLOTS,
            approved_sources=source["config"],
            worker_launch="retained-single-use",
            worker_credentials={
                "profile": "single-host-preflight",
                "identities": {"b" * 64: {"slot": "slot-0", "incarnation": "incarnation-0"}},
            },
        )
        assert app.authority.liveness.seconds == 30
        assert app.authority.liveness.thread.is_alive()
        app.close()
        assert not app.authority.liveness.thread.is_alive()
    finally:
        store.close()
