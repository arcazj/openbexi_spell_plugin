"""Private prompt authority over real mTLS, not full native prompt qualification."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import uuid
import pytest
from openbexi_spell_server.contracts import Fault, digest, envelope, policy
from openbexi_spell_server.prompts import NativePromptReplies, prompt_grant
from openbexi_spell_server.control import NativeControlJournal
from test_launch import call
from test_services import request
import test_members as members
import test_preflight as helpers

source = members.source
setup = members.setup
family = members.family


@pytest.fixture
def prompts(family, pki):
    NativeControlJournal(family["app"].authority)
    assert members.bind(family, pki)[0] == 200
    return NativePromptReplies(family["app"].authority)


def opened(family, pki, **changes):
    data = dict(
        prompt_id=str(uuid.uuid4()),
        target_admission_id=None,
        instance_id="main#1",
        definition_sha256=digest({"text": "Continue?"}),
    )
    data.update(changes)
    code, result = call(family, pki, family["grant"], "prompt-open", **data)
    assert code == 200, result
    return data


def enqueue(
    family,
    pki,
    prompt,
    *,
    action="ANSWER",
    answer="yes",
    subject="alice",
    key=None,
    certificate="listener",
    **changes,
):
    body = dict(
        helpers.proof(family["execution"]),
        prompt_id=prompt["prompt_id"],
        target_admission_id=prompt["target_admission_id"],
        definition_sha256=prompt["definition_sha256"],
        action=action,
        answer=answer,
    )
    body.update(changes)
    return request(
        family["server"],
        pki[certificate]["client"],
        "/v1/rpc",
        subject=None,
        payload=envelope("A", subject, "execution.prompt.reply", body, key or str(uuid.uuid4())),
    )


def worker(family, pki, action="prompt-poll", grant=None, **kw):
    if grant is not None:
        kw["prompt_grant"] = grant
    return call(family, pki, family["grant"], action, **kw)


def delivered(family, pki, prompt=None, *, action="ANSWER", answer="yes"):
    prompt = opened(family, pki) if prompt is None else prompt
    assert enqueue(family, pki, prompt, action=action, answer=answer)[0] == 200
    code, body = worker(family, pki)
    assert code == 200 and body["result"]["action"] == "reply"
    return (prompt, body["result"]["grant"], body["result"]["answer"])


def rows(family):
    return (
        family["store"]
        .db.execute("SELECT * FROM native_prompt_replies ORDER BY sequence")
        .fetchall()
    )


def assert_no_release(family, result):
    assert result["runtime_enabled"] is False
    assert result["quiescence_proven"] is False
    assert result["effective_transfer"] is False
    assert result["hold_retained"] is True
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_prompt_routes_stay_closed_by_default(family, pki):
    fake = dict(prompt_id=str(uuid.uuid4()), target_admission_id=None, definition_sha256="a" * 64)
    assert enqueue(family, pki, fake)[0] == 404
    assert worker(family, pki)[0] == 404


@pytest.mark.parametrize("action,answer", [("ANSWER", "yes"), ("CANCEL", None)])
def test_positive_bound_reply_consumes_once_without_settlement(
    prompts, family, pki, action, answer
):
    prompt, grant, value = delivered(family, pki, action=action, answer=answer)
    assert value == answer
    assert prompt_grant(grant).prompt_id == prompt["prompt_id"]
    assert worker(family, pki)[1]["result"]["action"] == "none"
    assert worker(family, pki, "prompt-consume", grant)[0] == 409
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    assert worker(family, pki, "prompt-forward", grant)[0] == 409
    code, response = worker(family, pki, "prompt-consume", grant)
    assert code == 200
    assert_no_release(family, response["result"])
    assert worker(family, pki, "prompt-consume", grant)[0] == 409
    assert rows(family)[0]["state"] == "CONSUMED_UNPROVEN"


def test_answers_and_capabilities_are_not_in_sqlite_or_replay(prompts, family, pki):
    prompt = opened(family, pki)
    answer = "PRIVATE_ANSWER_" + str(uuid.uuid4())
    key = str(uuid.uuid4())
    status, result = enqueue(family, pki, prompt, answer=answer, key=key)
    assert status == 200
    assert answer not in json.dumps(result)
    _, grant, _ = delivered_from_queue(family, pki, prompt)
    replay = enqueue(family, pki, prompt, answer=answer, key=key)
    assert replay[0] == 200 and replay[1]["result"]["replayed"] is True
    dumped = "\n".join(family["store"].db.iterdump())
    for secret in (
        answer,
        grant["token"],
        family["execution"]["capability"],
        family["grant"].token,
    ):
        assert secret not in dumped and secret not in json.dumps(replay)
    assert grant["reply_id"] not in prompts.answers


def delivered_from_queue(family, pki, prompt):
    code, result = worker(family, pki)
    assert code == 200 and result["result"]["action"] == "reply"
    return (prompt, result["result"]["grant"], result["result"]["answer"])


@pytest.mark.parametrize("phase", ["queued", "delivered", "forwarded"])
def test_disconnect_fences_at_every_reply_boundary(prompts, family, pki, phase):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    grant = None
    if phase != "queued":
        _, grant, _ = delivered_from_queue(family, pki, prompt)
    if phase == "forwarded":
        assert worker(family, pki, "prompt-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    if phase == "queued":
        assert worker(family, pki)[1]["result"]["action"] == "hold"
        assert not prompts.answers
    else:
        route = "prompt-consume" if phase == "forwarded" else "prompt-forward"
        assert worker(family, pki, route, grant)[0] == 403
    assert enqueue(family, pki, prompt)[0] == 403


@pytest.mark.parametrize("subject", ["bob", "observer"])
def test_foreign_owner_cannot_reply_with_copied_capability(prompts, family, pki, subject):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt, subject=subject)[0] == 403
    assert not rows(family)


@pytest.mark.parametrize("certificate", ["alice", "bob", "observer", "listener"])
def test_other_certificate_cannot_poll_or_consume(prompts, family, pki, certificate):
    _, grant, _ = delivered(family, pki)
    assert worker(family, pki, certificate=certificate)[0] in (403, 404)
    assert worker(family, pki, "prompt-consume", grant, certificate=certificate)[0] in (403, 404)


def test_one_of_30_competing_replies_wins(prompts, family, pki):
    prompt = opened(family, pki)
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(
            pool.map(lambda n: enqueue(family, pki, prompt, answer=str(n))[0], range(30))
        )
    assert replies.count(200) == 1 and replies.count(409) == 29
    assert len(rows(family)) == 1 and len(prompts.answers) == 1


def test_one_of_30_polls_receives_answer_and_token(prompts, family, pki):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: worker(family, pki), range(30)))
    assert all((code == 200 for code, _ in replies))
    assert sum((body["result"]["action"] == "reply" for _, body in replies)) == 1
    assert not prompts.answers


@pytest.mark.parametrize(
    "changes",
    [
        {"answer": True},
        {"answer": 42},
        {"answer": {}},
        {"answer": ["yes"]},
        {"answer": "\x00bad"},
        {"answer": "\ud800"},
        {"answer": "x" * 4097},
        {"action": "EVAL"},
        {"action": True},
        {"action": "CANCEL", "answer": "yes"},
        {"prompt_id": "not-a-uuid"},
        {"definition_sha256": "not-a-digest"},
        {"target_admission_id": "other"},
        {"extra": "field"},
    ],
)
def test_invalid_answers_and_shapes_never_enter_journal(prompts, family, pki, changes):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt, **changes)[0] in (400, 403, 413)
    assert not rows(family) and (not prompts.answers)


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_id": str(uuid.uuid4())},
        {"definition_sha256": "b" * 64},
        {"target_admission_id": str(uuid.uuid4())},
        {"expected_epoch": 2},
        {"connection_generation": 2},
        {"capability": "0" * 64},
        {"connection_id": str(uuid.uuid4())},
    ],
)
def test_owner_cannot_retarget_or_restamp_prompt(prompts, family, pki, changes):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt, **changes)[0] in (400, 403)
    assert not rows(family)


@pytest.mark.parametrize(
    "change",
    [
        {"prompt_id": str(uuid.uuid4())},
        {"reply_id": str(uuid.uuid4())},
        {"member_binding_hash": "f" * 64},
        {"runtime_origin_hash": "f" * 64},
        {"action": "CANCEL"},
        {"answer_sha256": "f" * 64},
        {"token": "0" * 64},
        {"owner": "bob"},
        {"control_epoch": 2},
        {"expires_at": 10**13},
        {"expires_at": 30},
        {"connection_generation": True},
    ],
)
def test_copied_modified_reply_grant_fails_before_forward(prompts, family, pki, change):
    _, grant, _ = delivered(family, pki)
    assert worker(family, pki, "prompt-forward", dict(grant, **change))[0] in (400, 403)
    assert rows(family)[0]["state"] == "DELIVERY_UNPROVEN"


@pytest.mark.parametrize("phase", ["queued", "delivered", "forwarded"])
def test_expired_reply_never_delivers_or_consumes(prompts, family, pki, phase):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    grant = None
    if phase != "queued":
        _, grant, _ = delivered_from_queue(family, pki, prompt)
    if phase == "forwarded":
        assert worker(family, pki, "prompt-forward", grant)[0] == 200
    deadline = rows(family)[0]["expires_at"]
    family["app"].authority.clock = lambda: deadline
    if phase == "queued":
        assert worker(family, pki)[1]["result"]["action"] == "hold"
        assert not prompts.answers
    else:
        route = "prompt-consume" if phase == "forwarded" else "prompt-forward"
        assert worker(family, pki, route, grant)[0] == 403


def test_identical_owner_replay_is_history_not_a_second_answer(prompts, family, pki):
    prompt = opened(family, pki)
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: enqueue(family, pki, prompt, key=key), range(30)))
    assert all((code == 200 for code, _ in results))
    assert len({v["result"]["reply_id"] for _, v in results}) == 1
    assert len(rows(family)) == 1 and len(prompts.answers) == 1
    assert enqueue(family, pki, prompt, key=key, answer="different")[0] == 409
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert enqueue(family, pki, prompt, key=key)[0] == 403


def close(family, pki, prompt, outcome="TIMEOUT", **changes):
    return worker(
        family, pki, "prompt-close", prompt_id=prompt["prompt_id"], outcome=outcome, **changes
    )


@pytest.mark.parametrize("phase", ["queued", "delivered", "forwarded", "consumed"])
def test_timeout_closes_only_exact_prompt_and_preserves_held_execution(prompts, family, pki, phase):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    grant = None
    if phase != "queued":
        _, grant, _ = delivered_from_queue(family, pki, prompt)
    if phase in ("forwarded", "consumed"):
        assert worker(family, pki, "prompt-forward", grant)[0] == 200
    if phase == "consumed":
        assert worker(family, pki, "prompt-consume", grant)[0] == 200
    code, response = close(family, pki, prompt)
    assert code == 200
    assert_no_release(family, response["result"])
    assert not prompts.answers
    if grant:
        assert worker(family, pki, "prompt-consume", grant)[0] == 403
    assert rows(family)[0]["state"] == (
        "CONSUMED_UNPROVEN" if phase == "consumed" else "CLOSED_UNPROVEN"
    )
    assert close(family, pki, prompt)[0] == 200
    assert close(family, pki, prompt, "FAILED")[0] == 409
    newer = opened(family, pki)
    assert close(family, pki, prompt)[0] == 200
    assert enqueue(family, pki, newer)[0] == 200


def test_native_close_after_disconnect_is_diagnostic_not_resume_permission(prompts, family, pki):
    prompt, grant, _ = delivered(family, pki)
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    assert worker(family, pki, "prompt-consume", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    code, result = close(family, pki, prompt, "ANSWER_SELECTED")
    assert code == 200
    assert_no_release(family, result["result"])
    assert enqueue(family, pki, prompt)[0] == 403


@pytest.mark.parametrize("outcome", ["ANSWER_SELECTED", "CANCEL_SELECTED"])
def test_native_success_report_requires_matching_consumption(prompts, family, pki, outcome):
    prompt = opened(family, pki)
    assert close(family, pki, prompt, outcome)[0] == 403
    assert enqueue(family, pki, prompt)[0] == 200
    _, grant, _ = delivered_from_queue(family, pki, prompt)
    assert close(family, pki, prompt, outcome)[0] == 403
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    assert close(family, pki, prompt, outcome)[0] == 403
    assert worker(family, pki, "prompt-consume", grant)[0] == 200
    assert close(family, pki, prompt, outcome)[0] == (200 if outcome == "ANSWER_SELECTED" else 403)


def test_memory_loss_is_not_an_invitation_to_resubmit_or_reconstruct(prompts, family, pki):
    prompt = opened(family, pki)
    key = str(uuid.uuid4())
    assert enqueue(family, pki, prompt, key=key)[0] == 200
    prompts.answers.clear()
    assert worker(family, pki)[1]["result"]["action"] == "hold"
    assert rows(family)[0]["state"] == "DELIVERY_FENCED"
    assert enqueue(family, pki, prompt, key=key)[0] == 200
    assert not prompts.answers
    assert enqueue(family, pki, prompt)[0] == 409


def test_open_requires_original_registered_member_and_unique_generation(prompts, family, pki):
    prompt = opened(family, pki)
    assert worker(family, pki, "prompt-open", **prompt)[0] == 409
    assert worker(family, pki, "prompt-open", **dict(prompt, prompt_id=str(uuid.uuid4())))[0] == 409
    assert close(family, pki, prompt)[0] == 200
    assert worker(family, pki, "prompt-open", **prompt)[0] == 409
    for changes in ({"instance_id": "child#0"}, {"target_admission_id": str(uuid.uuid4())}):
        assert (
            worker(
                family, pki, "prompt-open", **dict(prompt, prompt_id=str(uuid.uuid4()), **changes)
            )[0]
            == 403
        )


def test_prompt_capacity_retains_tombstones(prompts, family, pki):
    prompts.MAX_PER_EXECUTION = 2
    for _ in range(2):
        p = opened(family, pki)
        assert close(family, pki, p)[0] == 200
    data = dict(
        prompt_id=str(uuid.uuid4()),
        target_admission_id=None,
        instance_id="main#1",
        definition_sha256="a" * 64,
    )
    assert worker(family, pki, "prompt-open", **data)[0] == 503
    assert family["store"].db.execute("SELECT COUNT(*) FROM native_prompts").fetchone()[0] == 2


@pytest.mark.parametrize("phase", ["open", "admit", "poll", "forward", "consume", "close"])
def test_audit_failure_rolls_back_state_and_does_not_grant_action(prompts, family, pki, phase):
    data = dict(
        prompt_id=str(uuid.uuid4()),
        target_admission_id=None,
        instance_id="main#1",
        definition_sha256="a" * 64,
    )
    grant = None
    if phase != "open":
        assert worker(family, pki, "prompt-open", **data)[0] == 200
    if phase in ("poll", "forward", "consume", "close"):
        assert enqueue(family, pki, data)[0] == 200
    if phase in ("forward", "consume"):
        _, grant, _ = delivered_from_queue(family, pki, data)
    if phase == "consume":
        assert worker(family, pki, "prompt-forward", grant)[0] == 200
    store = family["store"]
    before = list(store.db.iterdump())
    memory = dict(prompts.answers)
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if phase == "open":
        result = worker(family, pki, "prompt-open", **data)
    elif phase == "admit":
        result = enqueue(family, pki, data)
    elif phase == "poll":
        result = worker(family, pki)
    elif phase == "close":
        result = close(family, pki, data)
    else:
        result = worker(family, pki, "prompt-" + phase, grant)
    assert result[0] == 503
    assert list(store.db.iterdump()) == before
    assert prompts.answers == memory


def test_prompt_intent_retires_unused_initial_run_lane(prompts, family, pki):
    import test_control as controls

    p = opened(family, pki)
    assert enqueue(family, pki, p)[0] == 200
    assert controls.admit(family, pki, controls.operation())[0] == 403


def test_consumption_racing_close_has_one_durable_order(prompts, family, pki):
    p, grant, _ = delivered(family, pki)
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        consumed = pool.submit(worker, family, pki, "prompt-consume", grant)
        closed = pool.submit(close, family, pki, p)
        assert closed.result()[0] == 200
        assert consumed.result()[0] in (200, 403)
    assert worker(family, pki, "prompt-consume", grant)[0] == 403
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("phase", ["queued", "delivered", "forwarded"])
def test_live_permission_revocation_denies_later_reply_stages(prompts, family, pki, phase):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    grant = None
    if phase != "queued":
        _, grant, _ = delivered_from_queue(family, pki, prompt)
    if phase == "forwarded":
        assert worker(family, pki, "prompt-forward", grant)[0] == 200
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert enqueue(family, pki, prompt)[0] == 403
    if phase == "queued":
        assert worker(family, pki)[1]["result"]["action"] == "hold"
    else:
        assert (
            worker(
                family, pki, "prompt-consume" if phase == "forwarded" else "prompt-forward", grant
            )[0]
            == 403
        )


def test_restart_fences_original_prompt_and_all_delivered_reply_proofs(prompts, family, pki):
    from openbexi_spell_server.authority import ExecutionAuthority
    from openbexi_spell_server.store import ContextStore

    prompt, grant, _ = delivered(family, pki)
    before = [dict(row) for row in rows(family)]
    old = family["store"]
    directory = Path(old.db.execute("PRAGMA database_list").fetchone()[2]).parent
    old.close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(store, family["app"].subjects)
        NativeControlJournal(authority)
        restarted = NativePromptReplies(authority)
        assert not restarted.answers
        after = [dict(r) for r in store.db.execute("SELECT * FROM native_prompt_replies")]
        assert after == [dict(r, state="RESTART_FENCED") for r in before]
        assert (
            store.db.execute("SELECT state FROM native_prompts").fetchone()[0] == "RESTART_FENCED"
        )
        with pytest.raises(Fault):
            restarted.poll(family["grant"])
        with pytest.raises(Fault):
            restarted.advance(family["grant"], prompt_grant(grant), "forward")
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        store.close()


def test_registered_child_prompt_cannot_receive_root_answer_or_startup_authority(
    prompts, family, pki
):
    import test_family as families
    import test_control as controls

    child = families.admit(family, pki)[1]["result"]["child_grant"]
    assert families.consume(family, pki, child)[0] == 200
    assert (
        members.bind(
            family,
            pki,
            members.member(
                target_admission_id=child["admission_id"], instance_id="child#0", pid=1235
            ),
        )[0]
        == 200
    )
    parent = opened(family, pki)
    descendant = opened(
        family, pki, target_admission_id=child["admission_id"], instance_id="child#0"
    )
    assert enqueue(family, pki, parent)[0] == 200
    assert enqueue(family, pki, descendant, target_admission_id=None)[0] == 403
    assert (
        controls.admit(
            family, pki, dict(controls.operation(), target_admission_id=child["admission_id"])
        )[0]
        == 200
    )
    assert enqueue(family, pki, descendant)[0] == 200
    assert (
        controls.admit(
            family, pki, dict(controls.operation(), target_admission_id=child["admission_id"])
        )[0]
        == 403
    )
    _, root_grant, _ = delivered_from_queue(family, pki, parent)
    _, child_grant, _ = delivered_from_queue(family, pki, descendant)
    assert root_grant["member_binding_hash"] != child_grant["member_binding_hash"]
    assert (
        worker(family, pki, "prompt-forward", dict(root_grant, prompt_id=child_grant["prompt_id"]))[
            0
        ]
        == 403
    )
    assert worker(family, pki, "prompt-forward", child_grant)[0] == 200
    assert worker(family, pki, "prompt-consume", child_grant)[0] == 200


def test_memory_answer_tampering_is_detected_before_delivery(prompts, family, pki):
    prompt = opened(family, pki)
    assert enqueue(family, pki, prompt)[0] == 200
    reply_id = rows(family)[0]["reply_id"]
    prompts.answers[reply_id] = "changed-in-memory"
    assert worker(family, pki)[1]["result"]["action"] == "hold"
    assert not prompts.answers
    assert rows(family)[0]["state"] == "DELIVERY_FENCED"


def test_no_public_gateway_or_listener_authority_route_is_added():
    from openbexi_spell_server.contracts import AUTHORITY_MUTATIONS, METHODS

    assert "execution.prompt.reply" not in AUTHORITY_MUTATIONS
    assert "execution.prompt.reply" not in METHODS
    root = Path(__file__).resolve().parents[2]
    policy_text = (root / "host_runtime/native/mutation_policy.H").read_text()
    assert 'if (id == "MSG_ANSWER" || id == "MSG_CANCEL") return true;' in policy_text


def test_disconnected_owner_cannot_reopen_a_closed_prompt(prompts, family, pki):
    prompt = opened(family, pki)
    assert close(family, pki, prompt)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert worker(family, pki, "prompt-open", **dict(prompt, prompt_id=str(uuid.uuid4())))[0] == 403


def test_dispatch_reports_after_disconnect_do_not_authorize_replay(prompts, family, pki):
    prompt, grant, _ = delivered(family, pki)
    assert worker(family, pki, "prompt-report", grant, outcome="UNCERTAIN")[0] == 403
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    code, body = worker(family, pki, "prompt-report", grant, outcome="UNCERTAIN")
    assert code == 200
    assert_no_release(family, body["result"])
    assert worker(family, pki, "prompt-report", grant, outcome="UNCERTAIN")[0] == 200
    assert worker(family, pki, "prompt-report", grant, outcome="IPC_SEND_ACKNOWLEDGED")[0] == 409
    assert worker(family, pki, "prompt-report", grant, outcome="COMPLETED")[0] == 403
    assert worker(family, pki, "prompt-consume", grant)[0] == 403
    assert rows(family)[0]["state"] == "FORWARD_UNPROVEN"
    assert rows(family)[0]["diagnostic"] == "UNCERTAIN"


def test_cancel_selection_is_a_bound_report_not_a_procedure_abort_proof(prompts, family, pki):
    prompt, grant, _ = delivered(family, pki, action="CANCEL", answer=None)
    assert worker(family, pki, "prompt-forward", grant)[0] == 200
    assert worker(family, pki, "prompt-consume", grant)[0] == 200
    code, body = close(family, pki, prompt, "CANCEL_SELECTED")
    assert code == 200
    assert_no_release(family, body["result"])
    assert (
        family["store"].db.execute("SELECT lifecycle FROM executions").fetchone()[0] == "STARTING"
    )
    assert rows(family)[0]["state"] == "CONSUMED_UNPROVEN"
