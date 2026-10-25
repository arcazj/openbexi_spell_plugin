"""Actual owner-grant verification over mTLS; no caller 'verified' booleans."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import uuid

import pytest

from openbexi_spell_server.commands import NativeOwnerCommands
from openbexi_spell_server.control import NativeControlJournal
import test_owner_commands as owner
import test_members as members
import test_control as controls
import test_child_gate as gates

source = owner.source
setup = owner.setup
family = owner.family
provider = owner.provider


@pytest.fixture
def terminal(family, pki):
    NativeControlJournal(family["app"].authority)
    assert members.bind(family, pki)[0] == 200
    return NativeOwnerCommands(family["app"].authority, terminal_commands=True)


@pytest.fixture
def agent(terminal, provider, family):
    session = SimpleNamespace(instance="main#1", request=lambda *a, **k: {})
    journal = controls.module.NativeRunJournal(
        session, provider.request, provider.route, provider, terminal_commands=True
    )
    journal.bound_members["main#1"] = (
        family["store"].db.execute("SELECT binding_hash FROM native_members").fetchone()[0]
    )
    return journal


def delivered(family, pki, operation="CMD_ABORT"):
    return owner.delivered(family, pki, operation)


def callback(grant, stage="preprocess", **changes):
    return dict(
        schema="openbexi.native-terminal/1",
        instance_id="main#1",
        command=grant["command"],
        request_id=grant["command_id"],
        stage=stage,
        **changes,
    )


def prepare(agent, family, pki, operation="CMD_ABORT"):
    grant = delivered(family, pki, operation)
    agent.dispatch_owner(grant)
    agent.forward(
        dict(
            schema="openbexi.native-control/1",
            instance_id="main#1",
            command=operation,
            request_id=grant["command_id"],
        )
    )
    return grant


@pytest.mark.parametrize("operation", ["CMD_ABORT", "CMD_CLOSE"])
def test_terminal_owner_queue_is_explicitly_disabled_by_default(family, pki, operation):
    NativeControlJournal(family["app"].authority)
    assert members.bind(family, pki)[0] == 200
    NativeOwnerCommands(family["app"].authority)
    assert owner.enqueue(family, pki, operation)[0] == 403
    assert owner.rows(family) == []


@pytest.mark.parametrize("operation", ["CMD_ABORT", "CMD_CLOSE"])
def test_exact_capability_two_durable_single_use_boundaries(terminal, family, pki, operation):
    grant = delivered(family, pki, operation)
    assert owner.worker(family, pki, "command-consume", grant)[0] == 409
    assert owner.worker(family, pki, "command-terminal-execute", grant)[0] == 409
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    assert (
        owner.worker(family, pki, "command-consume", grant)[1]["result"]["state"]
        == "TERMINAL_PREPROCESSED_UNPROVEN"
    )
    assert owner.worker(family, pki, "command-consume", grant)[0] == 409
    code, receipt = owner.worker(family, pki, "command-terminal-execute", grant)
    assert code == 200 and receipt["result"]["state"] == "EXECUTION_UNPROVEN"
    assert owner.worker(family, pki, "command-terminal-execute", grant)[0] == 409
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    text = "\n".join(family["store"].db.iterdump())
    assert grant["token"] not in text and family["execution"]["capability"] not in text
    assert all(
        receipt["result"][k] is False
        for k in ("effective_transfer", "quiescence_proven", "runtime_enabled")
    )


@pytest.mark.parametrize("stage", ["command-consume", "command-terminal-execute"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("token", "0" * 64),
        ("execution_id", str(uuid.uuid4())),
        ("command_id", str(uuid.uuid4())),
        ("member_binding_hash", "0" * 64),
        ("control_epoch", 99),
        ("connection_id", str(uuid.uuid4())),
        ("worker_generation", 99),
        ("worker_incarnation", "other"),
        ("runtime_origin_hash", "0" * 64),
        ("command", "CMD_CLOSE"),
        ("operation_digest", "0" * 64),
        ("target_admission_id", str(uuid.uuid4())),
        ("authority_incarnation", str(uuid.uuid4())),
        ("owner", "bob"),
    ],
)
def test_altered_cryptographic_binding_has_no_transition(
    terminal, family, pki, stage, field, value
):
    grant = delivered(family, pki)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    if stage == "command-terminal-execute":
        assert owner.worker(family, pki, "command-consume", grant)[0] == 200
    before = dict(owner.rows(family)[0])
    forged = {**grant, field: value}
    assert owner.worker(family, pki, stage, forged)[0] in (400, 403)
    assert dict(owner.rows(family)[0]) == before


@pytest.mark.parametrize("stage", ["command-consume", "command-terminal-execute"])
@pytest.mark.parametrize("reason", ["disconnect", "expiry", "revocation", "restart"])
def test_live_owner_and_authority_checked_at_each_boundary(terminal, family, pki, stage, reason):
    grant = delivered(family, pki)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    if stage == "command-terminal-execute":
        assert owner.worker(family, pki, "command-consume", grant)[0] == 200
    if reason == "disconnect":
        family["controller"]("session.close", dict(connection_id=family["connection"]))
    elif reason == "expiry":
        family["app"].authority.clock = lambda: grant["expires_at"] + 1
    elif reason == "revocation":
        family["app"].authority.subjects["alice"] = type(family["app"].authority.subjects["alice"])(
            "alice", frozenset()
        )
    else:
        with family["store"].transaction():
            family["store"].db.execute("UPDATE native_owner_commands SET state='RESTART_FENCED'")
    assert owner.worker(family, pki, stage, grant)[0] in (403, 409)
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("certificate", ["alice", "bob", "observer", "listener"])
def test_only_consumed_original_worker_can_present_the_grant(terminal, family, pki, certificate):
    grant = delivered(family, pki)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    for stage in ("command-consume", "command-terminal-execute"):
        assert owner.worker(family, pki, stage, grant, certificate=certificate)[0] in (403, 404)
    assert owner.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


@pytest.mark.parametrize("stage", ["command-consume", "command-terminal-execute"])
def test_concurrent_duplicate_grants_have_one_durable_winner(terminal, family, pki, stage):
    grant = delivered(family, pki)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    if stage.endswith("execute"):
        assert owner.worker(family, pki, "command-consume", grant)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: owner.worker(family, pki, stage, grant)[0], range(32)))
    assert codes.count(200) == 1 and codes.count(409) == 31


@pytest.mark.parametrize("stage", ["command-consume", "command-terminal-execute"])
def test_audit_failure_rolls_back_and_returns_no_permission(terminal, family, pki, stage):
    grant = delivered(family, pki)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    if stage.endswith("execute"):
        assert owner.worker(family, pki, "command-consume", grant)[0] == 200
    before = dict(owner.rows(family)[0])
    store = family["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert owner.worker(family, pki, stage, grant)[0] == 503
    assert dict(owner.rows(family)[0]) == before


@pytest.mark.parametrize("operation", ["CMD_ABORT", "CMD_CLOSE"])
def test_agent_real_rpc_and_no_replay(agent, family, pki, operation):
    grant = prepare(agent, family, pki, operation)
    with pytest.raises(ValueError, match="pre-effect"):
        agent.consume(
            {
                k: v
                for k, v in {**callback(grant), "schema": "openbexi.native-consume/1"}.items()
                if k != "stage"
            }
        )
    agent.terminal(callback(grant))
    assert owner.rows(family)[0]["state"] == "TERMINAL_PREPROCESSED_UNPROVEN"
    with pytest.raises(ValueError, match="already attempted"):
        agent.terminal(callback(grant))
    agent.terminal(callback(grant, "execute"))
    with pytest.raises(ValueError, match="already attempted"):
        agent.terminal(callback(grant, "execute"))
    assert owner.rows(family)[0]["state"] == "EXECUTION_UNPROVEN"


@pytest.mark.parametrize("stage", ["preprocess", "execute"])
def test_lost_rpc_ack_never_retries_single_use_permission(agent, family, pki, stage):
    grant = prepare(agent, family, pki)
    if stage == "execute":
        agent.terminal(callback(grant))
    route = agent.route
    calls = []

    def lost(payload, **options):
        calls.append(options["path"])
        route.call(payload, **options)
        raise TimeoutError("receipt lost after durable commit")

    agent.route = SimpleNamespace(call=lost)
    with pytest.raises(TimeoutError):
        agent.terminal(callback(grant, stage))
    agent.route = route
    with pytest.raises(ValueError):
        agent.terminal(callback(grant, stage))
    assert len(calls) == 1
    assert owner.rows(family)[0]["state"] == (
        "EXECUTION_UNPROVEN" if stage == "execute" else "TERMINAL_PREPROCESSED_UNPROVEN"
    )


@pytest.mark.parametrize("role,instance", [("context", "main#1"), ("executor", "child#1")])
def test_local_dispatch_rejects_wrong_peer_before_authority(agent, family, pki, role, instance):
    grant = prepare(agent, family, pki)
    server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
    server.controls = agent
    server.report = lambda *a, **k: None
    with pytest.raises(ValueError, match="peer or member"):
        server.dispatch(role, instance, callback(grant))
    assert owner.rows(family)[0]["state"] == "FORWARD_UNPROVEN"
