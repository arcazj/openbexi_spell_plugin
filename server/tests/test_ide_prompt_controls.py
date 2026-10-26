"""Pinned installed-client transport through the private prompt-reply edge."""

import uuid

import pytest

from openbexi_runtime.spell_server_client import SpellServerError
from openbexi_spell_server.launch import start_grant
import test_ide_native_controls as native
import test_live_handoff as live
import test_prompt_authority as prompts
import test_preflight as helpers

source, setup, ledger, desktop = native.source, native.setup, native.ledger, native.desktop


def reply(desktop, prompt, *, subject="alice", proof=None, key=None, **changes):
    ledger = desktop["ledger"]
    payload = dict(
        helpers.proof(ledger["execution"]) if proof is None else proof,
        prompt_id=prompt["prompt_id"],
        target_admission_id=prompt["target_admission_id"],
        definition_sha256=prompt["definition_sha256"],
        action="ANSWER",
        answer="yes",
    )
    payload.update(changes)
    return desktop["clients"][subject].request(
        "POST",
        "/v1/contexts/A/authority",
        {"method": "execution.prompt.reply", "payload": payload},
        key=key or str(uuid.uuid4()),
    )["result"]


def test_private_prompt_reply_crosses_all_tls_hops_once(desktop, pki):
    ledger = desktop["ledger"]
    prompt = prompts.opened(ledger, pki)
    first = reply(desktop, prompt, key="original")
    assert reply(desktop, prompt, key="original") == dict(first, replayed=True)
    assert len(prompts.rows(ledger)) == 1
    delivery = prompts.worker(ledger, pki)[1]["result"]
    assert delivery["action"] == "reply" and delivery["answer"] == "yes"
    assert delivery["grant"]["owner"] == "alice"
    assert prompts.worker(ledger, pki)[1]["result"]["action"] == "none"


@pytest.mark.parametrize("subject", ["bob", "observer"])
def test_stolen_prompt_proof_cannot_change_authenticated_subject(desktop, pki, subject):
    ledger = desktop["ledger"]
    prompt = prompts.opened(ledger, pki)
    with pytest.raises(SpellServerError) as error:
        reply(desktop, prompt, subject=subject)
    assert error.value.status == 403 and not prompts.rows(ledger)


@pytest.mark.parametrize("disabled", ["listener", "context"])
def test_prompt_route_requires_both_private_opt_ins(desktop, pki, disabled):
    ledger = desktop["ledger"]
    prompt = prompts.opened(ledger, pki)
    if disabled == "listener":
        desktop["listener"].native_command_contexts = frozenset()
    else:
        ledger["app"].authority.native_prompts = None
    with pytest.raises(SpellServerError) as error:
        reply(desktop, prompt)
    assert error.value.status == 404 and not prompts.rows(ledger)


@pytest.mark.parametrize(
    "changes", [{"expected_epoch": 2}, {"definition_sha256": "f" * 64}, {"owner": "alice"}]
)
def test_stale_or_changed_prompt_proof_is_not_admitted(desktop, pki, changes):
    ledger = desktop["ledger"]
    prompt = prompts.opened(ledger, pki)
    with pytest.raises(SpellServerError) as error:
        reply(desktop, prompt, **changes)
    assert error.value.status in {400, 403} and not prompts.rows(ledger)


def test_installed_client_answers_original_prompt_only_after_new_owner_activation(desktop, pki):
    ledger = desktop["ledger"]
    prompt = prompts.opened(ledger, pki, native_timeout_microseconds="0")
    _, _, bound, epoch = live.resumed(ledger, pki)
    proof = helpers.proof(bound)
    with pytest.raises(SpellServerError) as error:
        reply(desktop, prompt, subject="bob", proof=proof)
    assert error.value.status == 403
    new = live.activate(ledger, pki, epoch)
    ledger["grant"] = start_grant(new["grant"])
    ledger["runtime_capabilities"][ledger["grant"].execution_id] = new["runtime_capability"]
    with pytest.raises(SpellServerError) as error:
        reply(desktop, prompt)
    assert error.value.status == 403
    assert reply(desktop, prompt, subject="bob", proof=proof)["admitted"]
    grant = prompts.worker(ledger, pki)[1]["result"]["grant"]
    assert grant["owner"] == "bob" and grant["control_epoch"] == 2
