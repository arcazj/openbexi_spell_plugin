"""Pending untimed native prompts retain identity across real authority rotation."""

from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import uuid

import pytest

from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.contracts import Fault
from openbexi_spell_server.transport import Route
import test_live_handoff as live
import test_prompt_agent as agents
import test_prompt_authority as protocol
import test_preflight as helpers

source, setup, ledger = live.source, live.setup, live.ledger


def native_relay(ledger, pki):
    children = SimpleNamespace(lock=threading.Lock(), started={"main#1": None})
    session = SimpleNamespace(instance="main#1", request=lambda *a, **k: None)
    request = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(ledger["grant"]),
        runtime_capability=ledger["runtime_capabilities"][ledger["grant"].execution_id],
    )
    route = Route(ledger["config"]["context_url"], pki["context-a"]["pin"], pki["worker"]["client"])
    journal = agents.owners.controls.module.NativeRunJournal(session, request, route, children)
    journal.bound_members["main#1"] = (
        ledger["store"].db.execute("SELECT binding_hash FROM native_members").fetchone()[0]
    )
    relay = agents.module.NativePromptAgent(journal)
    relay.sent = []
    journal.original = lambda *a, **k: relay.sent.append((a, k))
    return relay


def declare(relay, timeout="0"):
    identity = str(uuid.uuid4())
    relay.declare(
        dict(
            schema="openbexi.native-prompt-declare/1",
            instance_id="main#1",
            prompt_id=identity,
            definition={"ProcId": "main#1", "Text": "Continue?", "TimeoutMicroseconds": timeout},
        )
    )
    return dict(
        prompt_id=identity,
        target_admission_id=None,
        definition_sha256=relay.registrations[identity][3],
    )


def prompt_row(ledger):
    return dict(ledger["store"].db.execute("SELECT * FROM native_prompts").fetchone())


def test_unanswered_untimed_prompt_keeps_identity_and_requires_fresh_owner_reply(ledger, pki):
    relay = native_relay(ledger, pki)
    prompt = declare(relay)
    original = prompt_row(ledger)
    assert original["handoff_untimed"] == 1
    _, _, bound, epoch = live.resumed(ledger, pki)
    assert prompt_row(ledger) == original
    for subject in ("alice", "observer", "bob"):
        assert (
            protocol.enqueue(ledger, pki, prompt, subject=subject, **helpers.proof(bound))[0] == 403
        )
    new = live.activate(ledger, pki, epoch)
    ledger["grant"] = start_grant(new["grant"])
    ledger["runtime_capabilities"][ledger["grant"].execution_id] = new["runtime_capability"]
    relay.journal.request.update(grant=new["grant"], runtime_capability=new["runtime_capability"])
    assert protocol.enqueue(ledger, pki, prompt, subject="bob", **helpers.proof(bound))[0] == 200
    delivery = protocol.worker(ledger, pki)[1]["result"]
    grant = delivery["grant"]
    assert grant["control_epoch"] == 2 and grant["owner"] == "bob"
    assert grant["runtime_origin_hash"] == original["origin_hash"]
    for key in ("control_epoch", "connection_id", "connection_generation"):
        with pytest.raises(ValueError, match="provenance"):
            relay.dispatch(dict(grant, **{key: getattr(relay.original, key)}), delivery["answer"])
    assert not relay.sent and not relay.replies
    relay.dispatch(grant, delivery["answer"])
    relay.consume(agents.consume_body(grant))
    relay.close(
        dict(
            schema="openbexi.native-prompt-close/1",
            instance_id="main#1",
            prompt_id=prompt["prompt_id"],
            outcome="ANSWER_SELECTED",
        )
    )
    assert len(relay.sent) == 1
    assert prompt_row(ledger) == dict(original, state="CLOSED", outcome="ANSWER_SELECTED")
    assert protocol.rows(ledger)[0]["epoch"] == 2
    ledger["app"].authority.live_handoff._prompts_settled(ledger["grant"].execution_id)


@pytest.mark.parametrize("timeout", ["1", "-1", "0.0", "", "nan"])
def test_only_exact_native_zero_timeout_is_transferable(ledger, pki, timeout):
    declare(native_relay(ledger, pki), timeout)
    assert prompt_row(ledger)["handoff_untimed"] == 0
    with pytest.raises(AssertionError, match="handoff_prompt_unresolved"):
        live.prepare(ledger, pki)
    assert live.observe(ledger, pki)["control_state"] == "OWNED"


@pytest.mark.parametrize("stage", ["QUEUED", "DELIVERED", "FORWARDED", "CONSUMED", "UNCERTAIN"])
def test_no_admitted_reply_can_cross_handoff_even_on_untimed_prompt(ledger, pki, stage):
    prompt = protocol.opened(ledger, pki, native_timeout_microseconds="0")
    assert protocol.enqueue(ledger, pki, prompt)[0] == 200
    if stage != "QUEUED":
        grant = protocol.worker(ledger, pki)[1]["result"]["grant"]
        if stage in {"FORWARDED", "CONSUMED", "UNCERTAIN"}:
            assert protocol.worker(ledger, pki, "prompt-forward", grant)[0] == 200
        if stage in {"CONSUMED", "UNCERTAIN"}:
            assert protocol.worker(ledger, pki, "prompt-consume", grant)[0] == 200
        if stage == "UNCERTAIN":
            assert (
                protocol.worker(ledger, pki, "prompt-report", grant, outcome="UNCERTAIN")[0] == 200
            )
    before = dict(protocol.rows(ledger)[0])
    with pytest.raises(AssertionError, match="handoff_prompt_unresolved"):
        live.prepare(ledger, pki)
    assert dict(protocol.rows(ledger)[0]) == before
    assert live.observe(ledger, pki)["owner"] == "alice"
    assert live.observe(ledger, pki)["control_state"] == "OWNED"


@pytest.mark.parametrize("outcome", ["UNKNOWN", "FAILED"])
def test_uncertain_native_close_still_blocks_classified_untimed_prompt(ledger, pki, outcome):
    prompt = protocol.opened(ledger, pki, native_timeout_microseconds="0")
    assert (
        protocol.worker(
            ledger, pki, "prompt-close", prompt_id=prompt["prompt_id"], outcome=outcome
        )[0]
        == 200
    )
    with pytest.raises(AssertionError, match="handoff_prompt_unresolved"):
        live.prepare(ledger, pki)


def test_old_prompt_schema_migrates_conservatively_and_restart_fences(ledger, pki):
    protocol.opened(ledger, pki, native_timeout_microseconds="0")
    authority = ledger["app"].authority
    with ledger["store"].transaction():
        ledger["store"].db.execute("ALTER TABLE native_prompts DROP COLUMN handoff_untimed")
        ledger["store"].db.execute("PRAGMA user_version=21")
    authority.native_prompts = None
    protocol.NativePromptReplies(authority)
    assert prompt_row(ledger)["handoff_untimed"] == 0
    assert prompt_row(ledger)["state"] == "RESTART_FENCED"
    assert ledger["store"].db.execute("PRAGMA user_version").fetchone()[0] == 22


def test_uncertain_close_after_acceptance_prevents_host_completion(ledger, pki):
    prompt = protocol.opened(ledger, pki, native_timeout_microseconds="0")
    state, evidence = live.prepare(ledger, pki)
    assert (
        protocol.worker(
            ledger, pki, "prompt-close", prompt_id=prompt["prompt_id"], outcome="UNKNOWN"
        )[0]
        == 200
    )
    with pytest.raises(Fault):
        live.host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=evidence)
    assert live.observe(ledger, pki)["owner"] == "alice"
    assert live.host(ledger, pki, "status")["state"] == "REQUESTED"


def test_reply_admission_and_handoff_acceptance_cannot_both_win(ledger, pki):
    prompt = protocol.opened(ledger, pki, native_timeout_microseconds="0")
    controller = ledger["controller"]
    bob = controller("session.open", {}, subject="bob")["connection_id"]
    claim = controller(
        "execution.claim",
        dict(execution_id=ledger["execution"]["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    start = threading.Barrier(2)

    def accept():
        start.wait(timeout=5)
        try:
            ledger["app"].authority.mutate(
                "alice",
                "execution.decide",
                str(uuid.uuid4()),
                dict(
                    helpers.proof(ledger["execution"]),
                    claim_id=claim["claim_id"],
                    decision="accept",
                ),
            )
            return 200
        except Fault as error:
            assert error.code == "handoff_prompt_unresolved"
            return error.status

    def reply():
        start.wait(timeout=5)
        return protocol.enqueue(ledger, pki, prompt)[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        acceptance, answer = pool.submit(accept), pool.submit(reply)
        result = (acceptance.result(timeout=10), answer.result(timeout=10))
    assert result in {(200, 403), (409, 200)}
