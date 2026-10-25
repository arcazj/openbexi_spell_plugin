"""Original-grant native RUN journal over real TLS, including reply-loss races."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.contracts import Fault, canonical, policy
from openbexi_spell_server.control import NativeControlJournal
from openbexi_spell_server.store import ContextStore
from test_launch import call
from test_pause import accept
import test_child_gate as gates
import test_family as families


source = gates.source
setup = gates.setup
family = gates.family
provider = gates.provider

spec = importlib.util.spec_from_file_location(
    "native_control_journal_test",
    Path(__file__).resolve().parents[2] / "host_runtime/python/control_journal.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def journal(family):
    journal = NativeControlJournal(family["app"].authority)
    journal.bind_member(
        family["grant"],
        dict(
            target_admission_id=None,
            instance_id="main#1",
            pid=1234,
            parent_pid=1000,
            start_ticks=99,
            executable_sha256="a" * 64,
        ),
    )
    return journal


def operation():
    return dict(request_id=str(uuid.uuid4()), target_admission_id=None, command="CMD_RUN")


def admit(family, pki, body=None, **updates):
    return call(family, pki, family["grant"], "control-admit", **(body or operation()), **updates)


def report(family, pki, body, outcome="IPC_SEND_ACKNOWLEDGED", **updates):
    return call(family, pki, family["grant"], "control-report", **body, outcome=outcome, **updates)


def rows(family):
    return family["store"].db.execute("SELECT * FROM native_control_attempts").fetchall()


@pytest.fixture
def agent(provider, journal):
    sent = []
    store = journal.store

    def send(identifier, fields=None, **options):
        target = options.get("procedure") or "main#1"
        row = store.db.execute(
            "SELECT state,outcome FROM native_control_attempts WHERE target_id=?",
            (provider.started[target] or "",),
        ).fetchone()
        assert row is not None and tuple(row) == ("DISPATCH_UNCERTAIN", None)
        sent.append((identifier, fields, options))
        return {"sent": True}

    session = SimpleNamespace(instance="main#1", request=send)
    journal = module.NativeRunJournal(session, provider.request, provider.route, provider)
    journal.sent = sent
    return journal


def test_routes_require_explicit_control_profile(family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 404
    assert report(family, pki, body)[0] == 404
    assert consume(family, pki, body)[0] == 404


@pytest.mark.parametrize("certificate", ["alice", "bob", "observer", "listener"])
def test_non_worker_cannot_admit_or_report(journal, family, pki, certificate):
    body = operation()
    assert admit(family, pki, body, certificate=certificate)[0] in (403, 404)
    assert report(family, pki, body, certificate=certificate)[0] in (403, 404)
    assert call(family, pki, family["grant"], "control-consume", **body, certificate=certificate)[
        0
    ] in (403, 404)
    assert not rows(family)


def test_copied_start_config_without_consumption_proof_cannot_admit(journal, family, pki):
    assert admit(family, pki, runtime_capability="0" * 64)[0] == 403
    assert not rows(family)


def test_one_of_100_run_admissions_wins_and_new_uuid_cannot_replay(journal, family, pki):
    body = operation()
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: admit(family, pki, body)[0], range(100)))
    assert statuses.count(200) == 1 and statuses.count(409) == 99
    assert admit(family, pki)[0] == 409
    assert len(rows(family)) == 1
    assert family["store"].db.execute("PRAGMA user_version").fetchone()[0] == 14


def test_send_ack_is_not_execution_or_queue_settlement(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    code, answer = report(family, pki, body)
    assert code == 200
    assert answer["result"]["state"] == "DISPATCH_UNCERTAIN"
    assert not answer["result"]["quiescence_proven"]
    assert not answer["result"]["effective_transfer"]
    assert rows(family)[0]["state"] == "DISPATCH_UNCERTAIN"
    events = family["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert report(family, pki, body) == (code, answer)
    assert family["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == events
    assert report(family, pki, body, outcome="UNCERTAIN")[0] == 409
    decision, _ = accept(family)
    assert decision["state"] == "BLOCKED"
    row = family["store"].db.execute("SELECT owner,epoch,control_state FROM executions").fetchone()
    assert tuple(row) == ("alice", 1, "RECOVERY_REQUIRED")
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("outcome", ["COMPLETED", "QUIESCED", True, {}, None])
def test_worker_cannot_assert_a_completed_control_queue(journal, family, pki, outcome):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert report(family, pki, body, outcome=outcome)[0] == 403
    assert rows(family)[0]["outcome"] is None


def test_report_binding_cannot_change_command_or_target(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    for change in ({"command": "CMD_PAUSE"}, {"target_admission_id": str(uuid.uuid4())}):
        assert report(family, pki, dict(body, **change))[0] == 403
    assert rows(family)[0]["outcome"] is None


def test_diagnostics_after_disconnect_cannot_reauthorize_control(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    family["controller"]("session.close", {"connection_id": family["connection"]})
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert report(family, pki, body, outcome="UNCERTAIN")[0] == 200
    assert admit(family, pki)[0] == 403
    assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_control_requires_consumed_original_family_target(journal, family, pki):
    child = families.admit(family, pki)[1]["result"]["child_grant"]
    body = dict(operation(), target_admission_id=child["admission_id"])
    assert admit(family, pki, body)[0] == 403
    assert families.consume(family, pki, child)[0] == 200
    assert admit(family, pki, body)[0] == 200
    assert len(rows(family)) == 1
    assert rows(family)[0]["target_id"] == child["admission_id"]


def test_audit_failure_rolls_back_admission(journal, family, pki):
    family["store"].max_events = (
        family["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    )
    assert admit(family, pki)[0] == 503
    assert not rows(family)


def test_restart_retains_uncertainty_original_binding_and_holds(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert report(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert consume(family, pki, body)[0] == 200
    before = dict(rows(family)[0])
    old = family["store"]
    directory = Path(old.db.execute("PRAGMA database_list").fetchone()[2]).parent
    old.close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(store, family["app"].subjects)
        restarted = NativeControlJournal(authority)
        after = dict(store.db.execute("SELECT * FROM native_control_attempts").fetchone())
        assert after == dict(before, state="RESTART_FENCED")
        assert (
            store.db.execute("SELECT state FROM native_control_forwards").fetchone()[0]
            == "RESTART_FENCED"
        )
        assert (
            store.db.execute("SELECT state FROM native_control_consumptions").fetchone()[0]
            == "RESTART_FENCED"
        )
        with pytest.raises(Fault):
            restarted.consume(family["grant"], body)
        with pytest.raises(Fault):
            restarted.forward(family["grant"], body)
        with pytest.raises(Fault):
            restarted.admit(family["grant"], operation())
        with pytest.raises(Fault):
            restarted.report(family["grant"], dict(body, outcome="IPC_SEND_ACKNOWLEDGED"))
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        store.close()


def test_agent_runs_root_and_admitted_child_once_with_exact_original_identity(
    agent, provider, family
):
    provider.admit(gates.body())
    assert agent.dispatch("CMD_RUN", send=True) == {"sent": True}
    assert agent.dispatch("CMD_RUN", send=True, procedure="child#1") == {"sent": True}
    assert len(agent.sent) == 2 and len(rows(family)) == 2
    assert all(row["state"] == "DISPATCH_UNCERTAIN" for row in rows(family))
    serialized = canonical([dict(row) for row in rows(family)]).decode()
    assert family["grant"].token not in serialized
    assert provider.request["runtime_capability"] not in serialized
    with pytest.raises(ValueError, match="already attempted"):
        agent.dispatch("CMD_RUN", send=True)


@pytest.mark.parametrize("stage", ["control-admit", "native-send", "control-report"])
def test_agent_does_not_replay_after_lost_reply(agent, family, stage):
    real = agent.route

    def lost(payload, **kwargs):
        result = real.call(payload, **kwargs)
        if kwargs["path"].endswith(stage):
            raise TimeoutError("Injected lost reply after durable commit")
        return result

    agent.route = SimpleNamespace(call=lost)
    if stage == "native-send":
        send = agent.original

        def unknown(*args, **kwargs):
            send(*args, **kwargs)
            raise TimeoutError("Injected native IPC uncertainty")

        agent.original = unknown
    with pytest.raises(TimeoutError):
        agent.dispatch("CMD_RUN", send=True)
    with pytest.raises(ValueError, match="already attempted"):
        agent.dispatch("CMD_RUN", send=True)
    assert len(agent.sent) == (0 if stage == "control-admit" else 1)
    assert len(rows(family)) == 1 and rows(family)[0]["state"] == "DISPATCH_UNCERTAIN"


def test_fence_between_admission_and_transport_cannot_be_mistaken_for_handoff(agent, family):
    send = agent.original

    def fence(*args, **kwargs):
        decision, _ = accept(family)
        assert decision["state"] == "BLOCKED"
        return send(*args, **kwargs)

    agent.original = fence
    assert agent.dispatch("CMD_RUN", send=True) == {"sent": True}
    assert rows(family)[0]["state"] == "DISPATCH_UNCERTAIN"
    assert rows(family)[0]["outcome"] == "IPC_SEND_ACKNOWLEDGED"
    row = family["store"].db.execute("SELECT owner,epoch,control_state FROM executions").fetchone()
    assert tuple(row) == ("alice", 1, "RECOVERY_REQUIRED")


def test_forged_admission_reply_prevents_native_send(agent, family):
    real = agent.route

    def forged(payload, **kwargs):
        return dict(real.call(payload, **kwargs), quiescence_proven=True)

    agent.route = SimpleNamespace(call=forged)
    with pytest.raises(ValueError, match="receipt differs"):
        agent.dispatch("CMD_RUN", send=True)
    assert not agent.sent and len(rows(family)) == 1


def test_concurrent_agent_duplicate_never_duplicates_native_send(agent, family):
    def run(_):
        try:
            agent.dispatch("CMD_RUN", send=True)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(run, range(20))) == 1
    assert len(agent.sent) == 1 and len(rows(family)) == 1


def forward(family, pki, body):
    return call(family, pki, family["grant"], "control-forward", **body)


def test_one_of_twenty_forward_admissions_wins_without_queue_proof(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: forward(family, pki, body), range(20)))
    assert sum(code == 200 for code, _ in replies) == 1
    assert sum(code == 409 for code, _ in replies) == 19
    result = next(reply["result"] for code, reply in replies if code == 200)
    assert result["state"] == "FORWARD_UNPROVEN" and not result["quiescence_proven"]
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_forwards").fetchone()[0]
        == 1
    )


def test_admitted_run_cannot_forward_after_owner_fence(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert accept(family)[0]["state"] == "BLOCKED"
    assert forward(family, pki, body)[0] == 403
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_forwards").fetchone()[0]
        == 0
    )


def test_forged_forward_target_does_not_consume_original_attempt(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, dict(body, target_admission_id=str(uuid.uuid4())))[0] == 403
    assert forward(family, pki, body)[0] == 200


def native_forward_body(agent, **updates):
    identifier = agent.sent[0][1]["V08ControlRequest"]
    return dict(
        schema="openbexi.native-control/1",
        command="CMD_RUN",
        request_id=identifier,
        instance_id="main#1",
        **updates,
    )


def test_native_forward_callback_matches_actual_ipc_marker_once(agent, family):
    agent.dispatch("CMD_RUN", send=True)
    body = native_forward_body(agent)
    agent.forward(body)
    with pytest.raises(ValueError, match="already attempted"):
        agent.forward(body)
    assert len(agent.forwarded) == 1
    assert (
        family["store"].db.execute("SELECT state FROM native_control_forwards").fetchone()[0]
        == "FORWARD_UNPROVEN"
    )


def test_native_forward_denies_unregistered_and_cross_target_markers(agent, family):
    body = dict(
        schema="openbexi.native-control/1",
        command="CMD_RUN",
        request_id=str(uuid.uuid4()),
        instance_id="main#1",
    )
    with pytest.raises(ValueError, match="not admitted"):
        agent.forward(body)
    agent.dispatch("CMD_RUN", send=True)
    body = native_forward_body(agent)
    with pytest.raises(ValueError, match="not admitted"):
        agent.forward(dict(body, instance_id="child#1"))
    agent.forward(body)
    assert len(agent.forwarded) == 1


def test_lost_forward_receipt_cannot_retry_the_native_callback(agent, family):
    agent.dispatch("CMD_RUN", send=True)
    real = agent.route

    def lost(payload, **kwargs):
        real.call(payload, **kwargs)
        raise TimeoutError("Injected loss after durable forward admission")

    agent.route = SimpleNamespace(call=lost)
    body = native_forward_body(agent)
    with pytest.raises(TimeoutError):
        agent.forward(body)
    with pytest.raises(ValueError, match="already attempted"):
        agent.forward(body)
    assert not agent.forwarded
    assert (
        family["store"].db.execute("SELECT state FROM native_control_forwards").fetchone()[0]
        == "FORWARD_UNPROVEN"
    )


def consume(family, pki, body):
    return call(family, pki, family["grant"], "control-consume", **body)


def test_consumption_requires_original_forward_and_spends_only_once(journal, family, pki):
    body = operation()
    assert consume(family, pki, body)[0] == 403
    assert admit(family, pki, body)[0] == 200
    assert consume(family, pki, body)[0] == 403
    assert forward(family, pki, body)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: consume(family, pki, body), range(20)))
    assert sum(code == 200 for code, _ in replies) == 1
    assert sum(code == 409 for code, _ in replies) == 19
    result = next(reply["result"] for code, reply in replies if code == 200)
    assert result["state"] == "EXECUTION_UNPROVEN"
    assert result["hold_retained"] and not result["quiescence_proven"]
    assert not result["effective_transfer"] and not result["runtime_enabled"]


def test_stale_forward_cannot_consume_after_controller_fence(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert accept(family)[0]["state"] == "BLOCKED"
    assert consume(family, pki, body)[0] == 403
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0]
        == 0
    )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_consumption_before_fence_is_unproven_and_cannot_release_or_transfer(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert consume(family, pki, body)[0] == 200
    assert accept(family)[0]["state"] == "BLOCKED"
    assert consume(family, pki, body)[0] == 403
    assert (
        family["store"].db.execute("SELECT state FROM native_control_consumptions").fetchone()[0]
        == "EXECUTION_UNPROVEN"
    )
    assert tuple(family["store"].db.execute("SELECT owner,epoch FROM executions").fetchone()) == (
        "alice",
        1,
    )


def test_substituted_consumption_and_audit_failure_cannot_spend_original(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert consume(family, pki, dict(body, target_admission_id=str(uuid.uuid4())))[0] == 403
    assert consume(family, pki, dict(body, command="CMD_STEP"))[0] == 403
    store = family["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert consume(family, pki, body)[0] == 503
    assert store.db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0] == 0
    store.max_events += 10
    assert consume(family, pki, body)[0] == 200


def test_agent_consumption_requires_verified_forward_and_exact_member(agent, family):
    agent.dispatch("CMD_RUN", send=True)
    forwarded = native_forward_body(agent)
    body = dict(forwarded, schema="openbexi.native-consume/1")
    with pytest.raises(ValueError, match="not admitted"):
        agent.consume(body)
    agent.forward(forwarded)
    with pytest.raises(ValueError, match="not admitted"):
        agent.consume(dict(body, instance_id="child#1"))
    agent.consume(body)
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(body)
    assert len(agent.consumed) == 1


@pytest.mark.parametrize("outcome", ["lost", "forged"])
def test_uncertain_or_forged_consumption_reply_never_allows_executor_retry(agent, family, outcome):
    agent.dispatch("CMD_RUN", send=True)
    forwarded = native_forward_body(agent)
    agent.forward(forwarded)
    real = agent.route

    def change(payload, **options):
        reply = real.call(payload, **options)
        if outcome == "lost":
            raise TimeoutError("Injected consumption reply loss")
        return dict(reply, quiescence_proven=True)

    agent.route = SimpleNamespace(call=change)
    body = dict(forwarded, schema="openbexi.native-consume/1")
    with pytest.raises((TimeoutError, ValueError)):
        agent.consume(body)
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(body)
    assert not agent.consumed
    assert (
        family["store"].db.execute("SELECT state FROM native_control_consumptions").fetchone()[0]
        == "EXECUTION_UNPROVEN"
    )


def test_consumption_cannot_use_copied_config_or_revoked_subject(journal, family, pki):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert (
        call(family, pki, family["grant"], "control-consume", **body, runtime_capability="0" * 64)[
            0
        ]
        == 403
    )
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert consume(family, pki, body)[0] == 403
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0]
        == 0
    )


def test_original_forwarded_run_is_denied_at_consumer_after_connection_close(agent, family):
    agent.dispatch("CMD_RUN", send=True)
    body = native_forward_body(agent)
    agent.forward(body)
    assert family["controller"]("session.close", {"connection_id": family["connection"]})["closed"]
    packet = dict(body, schema="openbexi.native-consume/1")
    with pytest.raises(Fault) as denied:
        agent.consume(packet)
    assert denied.value.status == 403
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(packet)
    assert not agent.consumed
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0]
        == 0
    )
    assert tuple(
        family["store"].db.execute("SELECT owner,epoch,control_state FROM executions").fetchone()
    ) == ("alice", 1, "CONTROLLER_DISCONNECTED")
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_original_run_mailbox_disposition_requires_final_consumption(journal, family, pki):
    body = operation()
    extra = dict(body, disposition="HANDLER_RETURNED")
    assert call(family, pki, family["grant"], "control-disposition", **extra)[0] == 403
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert call(family, pki, family["grant"], "control-disposition", **extra)[0] == 403
    assert consume(family, pki, body)[0] == 200
    status, reply = call(family, pki, family["grant"], "control-disposition", **extra)
    assert status == 200
    assert reply["result"] == dict(
        recorded=True, request_id=body["request_id"],
        execution_id=family["grant"].execution_id,
        disposition="HANDLER_RETURNED", state="EXECUTION_UNPROVEN",
        quiescence_proven=False, effective_transfer=False,
        hold_retained=True, runtime_enabled=False,
    )
    assert call(family, pki, family["grant"], "control-disposition", **extra) == (status, reply)
    assert call(
        family, pki, family["grant"], "control-disposition",
        **dict(body, disposition="DISCARDED_PENDING"),
    )[0] == 409
    assert rows(family)[0]["state"] == "DISPATCH_UNCERTAIN"
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("bad", ["COMPLETED", "QUIESCED", True, None])
def test_original_disposition_rejects_false_settlement(journal, family, pki, bad):
    body = operation()
    assert admit(family, pki, body)[0] == 200
    assert forward(family, pki, body)[0] == 200
    assert consume(family, pki, body)[0] == 200
    assert call(
        family, pki, family["grant"], "control-disposition",
        **dict(body, disposition=bad),
    )[0] in (400, 403)
    assert family["store"].db.execute(
        "SELECT COUNT(*) FROM native_control_dispositions"
    ).fetchone()[0] == 0
