"""Independent host mTLS, immutable container binding, and terminal reclamation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import uuid

import pytest

from openbexi_spell_server.contracts import Fault, canonical
from openbexi_spell_server.control import NativeControlJournal
from openbexi_spell_server.commands import NativeOwnerCommands
from openbexi_spell_server.effects import DriverGate, EffectAdmission
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.launch import WorkerLaunch
from openbexi_spell_server.prompts import NativePromptReplies
from openbexi_spell_server.settlement import TerminalSettlement
from openbexi_spell_server.pause import NativePauseBarrier
from openbexi_spell_server.services import Context
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.worker import preflight
from test_launch import call
from test_services import request, serving
from authority_test_helpers import accept
import test_family as families
import test_members as members
import test_owner_commands as owners
import test_preflight as helpers
import test_effects as effects
import test_prompt_authority as prompts

setup = families.setup
dss = effects.dss


@pytest.fixture
def source(tmp_path, request):
    result = families.source.__wrapped__(tmp_path)
    for entry in result["config"].values():
        entry["driver_binding"] = getattr(request, "param", "context-audit")
    return result


def configure(setup, pki):
    app = setup["app"]
    app.launch = WorkerLaunch(app.preflight)
    FamilyAdmission(app.authority, app.catalog)
    NativeControlJournal(app.authority)
    NativeOwnerCommands(app.authority, terminal=True)
    NativePromptReplies(app.authority)
    app.settlement = TerminalSettlement(
        app.authority,
        dict(profile="single-host-terminal-candidate", fingerprint=pki["host"]["pin"]),
        excluded_pins={pki["listener"]["pin"], pki["worker"]["pin"]},
    )


def host(setup, pki, action, *, certificate="host", **body):
    return request(
        setup["server"],
        pki[certificate]["client"],
        "/v1/host/terminal/" + action,
        subject=None,
        payload=dict(
            schema=TerminalSettlement.SCHEMA,
            context_id="A",
            execution_id=setup["execution"]["id"],
            authority_incarnation=setup["store"].incarnation,
            **body,
        ),
    )


def bind(setup, pki, **changes):
    return host(
        setup,
        pki,
        "bind",
        **dict(
            dict(
                container_id="c" * 64, image=setup["source"]["config"]["procedure"]["runtime_image"]
            ),
            **changes,
        ),
    )


def start(setup, pki):
    preflight(setup["config"])
    setup["grant"] = setup["app"].authority.admit_start("alice", helpers.proof(setup["execution"]))
    return call(setup, pki, setup["grant"])[0]


@pytest.fixture
def ledger(setup, pki):
    configure(setup, pki)
    assert bind(setup, pki)[0] == 200
    assert start(setup, pki) == 200
    assert members.bind(setup, pki)[0] == 200
    return setup


def begin(ledger, pki, status="FINISHED"):
    code, answer = host(ledger, pki, "begin", container_id="c" * 64, native_status=status)
    assert code == 200, answer
    return answer["result"]


def complete(ledger, pki, fence, **changes):
    evidence = dict(
        provider="docker-pidfd-terminal/1",
        container_id="c" * 64,
        image=ledger["source"]["config"]["procedure"]["runtime_image"],
        running=False,
        pid=0,
        exit_code=0,
        oom_killed=False,
        restart_count=0,
        original_handles=3,
        exited_handles=3,
        roster_hash=fence["roster_hash"],
    )
    evidence.update(changes)
    return host(ledger, pki, "complete", challenge=fence["challenge"], evidence=evidence)


def release(ledger, pki, result):
    return host(
        ledger, pki, "release", challenge=result["challenge"], report_hash=result["report_hash"]
    )


def held(ledger):
    return (
        ledger["store"]
        .db.execute(
            "SELECT COUNT(*) FROM reservations WHERE execution_id=?", (ledger["execution"]["id"],)
        )
        .fetchone()[0]
    )


def test_no_consumption_without_host_prelaunch_container_binding(setup, pki):
    configure(setup, pki)
    assert start(setup, pki) == 403
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0
    assert bind(setup, pki)[0] == 200
    assert call(setup, pki, setup["grant"])[0] == 200


@pytest.mark.parametrize("certificate", ["worker", "listener", "alice", "bob", "observer"])
def test_worker_and_browser_certificates_cannot_attest_terminal_proof(ledger, pki, certificate):
    for action, body in (
        ("bind", dict(container_id="c" * 64, image="sha256:" + "a" * 64)),
        ("begin", dict(container_id="c" * 64, native_status="CLOSED")),
        ("complete", dict(challenge=str(uuid.uuid4()), evidence={})),
        ("release", dict(challenge=str(uuid.uuid4()), report_hash="a" * 64)),
    ):
        assert host(ledger, pki, action, certificate=certificate, **body)[0] in (403, 404)
    assert held(ledger) == 1


def test_binding_is_immutable_and_late_binding_is_denied(ledger, pki):
    assert bind(ledger, pki, container_id="d" * 64)[0] == 403
    assert host(ledger, pki, "begin", container_id="d" * 64, native_status="CLOSED")[0] == 403
    assert held(ledger) == 1


@pytest.mark.parametrize("status", ["FINISHED", "ERROR", "ABORTED", "CLOSED"])
def test_known_terminal_releases_only_proven_reservations_and_never_reuses_worker(
    ledger, pki, status
):
    fence = begin(ledger, pki, status)
    code, answer = complete(ledger, pki, fence)
    assert code == 200 and answer["result"]["state"] == "SETTLED"
    assert held(ledger) == 1
    result = answer["result"]
    assert result["report"]["effects_settled"] is True
    code, released = release(ledger, pki, result)
    assert code == 200 and released["result"]["state"] == "RELEASED"
    assert released["result"]["worker_reusable"] is False
    assert held(ledger) == 0
    assert release(ledger, pki, result) == (code, released)
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert (
        ledger["store"].db.execute("SELECT spent FROM workers WHERE slot='one'").fetchone()[0] == 1
    )
    reserved = ledger["controller"](
        "execution.reserve",
        dict(
            procedure_id="procedure",
            connection_id=ledger["connection"],
            **{
                k: json.loads(
                    ledger["store"]
                    .db.execute("SELECT inventory FROM executions LIMIT 1")
                    .fetchone()[0]
                )[k]
                for k in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
            },
        ),
    )
    row = ledger["app"].authority._execution(reserved["id"])
    assert row["worker_slot"] == "two" and row["id"] != ledger["execution"]["id"]


def test_unknown_loss_keeps_hold_even_after_all_processes_exit(ledger, pki):
    fence = begin(ledger, pki, "UNKNOWN")
    code, answer = complete(ledger, pki, fence)
    assert code == 200 and answer["result"]["state"] == "HELD"
    assert "native_outcome_unknown" in answer["result"]["report"]["reasons"]
    assert release(ledger, pki, answer["result"])[0] == 409
    assert held(ledger) == 1


def test_pending_prompt_outcome_retains_reservations_after_process_exit(ledger, pki):
    prompts.opened(ledger, pki)
    fence = begin(ledger, pki)
    answer = complete(ledger, pki, fence)[1]["result"]
    assert answer["state"] == "HELD"
    assert "prompt_outcome_unresolved" in answer["report"]["reasons"]
    assert release(ledger, pki, answer)[0] == 409


@pytest.mark.parametrize("outcome", ["UNKNOWN", "FAILED"])
def test_closed_but_unresolved_prompt_outcome_cannot_release(ledger, pki, outcome):
    prompt = prompts.opened(ledger, pki)
    assert (
        prompts.worker(ledger, pki, "prompt-close", prompt_id=prompt["prompt_id"], outcome=outcome)[
            0
        ]
        == 200
    )
    fence = begin(ledger, pki)
    answer = complete(ledger, pki, fence)[1]["result"]
    assert answer["state"] == "HELD"
    assert "prompt_outcome_unresolved" in answer["report"]["reasons"]
    assert release(ledger, pki, answer)[0] == 409


def test_terminal_fence_retires_pending_transfer_without_giving_claimant_control(ledger, pki):
    pause = NativePauseBarrier(ledger["app"].authority)
    assert accept(ledger)[0]["state"] == "PAUSING"
    fence = begin(ledger, pki)
    answer = complete(ledger, pki, fence)[1]["result"]
    assert answer["state"] == "SETTLED" and answer["effective_transfer"] is False
    ledger["app"].authority.clock = lambda: 1e12
    pause.expire()
    row = ledger["app"].authority._execution(ledger["execution"]["id"])
    assert row["owner"] == "alice" and row["control_state"] == "TERMINATED"
    assert ledger["store"].db.execute("SELECT state FROM claims").fetchone()[0] == "INVALIDATED"


@pytest.mark.parametrize("phase", ["FENCED", "SETTLED", "RELEASED"])
def test_restart_keeps_reclamation_decision_and_cannot_replay_old_proof(ledger, pki, phase):
    fence = begin(ledger, pki)
    result = fence
    if phase != "FENCED":
        result = complete(ledger, pki, fence)[1]["result"]
    if phase == "RELEASED":
        assert release(ledger, pki, result)[0] == 200
    # Reopen the actual state file used by the service fixture.
    directory = Path(ledger["store"].db.execute("PRAGMA database_list").fetchone()[2]).parent
    ledger["store"].close()
    store = ContextStore(directory, "A")
    app = Context(
        store,
        pki["listener"]["pin"],
        {"alice": helpers.PERMISSIONS, "bob": helpers.PERMISSIONS},
        worker_slots={"one": "worker-1", "two": "worker-2"},
        approved_sources=ledger["source"]["config"],
        worker_credentials=ledger["credentials"],
        worker_launch="retained-single-use",
        native_children="admission-only",
        native_controls="run-journal",
        native_commands="owner-terminal-candidate",
        native_prompts="owner-reply-candidate",
        host_settlement=dict(
            profile="single-host-terminal-candidate", fingerprint=pki["host"]["pin"]
        ),
    )
    try:
        with serving(app, pki["context-a"]["server"]) as server:
            restarted = dict(ledger, app=app, store=store, server=server)
            assert release(restarted, pki, result)[0] == 403
            assert held(restarted) == (0 if phase == "RELEASED" else 1)
            assert store.db.execute("SELECT spent FROM workers WHERE slot='one'").fetchone()[0] == 1
    finally:
        app.close()
        store.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"container_id": "d" * 64},
        {"image": "sha256:" + "d" * 64},
        {"running": True},
        {"pid": 123},
        {"exit_code": 1},
        {"oom_killed": True},
        {"restart_count": 1},
        {"original_handles": 0, "exited_handles": 0},
        {"exited_handles": 2},
        {"original_handles": True, "exited_handles": True},
        {"roster_hash": "d" * 64},
    ],
)
def test_invalid_host_cleanup_evidence_cannot_clear_hold(ledger, pki, changes):
    fence = begin(ledger, pki)
    assert complete(ledger, pki, fence, **changes)[0] == 403
    assert held(ledger) == 1


def test_fence_stops_queued_commands_child_admission_and_startup_run(ledger, pki):
    grant = owners.delivered(ledger, pki, "CMD_RUN")
    child = families.admit(ledger, pki)[1]["result"]["child_grant"]
    fence = begin(ledger, pki)
    assert owners.worker(ledger, pki, "command-forward", grant)[0] == 403
    assert families.consume(ledger, pki, child)[0] == 403
    assert families.admit(ledger, pki, entrypoint="grand.py")[0] == 403
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    code, answer = complete(ledger, pki, fence)
    assert code == 200 and answer["result"]["state"] == "SETTLED"
    assert answer["result"]["report"]["preserved_work_journals"]["native_owner_commands"] == {
        "DELIVERY_UNPROVEN": 1
    }
    assert release(ledger, pki, answer["result"])[0] == 200
    assert held(ledger) == 0


def test_consumed_child_without_member_blocks_settlement(ledger, pki):
    child = families.admit(ledger, pki)[1]["result"]["child_grant"]
    assert families.consume(ledger, pki, child)[0] == 200
    fence = begin(ledger, pki)
    answer = complete(ledger, pki, fence)[1]["result"]
    assert answer["state"] == "HELD"
    assert "family_membership_unresolved" in answer["report"]["reasons"]
    assert held(ledger) == 2


def test_duplicate_completion_is_exactly_idempotent_and_changed_evidence_conflicts(ledger, pki):
    fence = begin(ledger, pki)
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda _: complete(ledger, pki, fence), range(8)))
    assert all(answer == answers[0] for answer in answers)
    assert answers[0][0] == 200
    assert complete(ledger, pki, fence, original_handles=4, exited_handles=4)[0] == 409
    count = (
        ledger["store"]
        .db.execute("SELECT COUNT(*) FROM events WHERE type='TERMINAL_FAMILY_RECONCILED'")
        .fetchone()[0]
    )
    assert count == 1


@pytest.mark.parametrize("source", ["simulator"], indirect=True)
@pytest.mark.parametrize("fault", [None, "partial", "disagree", "uncertain"])
def test_real_independent_dss_receipts_must_be_complete_in_both_ledgers(
    ledger, pki, dss, tmp_path, fault
):
    gate = DriverGate(ledger["app"].authority, tmp_path / "driver", {"simulator": dss.tc_address})
    bound = EffectAdmission(gate, ledger["grant"], "simulator", str(uuid.uuid4()))
    try:
        ok, receipts = effects.command(dss, bound)
        assert ok and len(receipts) == 5
        assert dss.get("state")["core"]["commands_executed"] == 1
        if fault == "partial":
            for db in (gate.db, ledger["store"].db):
                db.execute("DELETE FROM effect_intents WHERE stage='ONBOARD_EXECUTION'")
        elif fault == "disagree":
            gate.db.execute(
                "UPDATE effect_intents SET receipt_hash=? WHERE stage='RELEASE'", ("d" * 64,)
            )
        elif fault == "uncertain":
            for db in (gate.db, ledger["store"].db):
                db.execute("UPDATE effect_intents SET state='UNCERTAIN' WHERE stage='RELEASE'")
        fence = begin(ledger, pki)
        answer = complete(ledger, pki, fence)[1]["result"]
        assert answer["state"] == ("SETTLED" if fault is None else "HELD")
        if fault:
            assert "external_effects_unresolved" in answer["report"]["reasons"]
            assert release(ledger, pki, answer)[0] == 409
        else:
            assert answer["report"]["effect_receipts"] == 5
            assert release(ledger, pki, answer)[0] == 200
    finally:
        gate.close()


def test_report_audit_failure_rolls_back_and_retains_reservation(ledger, pki, monkeypatch):
    fence = begin(ledger, pki)
    event = ledger["store"]._event

    def fail(kind, body):
        if kind == "TERMINAL_FAMILY_RECONCILED":
            raise Fault(503, "injected_audit_failure")
        return event(kind, body)

    monkeypatch.setattr(ledger["store"], "_event", fail)
    assert complete(ledger, pki, fence)[0] == 503
    assert held(ledger) == 1
    row = (
        ledger["store"].db.execute("SELECT state,report_hash FROM terminal_settlements").fetchone()
    )
    assert tuple(row) == ("FENCED", None)


def test_host_scope_rejects_cross_context_and_old_incarnation(ledger, pki):
    common = dict(
        schema=TerminalSettlement.SCHEMA,
        context_id="A",
        execution_id=ledger["execution"]["id"],
        authority_incarnation=ledger["store"].incarnation,
        container_id="c" * 64,
        native_status="CLOSED",
    )
    for changes in (dict(context_id="B"), dict(authority_incarnation=str(uuid.uuid4()))):
        code, _ = request(
            ledger["server"],
            pki["host"]["client"],
            "/v1/host/terminal/begin",
            subject=None,
            payload=dict(common, **changes),
        )
        assert code == 403
    assert (
        "capability"
        not in canonical(ledger["app"].settlement.snapshot(ledger["execution"]["id"])).decode()
    )
