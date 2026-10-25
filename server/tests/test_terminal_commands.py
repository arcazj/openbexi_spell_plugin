"""Actual Context/mTLS single-use terminal authorization; native effects tested separately."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import uuid

import pytest

from openbexi_spell_server.commands import NativeOwnerCommands, owner_command_grant
from openbexi_spell_server.contracts import Fault
from openbexi_spell_server.control import NativeControlJournal
from openbexi_spell_server.prompts import NativePromptReplies
from test_launch import call
import test_owner_commands as owners
import test_members as members
import test_control as controls
import test_child_gate as gates

setup, family = members.setup, members.family


@pytest.fixture
def source(tmp_path):
    value = members.source.__wrapped__(tmp_path)
    for entry in value["config"].values():
        entry["driver_binding"] = "context-audit"
    return value


provider = gates.provider


@pytest.fixture
def terminal(family, pki):
    NativeControlJournal(family["app"].authority)
    assert members.bind(family, pki)[0] == 200
    NativePromptReplies(family["app"].authority)
    return NativeOwnerCommands(family["app"].authority, terminal=True)


def consume(family, pki, grant, status="RUNNING", prompt=None, **changes):
    body = dict(command_grant=grant, native_status=status, prompt_id=prompt)
    body.update(changes)
    return call(family, pki, family["grant"], "terminal-consume", **body)


def forward(family, pki, command="CMD_ABORT"):
    grant = owners.delivered(family, pki, command)
    assert owners.worker(family, pki, "command-forward", grant)[0] == 200
    return grant


@pytest.mark.parametrize(
    "command,status",
    [
        ("CMD_ABORT", "RUNNING"),
        ("CMD_CLOSE", "FINISHED"),
        ("CMD_CLOSE", "ABORTED"),
        ("CMD_CLOSE", "ERROR"),
    ],
)
def test_terminal_token_consumed_before_effects_and_never_reused(
    terminal, family, pki, command, status
):
    grant = forward(family, pki, command)
    assert owners.worker(family, pki, "command-consume", grant)[0] == 403
    code, response = consume(family, pki, grant, status)
    assert code == 200 and response["result"]["state"] == "EXECUTION_UNPROVEN"
    assert response["result"]["hold_retained"] is True
    assert response["result"]["quiescence_proven"] is False
    assert response["result"]["effective_transfer"] is False
    assert consume(family, pki, grant, status)[0] in (403, 409)
    db = family["store"].db
    assert db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    with pytest.raises(Fault, match="terminal_effects_fenced"):
        family["app"].authority.validate_start_grant(family["grant"])
    for command in ("CMD_RUN", "CMD_STEP", "CMD_PAUSE"):
        assert owners.enqueue(family, pki, command)[0] == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("token", "0" * 64),
        ("command_id", str(uuid.uuid4())),
        ("control_epoch", 2),
        ("member_binding_hash", "0" * 64),
        ("operation_digest", "0" * 64),
        ("connection_id", str(uuid.uuid4())),
        ("authority_incarnation", str(uuid.uuid4())),
        ("command", "CMD_CLOSE"),
        ("target_admission_id", str(uuid.uuid4())),
    ],
)
def test_terminal_grant_fields_are_cryptographically_bound(terminal, family, pki, field, value):
    grant = forward(family, pki)
    assert consume(family, pki, dict(grant, **{field: value}))[0] in (400, 403, 409)
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 0
    )
    assert consume(family, pki, grant)[0] == 200


@pytest.mark.parametrize(
    "status", ["RUNNING", "PAUSED", "PROMPT", "LOADED", "WAITING", "UNKNOWN", True, None]
)
def test_close_requires_native_terminal_status_before_setclosing(terminal, family, pki, status):
    grant = forward(family, pki, "CMD_CLOSE")
    assert consume(family, pki, grant, status)[0] in (400, 403, 409)
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 0
    )


def test_terminal_concurrent_consumption_is_one_winner(terminal, family, pki):
    grant = forward(family, pki)
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: consume(family, pki, grant)[0], range(16)))
    assert statuses.count(200) == 1
    assert all(status in (200, 403, 409) for status in statuses)
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 1
    )


@pytest.mark.parametrize("fence", ["disconnect", "epoch", "permission", "expiry"])
def test_terminal_live_authority_is_rechecked_at_cif_consumption(terminal, family, pki, fence):
    grant = forward(family, pki)
    if fence == "disconnect":
        family["controller"]("session.close", dict(connection_id=family["connection"]))
    elif fence == "epoch":
        family["store"].db.execute("UPDATE executions SET epoch=epoch+1")
    elif fence == "permission":
        family["app"].authority.subjects.pop("alice")
    else:
        family["app"].authority.clock = lambda: grant["expires_at"] + 1
    assert consume(family, pki, grant)[0] == 403
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 0
    )


def test_terminal_prompt_binding_is_exact_and_cannot_cancel_another_generation(
    terminal, family, pki
):
    prompt_id = str(uuid.uuid4())
    status, _ = call(
        family,
        pki,
        family["grant"],
        "prompt-open",
        prompt_id=prompt_id,
        target_admission_id=None,
        instance_id="main#1",
        definition_sha256="d" * 64,
    )
    assert status == 200
    grant = forward(family, pki)
    assert consume(family, pki, grant, "PROMPT", None)[0] == 403
    assert consume(family, pki, grant, "PROMPT", str(uuid.uuid4()))[0] == 403
    assert consume(family, pki, grant, "PROMPT", prompt_id)[0] == 200
    # Original native cancellation can report UNKNOWN after ABORT. It cannot
    # pretend that an independently owner-admitted prompt CANCEL was consumed.
    assert (
        call(
            family,
            pki,
            family["grant"],
            "prompt-close",
            prompt_id=prompt_id,
            outcome="CANCEL_SELECTED",
        )[0]
        == 403
    )
    assert (
        call(family, pki, family["grant"], "prompt-close", prompt_id=prompt_id, outcome="UNKNOWN")[
            0
        ]
        == 200
    )


def test_terminal_event_channel_is_only_original_member_lifecycle(terminal, family, pki):
    grant = forward(family, pki)
    assert consume(family, pki, grant)[0] == 200
    for message, expected in [
        ("Procedure finished: main#1 at test", 200),
        ("Procedure finished: foreign#1 at test", 403),
        ("arbitrary user payload", 403),
    ]:
        assert (
            call(
                family,
                pki,
                family["grant"],
                "terminal-event",
                request_id=str(uuid.uuid4()),
                message=message,
                severity=8,
                scope=1,
            )[0]
            == expected
        )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_terminal_audit_failure_rolls_back_consumption_and_intent(
    terminal, family, pki, monkeypatch
):
    grant = forward(family, pki)
    original = family["store"]._event

    def fail(kind, body):
        if kind == "NATIVE_TERMINAL_ADMISSION_CONSUMED":
            raise Fault(503, "audit_capacity_reached")
        return original(kind, body)

    monkeypatch.setattr(family["store"], "_event", fail)
    assert consume(family, pki, grant)[0] == 503
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 0
    )
    assert owners.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


def test_real_relay_never_retries_terminal_after_lost_consumption_reply(
    terminal, family, pki, provider
):
    grant = forward(family, pki)
    session = SimpleNamespace(instance="main#1", request=lambda *a, **k: None)
    agent = controls.module.NativeRunJournal(
        session, provider.request, provider.route, provider, terminal=True
    )
    obj = owner_command_grant(grant, allow_terminal=True)
    agent.owner_operations[obj.command_id] = ("main#1", obj)
    agent.owner_forwarded.add(obj.command_id)
    route, attempts = agent.route, []

    def lost(body, **options):
        attempts.append(body)
        route.call(body, **options)
        raise TimeoutError("lost committed reply")

    agent.route = SimpleNamespace(call=lost)
    body = dict(
        schema="openbexi.native-terminal-consume/1",
        instance_id="main#1",
        request_id=obj.command_id,
        command="CMD_ABORT",
        native_status="RUNNING",
        prompt_id=None,
    )
    with pytest.raises(TimeoutError):
        agent.consume_terminal(body)
    with pytest.raises(ValueError):
        agent.consume_terminal(body)
    assert len(attempts) == 1
    assert (
        family["store"].db.execute("SELECT COUNT(*) FROM native_terminal_intents").fetchone()[0]
        == 1
    )
    assert obj.command_id not in agent.owner_consumed


def test_native_prompt_cancel_fences_effects_before_scheduler_abort(terminal, family, pki):
    import test_prompt_authority as prompts

    pending, grant, _ = prompts.delivered(family, pki, action="CANCEL", answer=None)
    assert prompts.worker(family, pki, "prompt-forward", grant)[0] == 200
    assert prompts.worker(family, pki, "prompt-consume", grant)[0] == 200
    assert terminal.effects_fenced(family["grant"].execution_id)
    with pytest.raises(Fault, match="terminal_effects_fenced"):
        family["app"].authority.validate_start_grant(family["grant"])
    assert owners.enqueue(family, pki, "CMD_RUN")[0] == 403
    assert prompts.enqueue(family, pki, pending)[0] == 403
    assert (
        prompts.worker(
            family, pki, "prompt-close", prompt_id=pending["prompt_id"], outcome="CANCEL_SELECTED"
        )[0]
        == 200
    )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert (
        family["store"].db.execute("SELECT command FROM native_terminal_intents").fetchone()[0]
        == "MSG_CANCEL"
    )
