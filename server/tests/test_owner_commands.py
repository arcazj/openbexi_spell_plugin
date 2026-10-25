"""Fresh owner admission over real mTLS; native command effects are qualified separately."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.commands import NativeOwnerCommands, owner_command_grant
from openbexi_spell_server.contracts import Fault, envelope, policy
from openbexi_spell_server.control import NativeControlJournal
from openbexi_spell_server.store import ContextStore
from test_launch import call
from test_services import request
import test_members as members
import test_preflight as helpers
import test_control as controls
import test_child_gate as gates

source = members.source
setup = members.setup
family = members.family
provider = gates.provider


@pytest.fixture
def queue(family, pki):
    NativeControlJournal(family["app"].authority)
    assert members.bind(family, pki)[0] == 200
    return NativeOwnerCommands(family["app"].authority)


@pytest.fixture
def agent(queue, provider, family):
    sent = []
    session = SimpleNamespace(
        instance="main#1", request=lambda *args, **kwargs: sent.append((args, kwargs))
    )
    result = controls.module.NativeRunJournal(session, provider.request, provider.route, provider)
    result.bound_members["main#1"] = (
        family["store"].db.execute("SELECT binding_hash FROM native_members").fetchone()[0]
    )
    result.sent = sent
    return result


def enqueue(
    family,
    pki,
    command="CMD_STEP",
    *,
    subject="alice",
    key=None,
    body=None,
    certificate="listener",
    **changes,
):
    payload = (
        dict(helpers.proof(family["execution"]), target_admission_id=None, command=command)
        if body is None
        else dict(body)
    )
    payload.update(changes)
    return request(
        family["server"],
        pki[certificate]["client"],
        "/v1/rpc",
        subject=None,
        payload=envelope("A", subject, "execution.command", payload, key or str(uuid.uuid4())),
    )


def worker(family, pki, action="command-poll", grant=None, **changes):
    if grant is not None:
        changes["command_grant"] = grant
    return call(family, pki, family["grant"], action, **changes)


def delivered(family, pki, command="CMD_STEP"):
    assert enqueue(family, pki, command)[0] == 200
    code, reply = worker(family, pki)
    assert code == 200 and reply["result"]["action"] == "command"
    return reply["result"]["grant"]


def rows(family):
    return (
        family["store"]
        .db.execute("SELECT * FROM native_owner_commands ORDER BY sequence")
        .fetchall()
    )


def test_commands_and_worker_routes_are_disabled_by_default(family, pki):
    assert enqueue(family, pki)[0] == 404
    for action in ("command-poll", "command-forward", "command-consume", "command-report"):
        assert worker(family, pki, action, {} if action != "command-poll" else None)[0] == 404


def test_owner_proof_is_distinct_from_startup_grant(queue, family, pki):
    assert worker(family, pki)[1]["result"]["action"] == "none"
    assert (
        call(
            family,
            pki,
            family["grant"],
            "control-admit",
            request_id=str(uuid.uuid4()),
            target_admission_id=None,
            command="CMD_STEP",
        )[0]
        == 403
    )
    assert enqueue(family, pki, certificate="worker")[0] in (403, 404)
    assert not rows(family)


@pytest.mark.parametrize("command", ["CMD_RUN", "CMD_STEP", "CMD_PAUSE"])
def test_owner_can_queue_and_deliver_command_only_once(queue, family, pki, command):
    grant = delivered(family, pki, command)
    assert owner_command_grant(grant).command == command
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"
    assert worker(family, pki)[1]["result"]["action"] == "none"
    assert worker(family, pki, "command-consume", grant)[0] == 409
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-forward", grant)[0] == 409
    code, reply = worker(family, pki, "command-consume", grant)
    assert code == 200 and reply["result"]["state"] == "EXECUTION_UNPROVEN"
    assert worker(family, pki, "command-consume", grant)[0] == 409
    assert all(
        reply["result"][key] is False
        for key in ("quiescence_proven", "effective_transfer", "runtime_enabled")
    )
    text = "\n".join(family["store"].db.iterdump())
    assert grant["token"] not in text
    assert family["grant"].token not in text
    assert family["execution"]["capability"] not in text
    assert family["runtime_capabilities"][family["grant"].execution_id] not in text


def test_100_duplicate_owner_requests_queue_one_intent(queue, family, pki):
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: enqueue(family, pki, key=key), range(100)))
    assert all(code == 200 for code, _ in replies)
    assert len({reply["result"]["command_id"] for _, reply in replies}) == 1
    assert len(rows(family)) == 1
    assert enqueue(family, pki, "CMD_PAUSE", key=key)[0] == 409


def test_concurrent_polls_do_not_redeliver_a_token(queue, family, pki):
    assert enqueue(family, pki)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: worker(family, pki), range(20)))
    assert all(code == 200 for code, _ in replies)
    assert sum(reply["result"]["action"] == "command" for _, reply in replies) == 1
    assert sum(reply["result"]["action"] == "none" for _, reply in replies) == 19


@pytest.mark.parametrize("certificate", ["alice", "bob", "observer", "listener"])
def test_only_original_worker_can_poll_forward_consume_or_report(queue, family, pki, certificate):
    grant = delivered(family, pki)
    for action in ("command-poll", "command-forward", "command-consume", "command-report"):
        body = {} if action == "command-poll" else dict(command_grant=grant)
        if action == "command-report":
            body["outcome"] = "UNCERTAIN"
        assert call(family, pki, family["grant"], action, certificate=certificate, **body)[0] in (
            403,
            404,
        )
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


def test_copied_worker_config_without_memory_proof_cannot_receive_owner_grant(queue, family, pki):
    assert enqueue(family, pki)[0] == 200
    assert worker(family, pki, runtime_capability="0" * 64)[0] == 403
    assert rows(family)[0]["state"] == "QUEUED"


def test_non_owner_and_observer_cannot_enqueue_even_with_copied_owner_proof(queue, family, pki):
    family["app"].authority.subjects["observer"] = policy({"observer": ["execution:read"]})[
        "observer"
    ]
    assert enqueue(family, pki, subject="bob")[0] == 403
    assert enqueue(family, pki, subject="observer")[0] == 403
    assert not rows(family)


@pytest.mark.parametrize(
    "change",
    [
        dict(command="CMD_STEP_OVER"),
        dict(command="CMD_SCRIPT"),
        dict(command=[]),
        dict(command=True),
        dict(expected_epoch=True),
        dict(connection_generation=0),
        dict(capability="0" * 64),
        dict(target_admission_id=False),
        dict(target_admission_id=str(uuid.uuid4())),
        dict(parameters={}),
    ],
)
def test_owner_command_fields_are_closed_and_scoped(queue, family, pki, change):
    code, _ = enqueue(family, pki, **change)
    assert code in (400, 403)
    assert not rows(family)


@pytest.mark.parametrize(
    "change",
    [
        dict(token="0" * 64),
        dict(owner="bob"),
        dict(control_epoch=2),
        dict(control_epoch=True),
        dict(worker_slot="two"),
        dict(member_binding_hash="0" * 64),
        dict(runtime_origin_hash="0" * 64),
        dict(command_id=str(uuid.uuid4())),
        dict(command="CMD_SCRIPT"),
        dict(command=[]),
        dict(expires_at=1),
        dict(quiescence_proven=True),
    ],
)
def test_forged_or_type_substituted_grants_cannot_forward(queue, family, pki, change):
    grant = delivered(family, pki)
    assert worker(family, pki, "command-forward", dict(grant, **change))[0] in (400, 403)
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


@pytest.mark.parametrize("phase", ["queued", "delivered", "forwarded"])
def test_disconnect_fences_original_command_at_every_stage(queue, family, pki, phase):
    assert enqueue(family, pki)[0] == 200
    grant = None
    if phase != "queued":
        grant = worker(family, pki)[1]["result"]["grant"]
    if phase == "forwarded":
        assert worker(family, pki, "command-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    if phase == "queued":
        assert worker(family, pki)[1]["result"]["action"] == "hold"
        assert rows(family)[0]["state"] == "DELIVERY_FENCED"
    else:
        assert (
            worker(
                family, pki, "command-consume" if phase == "forwarded" else "command-forward", grant
            )[0]
            == 403
        )
    row = family["app"].authority.list_executions("alice")["executions"][0]
    assert (row["owner"], row["epoch"], row["control_state"]) == (
        "alice",
        1,
        "CONTROLLER_DISCONNECTED",
    )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_live_authorization_precedes_owner_request_replay(queue, family, pki):
    key = str(uuid.uuid4())
    assert enqueue(family, pki, key=key)[0] == 200
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert enqueue(family, pki, key=key)[0] == 403
    assert worker(family, pki)[1]["result"]["action"] == "hold"
    assert rows(family)[0]["state"] == "DELIVERY_FENCED"


def test_revoked_start_permission_cannot_step_but_owner_can_request_main_pause(queue, family, pki):
    family["app"].authority.subjects["alice"] = policy(
        {"alice": ["execution:control", "execution:read"]}
    )["alice"]
    assert enqueue(family, pki)[0] == 403
    assert enqueue(family, pki, "CMD_RUN")[0] == 403
    grant = delivered(family, pki, "CMD_PAUSE")
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 200


@pytest.mark.parametrize("phase", ["queued", "delivered"])
def test_expiry_cannot_reissue_or_consume_old_command(queue, family, pki, phase):
    assert enqueue(family, pki)[0] == 200
    grant = None if phase == "queued" else worker(family, pki)[1]["result"]["grant"]
    now = family["app"].authority.clock()
    family["app"].authority.clock = lambda: now + 31
    if phase == "queued":
        assert worker(family, pki)[1]["result"]["action"] == "hold"
        assert rows(family)[0]["state"] == "DELIVERY_FENCED"
    else:
        assert worker(family, pki, "command-forward", grant)[0] == 403
        assert worker(family, pki)[1]["result"]["action"] == "none"
        assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


def test_diagnostics_after_disconnect_are_not_settlement_or_command_authority(queue, family, pki):
    grant = delivered(family, pki)
    assert worker(family, pki, "command-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert worker(family, pki, "command-report", grant, outcome="UNCERTAIN")[0] == 200
    assert worker(family, pki, "command-report", grant, outcome="UNCERTAIN")[0] == 200
    assert worker(family, pki, "command-report", grant, outcome="IPC_SEND_ACKNOWLEDGED")[0] == 409
    assert worker(family, pki, "command-report", grant, outcome="COMPLETED")[0] == 403
    assert rows(family)[0]["state"] == "FORWARD_UNPROVEN"
    assert worker(family, pki, "command-consume", grant)[0] == 403


def test_enqueue_and_delivery_audit_failures_do_not_issue_permission(queue, family, pki):
    store = family["store"]
    limit = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    store.max_events = limit
    assert enqueue(family, pki)[0] == 503
    assert not rows(family)
    store.max_events = limit + 10
    assert enqueue(family, pki)[0] == 200
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert worker(family, pki)[0] == 503
    assert rows(family)[0]["state"] == "QUEUED" and rows(family)[0]["grant_hash"] is None


def test_restart_preserves_queued_and_delivered_rows_but_fences_every_grant(queue, family, pki):
    delivered(family, pki)
    assert enqueue(family, pki, "CMD_PAUSE")[0] == 200
    before = [dict(row) for row in rows(family)]
    old = family["store"]
    directory = Path(old.db.execute("PRAGMA database_list").fetchone()[2]).parent
    old.close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(store, family["app"].subjects)
        NativeControlJournal(authority)
        restarted = NativeOwnerCommands(authority)
        after = [
            dict(row)
            for row in store.db.execute("SELECT * FROM native_owner_commands ORDER BY sequence")
        ]
        assert after == [dict(row, state="RESTART_FENCED") for row in before]
        with pytest.raises(Fault):
            restarted.poll(family["grant"])
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        store.close()


def owner_callback(grant, stage="forward", **changes):
    return dict(
        dict(
            schema="openbexi.native-control/1"
            if stage == "forward"
            else "openbexi.native-consume/1",
            instance_id="main#1",
            request_id=grant["command_id"],
            command=grant["command"],
        ),
        **changes,
    )


def test_agent_keeps_owner_grant_before_send_and_verifies_both_native_phases(agent, family, pki):
    grant = delivered(family, pki)
    agent.dispatch_owner(grant)
    assert agent.sent == [
        (
            ("CMD_STEP", {"V08ControlRequest": grant["command_id"]}),
            dict(send=True, procedure="main#1"),
        )
    ]
    with pytest.raises(ValueError, match="not verified"):
        agent.consume(owner_callback(grant, "consume"))
    with pytest.raises(ValueError, match="identity differs"):
        agent.forward(owner_callback(grant, instance_id="child#0"))
    agent.forward(owner_callback(grant))
    agent.consume(owner_callback(grant, "consume"))
    assert grant["command_id"] in agent.owner_consumed
    with pytest.raises(ValueError, match="already attempted"):
        agent.dispatch_owner(grant)
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(owner_callback(grant, "consume"))


@pytest.mark.parametrize("phase", ["forward", "consume"])
@pytest.mark.parametrize("failure", ["lost", "forged"])
def test_owner_native_reply_loss_or_substitution_never_retries(agent, family, pki, phase, failure):
    grant = delivered(family, pki)
    agent.dispatch_owner(grant)
    if phase == "consume":
        agent.forward(owner_callback(grant))
    route = agent.route

    def changed(payload, **options):
        answer = route.call(payload, **options)
        if failure == "lost":
            raise TimeoutError("Injected owner grant response loss")
        return dict(answer, quiescence_proven=True)

    agent.route = SimpleNamespace(call=changed)
    callback = agent.forward if phase == "forward" else agent.consume
    with pytest.raises((TimeoutError, ValueError)):
        callback(owner_callback(grant, phase))
    with pytest.raises(ValueError, match="already attempted"):
        callback(owner_callback(grant, phase))
    assert rows(family)[0]["state"] == (
        "FORWARD_UNPROVEN" if phase == "forward" else "EXECUTION_UNPROVEN"
    )


def test_delivered_owner_command_stays_original_after_disconnect(agent, family, pki):
    grant = delivered(family, pki)
    agent.dispatch_owner(grant)
    agent.forward(owner_callback(grant))
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    with pytest.raises(Fault) as denied:
        agent.consume(owner_callback(grant, "consume"))
    assert denied.value.status == 403
    assert grant["command_id"] not in agent.owner_consumed
    assert rows(family)[0]["state"] == "FORWARD_UNPROVEN"
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(owner_callback(grant, "consume"))


def test_agent_refuses_substituted_member_binding_before_native_send(agent, family, pki):
    grant = delivered(family, pki)
    agent.bound_members["main#1"] = "0" * 64
    with pytest.raises(ValueError, match="member binding"):
        agent.dispatch_owner(grant)
    assert not agent.sent and not agent.owner_operations


def test_command_poll_response_loss_never_redelivers_grant(agent, family, pki):
    assert enqueue(family, pki)[0] == 200
    route = agent.route

    def lost(payload, **options):
        route.call(payload, **options)
        raise TimeoutError("Injected delivery response loss")

    agent.route = SimpleNamespace(call=lost)
    with pytest.raises(TimeoutError):
        agent.poll_owner()
    agent.route = route
    assert agent.poll_owner() == "none"
    assert not agent.sent and not agent.owner_operations
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


def test_uncertain_native_send_preserves_grant_and_cannot_retry(agent, family, pki):
    grant = delivered(family, pki)
    sends = []

    def lost(*args, **kwargs):
        sends.append((args, kwargs))
        raise TimeoutError("Injected native IPC response loss")

    agent.original = lost
    with pytest.raises(TimeoutError):
        agent.dispatch_owner(grant)
    with pytest.raises(ValueError, match="already attempted"):
        agent.dispatch_owner(grant)
    assert len(sends) == 1
    assert rows(family)[0]["diagnostic"] == "UNCERTAIN"
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


def test_child_command_requires_its_exact_consumed_registered_member(queue, family, pki):
    assert enqueue(family, pki, target_admission_id=str(uuid.uuid4()))[0] == 403
    child = members.families.admit(family, pki)[1]["result"]["child_grant"]
    target = child["admission_id"]
    assert enqueue(family, pki, target_admission_id=target)[0] == 403
    assert members.families.consume(family, pki, child)[0] == 200
    assert (
        members.bind(
            family, pki, members.member(target_admission_id=target, instance_id="child#0", pid=1235)
        )[0]
        == 200
    )
    assert enqueue(family, pki, target_admission_id=target)[0] == 200
    code, answer = worker(family, pki)
    assert code == 200
    grant = answer["result"]["grant"]
    assert grant["target_admission_id"] == target
    assert (
        grant["member_binding_hash"]
        != family["store"]
        .db.execute("SELECT binding_hash FROM native_members WHERE target_id=''")
        .fetchone()[0]
    )
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 409


def test_pending_command_capacity_cannot_discard_or_replace_old_intents(queue, family, pki):
    for _ in range(64):
        assert enqueue(family, pki)[0] == 200
    before = [(row["command_id"], row["state"]) for row in rows(family)]
    assert enqueue(family, pki)[0] == 503
    assert before == [(row["command_id"], row["state"]) for row in rows(family)]


def test_fresh_run_does_not_reuse_or_restamp_startup_authority(queue, family, pki):
    original = (
        family["store"]
        .db.execute(
            "SELECT start_hash,start_binding,epoch,connection_id FROM executions WHERE id=?",
            (family["grant"].execution_id,),
        )
        .fetchone()
    )
    first = delivered(family, pki, "CMD_RUN")
    assert worker(family, pki, "command-forward", first)[0] == 200
    assert worker(family, pki, "command-consume", first)[0] == 200
    second = delivered(family, pki, "CMD_RUN")
    assert first["command_id"] != second["command_id"] and first["token"] != second["token"]
    assert worker(family, pki, "command-forward", second)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert worker(family, pki, "command-consume", second)[0] == 403
    current = (
        family["store"]
        .db.execute(
            "SELECT start_hash,start_binding,epoch,connection_id FROM executions WHERE id=?",
            (family["grant"].execution_id,),
        )
        .fetchone()
    )
    assert tuple(original) == tuple(current)
    assert [row["state"] for row in rows(family)] == ["EXECUTION_UNPROVEN", "FORWARD_UNPROVEN"]


@pytest.mark.parametrize("command", ["CMD_RUN", "CMD_STEP", "CMD_PAUSE"])
@pytest.mark.parametrize("phase", ["unused", "admitted", "forwarded"])
def test_owner_intent_retires_unused_and_pending_startup_run(queue, family, pki, command, phase):
    initial = controls.operation()
    if phase != "unused":
        assert controls.admit(family, pki, initial)[0] == 200
    if phase == "forwarded":
        assert controls.forward(family, pki, initial)[0] == 200
    assert enqueue(family, pki, command)[0] == 200
    assert controls.admit(family, pki, controls.operation())[0] == 403
    assert controls.forward(family, pki, initial)[0] == 403
    assert controls.consume(family, pki, initial)[0] == 403
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0]
        == 0
    )
    grant = worker(family, pki)[1]["result"]["grant"]
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 200


def test_expired_owner_intent_cannot_reopen_startup_run(queue, family, pki):
    assert enqueue(family, pki)[0] == 200
    clock = family["app"].authority.clock()
    family["app"].authority.clock = lambda: clock + 31
    assert worker(family, pki)[1]["result"]["action"] == "hold"
    assert rows(family)[0]["state"] == "DELIVERY_FENCED"
    assert controls.admit(family, pki)[0] == 403


def test_failed_owner_intent_cannot_half_retire_startup_run(queue, family, pki):
    store = family["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert enqueue(family, pki)[0] == 503
    assert not rows(family)
    store.max_events += 100
    initial = controls.operation()
    assert controls.admit(family, pki, initial)[0] == 200
    assert controls.forward(family, pki, initial)[0] == 200
    assert controls.consume(family, pki, initial)[0] == 200


def test_startup_retirement_is_per_member_and_keeps_child_initial_run(queue, family, pki):
    assert enqueue(family, pki, "CMD_PAUSE")[0] == 200
    child = members.families.admit(family, pki)[1]["result"]["child_grant"]
    target = child["admission_id"]
    assert members.families.consume(family, pki, child)[0] == 200
    assert (
        members.bind(
            family, pki, members.member(target_admission_id=target, instance_id="child#0", pid=1235)
        )[0]
        == 200
    )
    child_initial = dict(controls.operation(), target_admission_id=target)
    assert controls.admit(family, pki)[0] == 403
    assert controls.admit(family, pki, child_initial)[0] == 200
    assert controls.forward(family, pki, child_initial)[0] == 200
    assert controls.consume(family, pki, child_initial)[0] == 200
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_control_consumptions").fetchone()[0]
        == 1
    )


def test_initial_consume_and_owner_intent_have_one_durable_order(queue, family, pki):
    initial = controls.operation()
    assert controls.admit(family, pki, initial)[0] == 200
    assert controls.forward(family, pki, initial)[0] == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        consuming = pool.submit(controls.consume, family, pki, initial)
        owner = pool.submit(enqueue, family, pki, "CMD_PAUSE")
        consumed = consuming.result()[0]
        assert owner.result()[0] == 200
    assert consumed in (200, 403)
    events = [
        row[0] for row in family["store"].db.execute("SELECT type FROM events ORDER BY sequence")
    ]
    if consumed == 200:
        assert events.index("NATIVE_CONTROL_CONSUMPTION_ADMITTED") < events.index(
            "OWNER_COMMAND_ADMITTED"
        )
    else:
        assert "NATIVE_CONTROL_CONSUMPTION_ADMITTED" not in events
    assert controls.consume(family, pki, initial)[0] == 403
