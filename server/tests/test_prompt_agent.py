"""Prompt relay uses actual Context mTLS; IPC callbacks here are controlled fixtures."""

from dataclasses import asdict
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid
import pytest
from openbexi_spell_server.contracts import Fault, digest
import test_prompt_authority as protocol
import test_owner_commands as owners
import test_child_gate as native_gate

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "candidate_prompt_agent", ROOT / "host_runtime/python/prompt_replies.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = protocol.source
setup = protocol.setup
family = protocol.family
prompts = protocol.prompts
provider = native_gate.provider


@pytest.fixture
def relay(prompts, provider, family):
    session = SimpleNamespace(instance="main#1", request=lambda *a, **k: None)
    journal = owners.controls.module.NativeRunJournal(
        session, provider.request, provider.route, provider
    )
    journal.bound_members["main#1"] = (
        family["store"].db.execute("SELECT binding_hash FROM native_members").fetchone()[0]
    )
    result = module.NativePromptAgent(journal)
    result.sent = []
    journal.original = lambda *a, **k: result.sent.append((a, k))
    return result


def open_native(relay):
    body = dict(
        schema="openbexi.native-prompt-open/1",
        instance_id="main#1",
        prompt_id=str(uuid.uuid4()),
        definition_sha256=digest({"text": "Reply?"}),
    )
    relay.register(body)
    return dict(body, target_admission_id=None)


def consume_body(grant, answer="yes", **changes):
    value = dict(
        schema="openbexi.native-prompt-consume/1",
        instance_id="main#1",
        prompt_id=grant["prompt_id"],
        reply_id=grant["reply_id"],
        action=grant["action"],
        answer=answer,
    )
    value.update(changes)
    return value


def queued(relay, family, pki, action="ANSWER", answer="yes"):
    native = open_native(relay)
    assert protocol.enqueue(family, pki, native, action=action, answer=answer)[0] == 200
    return native


@pytest.mark.parametrize("action,answer", [("ANSWER", "yes"), ("CANCEL", None)])
def test_exact_native_wire_fields_and_single_delivery(relay, family, pki, action, answer):
    native = queued(relay, family, pki, action, answer)
    assert relay.poll() == "reply"
    assert relay.poll() == "none"
    assert len(relay.sent) == 1
    (command, fields), options = relay.sent[0]
    assert command == ("MSG_ANSWER" if action == "ANSWER" else "MSG_CANCEL")
    assert fields["V08PromptId"] == native["prompt_id"]
    assert options == dict(send=True, procedure="main#1")
    assert set(fields) == (
        {"V08PromptId", "V08PromptRequest", "ReturnValue"}
        if action == "ANSWER"
        else {"V08PromptId", "V08PromptRequest"}
    )
    if action == "ANSWER":
        assert fields["ReturnValue"] == answer
    grant = asdict(next(iter(relay.replies.values()))[1])
    relay.consume(consume_body(grant, answer))
    with pytest.raises(ValueError, match="already attempted"):
        relay.consume(consume_body(grant, answer))
    assert protocol.rows(family)[0]["state"] == "CONSUMED_UNPROVEN"


def test_synchronous_consumption_during_ipc_does_not_deadlock(relay, family, pki):
    queued(relay, family, pki)

    def native_callback(command, fields, **options):
        grant = asdict(relay.replies[fields["V08PromptRequest"]][1])
        relay.consume(consume_body(grant, fields["ReturnValue"]))
        relay.sent.append(command)

    relay.journal.original = native_callback
    assert relay.poll() == "reply"
    assert relay.sent == ["MSG_ANSWER"]


@pytest.mark.parametrize(
    "changes",
    [
        {"instance_id": "child#0"},
        {"prompt_id": str(uuid.uuid4())},
        {"reply_id": str(uuid.uuid4())},
        {"action": "CANCEL", "answer": None},
        {"answer": "changed"},
        {"other": "unexpected"},
    ],
)
def test_native_callback_binding_is_exact_before_consumption(relay, family, pki, changes):
    queued(relay, family, pki)
    relay.poll()
    grant = asdict(next(iter(relay.replies.values()))[1])
    with pytest.raises((ValueError, Fault)):
        relay.consume(consume_body(grant, **changes))
    assert protocol.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


@pytest.mark.parametrize("phase", ["open", "forward", "consume", "close"])
def test_lost_authority_ack_never_retries_the_operation(relay, family, pki, phase):
    native = None
    if phase != "open":
        native = queued(relay, family, pki)
    grant = None
    if phase in ("consume", "close"):
        relay.poll()
        grant = asdict(next(iter(relay.replies.values()))[1])
    original = relay.journal.route
    calls = []

    def dropped(payload, **kwargs):
        calls.append(kwargs["path"])
        original.call(payload, **kwargs)
        raise TimeoutError("lost after durable commit")

    relay.journal.route = SimpleNamespace(call=dropped)
    if phase == "open":
        body = dict(
            schema="openbexi.native-prompt-open/1",
            instance_id="main#1",
            prompt_id=str(uuid.uuid4()),
            definition_sha256="a" * 64,
        )

        def invoke():
            return relay.register(body)
    elif phase == "forward":
        relay.journal.route = original
        _, grant, value = protocol.delivered_from_queue(family, pki, native)
        relay.journal.route = SimpleNamespace(call=dropped)

        def invoke():
            return relay.dispatch(grant, value)
    elif phase == "consume":

        def invoke():
            return relay.consume(consume_body(grant))
    else:
        body = dict(
            schema="openbexi.native-prompt-close/1",
            instance_id="main#1",
            prompt_id=native["prompt_id"],
            outcome="TIMEOUT",
        )

        def invoke():
            return relay.close(body)

    with pytest.raises(TimeoutError):
        invoke()
    with pytest.raises(ValueError, match="attempted|pending"):
        invoke()
    assert len(calls) == 1
    if phase == "forward":
        assert not relay.sent


def test_uncertain_physical_send_cannot_be_retried(relay, family, pki):
    native = queued(relay, family, pki)
    _, grant, value = protocol.delivered_from_queue(family, pki, native)
    attempts = []

    def uncertain(*a, **k):
        attempts.append(a)
        raise TimeoutError("native send uncertain")

    relay.journal.original = uncertain
    with pytest.raises(TimeoutError):
        relay.dispatch(grant, value)
    with pytest.raises(ValueError, match="already attempted"):
        relay.dispatch(grant, value)
    assert len(attempts) == 1 and protocol.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


def test_changed_answer_or_receipt_never_reaches_native(relay, family, pki):
    native = queued(relay, family, pki)
    _, grant, value = protocol.delivered_from_queue(family, pki, native)
    with pytest.raises(ValueError, match="answer differs"):
        relay.dispatch(grant, "other")
    real = relay.journal.route

    def forged(payload, **kw):
        result = real.call(payload, **kw)
        return dict(result, quiescence_proven=True)

    relay.journal.route = SimpleNamespace(call=forged)
    with pytest.raises(ValueError, match="receipt differs"):
        relay.dispatch(grant, value)
    assert not relay.sent
    assert protocol.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


def test_close_reuse_and_delayed_old_callback_cannot_touch_next_prompt(relay, family, pki):
    native = queued(relay, family, pki)
    relay.poll()
    grant = asdict(next(iter(relay.replies.values()))[1])
    relay.close(
        dict(
            schema="openbexi.native-prompt-close/1",
            instance_id="main#1",
            prompt_id=native["prompt_id"],
            outcome="TIMEOUT",
        )
    )
    newer = open_native(relay)
    with pytest.raises(ValueError):
        relay.consume(consume_body(grant))
    assert relay.active["main#1"] == newer["prompt_id"]
    with pytest.raises(ValueError):
        relay.register({k: v for k, v in native.items() if k != "target_admission_id"})


def test_context_process_cannot_impersonate_native_prompt_origin(relay):
    server = native_gate.module.NativeAdmissionServer.__new__(
        native_gate.module.NativeAdmissionServer
    )
    server.prompts = relay
    server.report = lambda *a, **k: None
    message = dict(
        schema="openbexi.native-prompt-open/1",
        instance_id="main#1",
        prompt_id=str(uuid.uuid4()),
        definition_sha256="a" * 64,
    )
    for role, instance in [("context", None), ("executor", "other#1")]:
        with pytest.raises(ValueError, match="origin"):
            server.dispatch(role, instance, message)
    assert not relay.open_attempted
    server.prompts = None
    with pytest.raises(ValueError, match="profile"):
        server.dispatch("executor", "main#1", message)


def test_role_checked_dispatch_reaches_prompt_adapter(relay):
    server = native_gate.module.NativeAdmissionServer.__new__(
        native_gate.module.NativeAdmissionServer
    )
    server.prompts = relay
    server.report = lambda *a, **k: None
    message = dict(
        schema="openbexi.native-prompt-open/1",
        instance_id="main#1",
        prompt_id=str(uuid.uuid4()),
        definition_sha256="a" * 64,
    )
    server.dispatch("executor", "main#1", message)
    assert message["prompt_id"] in relay.registrations
