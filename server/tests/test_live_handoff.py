"""Real production mTLS routes and original runtime fencing across A/B/C handoff."""

from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from openbexi_spell_server.contracts import Actor, Fault, envelope
from openbexi_spell_server.handoff import LiveFamilyHandoff
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.transport import Route
from authority_test_helpers import accept
from test_launch import call
import test_terminal_settlement as terminal
import test_owner_commands as owners
import test_family as families
import test_preflight as helpers

source = terminal.source
setup = terminal.setup


@pytest.fixture
def ledger(setup, pki):
    terminal.configure(setup, pki)
    LiveFamilyHandoff(setup["app"].authority)
    setup["app"].subjects["observer"] = Actor(
        "observer", frozenset({"context:read", "execution:read"})
    )
    assert terminal.bind(setup, pki)[0] == 200
    assert terminal.start(setup, pki) == 200
    assert terminal.members.bind(setup, pki)[0] == 200
    return setup


def host(ledger, pki, action, *, certificate="host", **body):
    route = Route(
        f"https://localhost:{ledger['server'].server_port}",
        pki["context-a"]["pin"],
        pki[certificate]["client"],
    )
    return route.call(
        dict(
            schema=LiveFamilyHandoff.SCHEMA,
            context_id="A",
            execution_id=ledger["execution"]["id"],
            authority_incarnation=ledger["store"].incarnation,
            **body,
        ),
        path="/v1/host/handoff/" + action,
        schema=LiveFamilyHandoff.SCHEMA,
    )


def evidence(ledger, state, **changes):
    members, _ = ledger["app"].settlement._roster(ledger["execution"]["id"])
    return dict(
        dict(
            provider="docker-cgroup-freezer-pidfd/1",
            container_id="c" * 64,
            image=ledger["source"]["config"]["procedure"]["runtime_image"],
            paused=True,
            running=True,
            frozen=True,
            oom_killed=False,
            restart_count=0,
            original_handles=4,
            alive_handles=4,
            member_bindings=sorted(m["binding_hash"] for m in members),
            roster_hash=state["roster_hash"],
        ),
        **changes,
    )


def prepare(ledger, pki):
    accept(ledger)
    state = host(ledger, pki, "status")
    proof = evidence(ledger, state)
    return state, proof


def transfer(ledger, pki):
    state, proof = prepare(ledger, pki)
    result = host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
    assert result["state"] == "TRANSFERRED_PAUSED" and result["quiescence_proven"]
    row = ledger["app"].authority._execution(ledger["execution"]["id"])
    bound = ledger["controller"](
        "execution.rebind",
        dict(
            execution_id=row["id"], connection_id=row["connection_id"], expected_epoch=row["epoch"]
        ),
        subject="bob",
    )
    return state, proof, bound


def resumed(ledger, pki):
    state, proof, bound = transfer(ledger, pki)
    code, answer = owners.enqueue(
        ledger,
        pki,
        "CMD_RUN",
        subject="bob",
        body=dict(helpers.proof(bound), target_admission_id=None, command="CMD_RUN"),
    )
    assert code == 200, answer
    result = host(
        ledger,
        pki,
        "resume",
        barrier_id=state["barrier_id"],
        resume_id=answer["result"]["command_id"],
        evidence=proof,
    )
    return state, proof, bound, result["runtime_epoch"]


def activate(ledger, pki, epoch, **changes):
    route = Route(
        f"https://localhost:{ledger['server'].server_port}",
        pki["context-a"]["pin"],
        pki["worker"]["client"],
    )
    return route.call(
        dict(
            dict(
                schema="openbexi.worker/2",
                context_id="A",
                grant=asdict(ledger["grant"]),
                runtime_capability=ledger["runtime_capabilities"][ledger["grant"].execution_id],
                runtime_epoch=epoch,
            ),
            **changes,
        ),
        path="/v1/worker/handoff-activate",
        schema="openbexi.worker/2",
    )


def observe(ledger, pki):
    route = Route(
        f"https://localhost:{ledger['server'].server_port}",
        pki["context-a"]["pin"],
        pki["listener"]["client"],
    )
    return route.call(envelope("A", "observer", "execution.list", {}))["executions"][0]


def test_actual_A_B_C_routes_rotate_once_and_preserve_original_family(ledger, pki):
    old = ledger["grant"]
    old_cap = ledger["runtime_capabilities"][old.execution_id]
    original_roster = ledger["app"].settlement._roster(old.execution_id)
    assert observe(ledger, pki)["owner"] == "alice"
    state, proof, bound, epoch = resumed(ledger, pki)
    view = observe(ledger, pki)
    assert view["owner"] == "bob" and view["epoch"] == 2
    assert "evidence" not in view["pause_barrier"] and "old_binding" not in repr(view)
    assert call(ledger, pki, old, "check")[0] == 403
    assert owners.enqueue(ledger, pki)[0] == 403
    assert owners.enqueue(ledger, pki, subject="observer")[0] == 403
    new = activate(ledger, pki, epoch)
    with pytest.raises(Fault, match="context_request_denied"):
        activate(ledger, pki, epoch)
    ledger["grant"] = start_grant(new["grant"])
    ledger["runtime_capabilities"][old.execution_id] = new["runtime_capability"]
    assert ledger["grant"].control_epoch == 2 and ledger["grant"].token != old.token
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200
    assert call(ledger, pki, old, "check", runtime_capability=old_cap)[0] == 403
    assert ledger["app"].settlement._roster(old.execution_id) == original_roster
    assert families.admit(ledger, pki)[0] == 403
    assert (
        owners.enqueue(
            ledger,
            pki,
            "CMD_STEP",
            subject="bob",
            body=dict(helpers.proof(bound), target_admission_id=None, command="CMD_STEP"),
        )[0]
        == 200
    )
    delivered = owners.worker(ledger, pki)[1]["result"]["grant"]
    assert delivered["owner"] == "bob" and delivered["control_epoch"] == 2
    assert owners.worker(ledger, pki, "command-forward", delivered)[0] == 200
    assert owners.worker(ledger, pki, "command-consume", delivered)[0] == 200
    assert (
        terminal.held(ledger) == 1
        and ledger["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    )
    assert observe(ledger, pki)["pause_barrier"]["runtime_identity_rotated"]


@pytest.mark.parametrize("status", ["FINISHED", "ERROR", "ABORTED", "CLOSED"])
def test_terminal_settlement_preserves_original_lineage_after_rotation(ledger, pki, status):
    _, _, _, epoch = resumed(ledger, pki)
    new = activate(ledger, pki, epoch)
    ledger["grant"] = start_grant(new["grant"])
    ledger["runtime_capabilities"][ledger["grant"].execution_id] = new["runtime_capability"]
    fence = terminal.begin(ledger, pki, status)
    code, answer = terminal.complete(ledger, pki, fence)
    assert code == 200 and answer["result"]["state"] == "SETTLED", answer
    assert terminal.release(ledger, pki, answer["result"])[0] == 200
    assert terminal.held(ledger) == 0
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert ledger["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


@pytest.mark.parametrize("certificate", ["worker", "listener", "alice", "bob", "observer"])
def test_only_separate_host_can_submit_freezer_evidence(ledger, pki, certificate):
    state, proof = prepare(ledger, pki)
    with pytest.raises(Fault):
        host(
            ledger,
            pki,
            "complete",
            certificate=certificate,
            barrier_id=state["barrier_id"],
            evidence=proof,
        )
    assert observe(ledger, pki)["owner"] == "alice"


@pytest.mark.parametrize(
    "changes",
    [
        dict(paused=False),
        dict(frozen=False),
        dict(running=False),
        dict(oom_killed=True),
        dict(restart_count=1),
        dict(original_handles=True),
        dict(alive_handles=3),
        dict(member_bindings=[]),
        dict(roster_hash="0" * 64),
        dict(container_id="d" * 64),
        dict(image="sha256:" + "0" * 64),
    ],
)
def test_false_or_substituted_physical_proof_keeps_A_and_holds(ledger, pki, changes):
    state, proof = prepare(ledger, pki)
    with pytest.raises(Fault, match="context_request_denied"):
        host(
            ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=dict(proof, **changes)
        )
    assert observe(ledger, pki)["owner"] == "alice" and terminal.held(ledger) == 1


def test_consumed_command_requires_real_native_handler_disposition(ledger, pki):
    grant = owners.delivered(ledger, pki, "CMD_RUN")
    assert owners.worker(ledger, pki, "command-forward", grant)[0] == 200
    assert owners.worker(ledger, pki, "command-consume", grant)[0] == 200
    state, proof = prepare(ledger, pki)
    with pytest.raises(Fault, match="context_request_denied"):
        host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
    assert (
        owners.worker(ledger, pki, "command-disposition", grant, disposition="HANDLER_RETURNED")[0]
        == 200
    )
    assert host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)[
        "effective_transfer"
    ]


def test_delayed_old_owner_command_cannot_be_relabelled_after_rotation(ledger, pki):
    delayed = owners.delivered(ledger, pki, "CMD_STEP")
    assert owners.worker(ledger, pki, "command-forward", delayed)[0] == 200
    _, _, _, epoch = resumed(ledger, pki)
    new = activate(ledger, pki, epoch)
    ledger["grant"] = start_grant(new["grant"])
    ledger["runtime_capabilities"][ledger["grant"].execution_id] = new["runtime_capability"]
    assert owners.worker(ledger, pki, "command-consume", delayed)[0] == 403
    assert (
        ledger["store"].db.execute("SELECT state FROM native_owner_commands").fetchone()[0]
        == "FORWARD_UNPROVEN"
    )


def test_B_must_bind_and_explicitly_resume_before_worker_activation(ledger, pki):
    state, proof, bound = transfer(ledger, pki)
    with pytest.raises(Fault, match="context_request_denied"):
        activate(ledger, pki, str(uuid.uuid4()))
    with pytest.raises(Fault, match="context_request_denied"):
        host(
            ledger,
            pki,
            "resume",
            barrier_id=state["barrier_id"],
            resume_id=str(uuid.uuid4()),
            evidence=proof,
        )
    assert (
        owners.enqueue(
            ledger,
            pki,
            "CMD_STEP",
            subject="bob",
            body=dict(helpers.proof(bound), target_admission_id=None, command="CMD_STEP"),
        )[0]
        == 409
    )


def test_complete_exact_replay_and_changed_evidence_conflict(ledger, pki):
    state, proof = prepare(ledger, pki)
    original = host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
    assert host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof) == original
    with pytest.raises(Fault, match="context_request_denied"):
        host(
            ledger,
            pki,
            "complete",
            barrier_id=state["barrier_id"],
            evidence=dict(proof, original_handles=5, alive_handles=5),
        )


def test_concurrent_activation_delivers_only_one_new_identity(ledger, pki):
    _, _, _, epoch = resumed(ledger, pki)

    def attempt(_):
        try:
            return activate(ledger, pki, epoch)
        except Fault as error:
            return error.status

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert sum(r == 403 for r in results) == 7


@pytest.mark.parametrize("phase", ["REQUESTED", "TRANSFERRED_PAUSED", "RESUME_AUTHORIZED"])
def test_timeout_never_unfreezes_or_restores_old_authority(ledger, pki, phase):
    if phase == "REQUESTED":
        state, _ = prepare(ledger, pki)
    elif phase == "TRANSFERRED_PAUSED":
        state, _, _ = transfer(ledger, pki)
    else:
        state, _, _, _ = resumed(ledger, pki)
    ledger["app"].authority.clock = lambda: state["deadline"] + 1
    assert observe(ledger, pki)["pause_barrier"]["state"] == "EXPIRED"
    assert observe(ledger, pki)["control_state"] == "RECOVERY_REQUIRED"
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert terminal.held(ledger) == 1


def test_audit_failure_rolls_back_transfer(ledger, pki):
    state, proof = prepare(ledger, pki)
    ledger["store"].max_events = (
        ledger["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    )
    with pytest.raises(Fault):
        host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
    assert observe(ledger, pki)["owner"] == "alice"
    assert host(ledger, pki, "status")["state"] == "REQUESTED"


@pytest.mark.parametrize("outcome", [None, "UNKNOWN", "FAILED"])
def test_pending_or_uncertain_prompt_rejects_accept_without_revoking_A(ledger, pki, outcome):
    prompt = terminal.prompts.opened(ledger, pki)
    if outcome:
        assert (
            terminal.prompts.worker(
                ledger, pki, "prompt-close", prompt_id=prompt["prompt_id"], outcome=outcome
            )[0]
            == 200
        )
    authority = ledger["app"].authority
    bob = ledger["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = ledger["controller"](
        "execution.claim",
        dict(execution_id=ledger["execution"]["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    with pytest.raises(Fault, match="handoff_prompt_unresolved"):
        authority.mutate(
            "alice",
            "execution.decide",
            str(uuid.uuid4()),
            dict(helpers.proof(ledger["execution"]), claim_id=claim["claim_id"], decision="accept"),
        )
    assert observe(ledger, pki)["control_state"] == "OWNED"
    assert call(ledger, pki, ledger["grant"], "check")[0] == 200


def test_unregistered_consumed_child_prevents_family_proof(ledger, pki):
    child = families.admit(ledger, pki)[1]["result"]["child_grant"]
    assert families.consume(ledger, pki, child)[0] == 200
    with pytest.raises(AssertionError, match="handoff_family_unresolved"):
        accept(ledger)
    assert observe(ledger, pki)["control_state"] == "OWNED"


@pytest.mark.parametrize("stage", ["prepared", "transferred", "authorized", "active"])
def test_context_restart_cannot_replay_a_live_resume_proof(ledger, pki, stage, tmp_path):
    from openbexi_spell_server.services import Context
    from openbexi_spell_server.store import ContextStore
    import shutil

    if stage == "prepared":
        state, proof = prepare(ledger, pki)
    elif stage == "transferred":
        state, proof, _ = transfer(ledger, pki)
    else:
        state, proof, _, epoch = resumed(ledger, pki)
        if stage == "active":
            activate(ledger, pki, epoch)
    destination = tmp_path / "restarted"
    from pathlib import Path

    database = ledger["store"].db.execute("PRAGMA database_list").fetchone()[2]
    shutil.copytree(Path(database).parent, destination)
    restarted = ContextStore(destination, "A")
    try:
        app = Context(
            restarted,
            pki["listener"]["pin"],
            {
                "alice": list(ledger["app"].subjects["alice"].permissions),
                "bob": list(ledger["app"].subjects["bob"].permissions),
            },
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
            native_pause="host-freeze-candidate",
        )
        assert (
            app.authority.live_handoff.snapshot(ledger["execution"]["id"])["state"]
            == "RESTART_FENCED"
        )
        with pytest.raises(Fault):
            app.authority.live_handoff.handle(
                app.settlement.peer,
                "/v1/host/handoff/complete",
                dict(
                    schema=LiveFamilyHandoff.SCHEMA,
                    context_id="A",
                    execution_id=ledger["execution"]["id"],
                    authority_incarnation=restarted.incarnation,
                    barrier_id=state["barrier_id"],
                    evidence=proof,
                ),
            )
        assert restarted.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    finally:
        restarted.close()


dss = terminal.dss


@pytest.mark.parametrize("source", ["simulator"], indirect=True)
@pytest.mark.parametrize("fault", [None, "partial", "conflict", "uncertain"])
def test_independent_DSS_receipts_and_runtime_provenance_survive_transfer(
    ledger, pki, dss, tmp_path, fault
):
    from openbexi_spell_server.effects import DriverGate, EffectAdmission

    gate = DriverGate(ledger["app"].authority, tmp_path / "driver", {"simulator": dss.tc_address})
    # This test invokes the actual driver effect seam directly. No native RPC
    # calls exist in this test; their separate journal is explicitly empty.
    ledger["store"].db.execute("CREATE TABLE native_driver_calls(execution_id TEXT,state TEXT)")
    try:
        old = ledger["grant"]
        admission = EffectAdmission(gate, old, "simulator", str(uuid.uuid4()))
        ok, receipts = terminal.effects.command(dss, admission)
        assert ok and len(receipts) == 5
        if fault == "partial":
            for db in (gate.db, ledger["store"].db):
                db.execute("DELETE FROM effect_intents WHERE stage='ONBOARD_EXECUTION'")
        if fault == "conflict":
            gate.db.execute(
                "UPDATE effect_intents SET receipt_hash=? WHERE stage='RELEASE'", ("f" * 64,)
            )
        if fault == "uncertain":
            for db in (gate.db, ledger["store"].db):
                db.execute("UPDATE effect_intents SET state='UNCERTAIN' WHERE stage='RELEASE'")
        if fault:
            state, proof = prepare(ledger, pki)
            with pytest.raises(Fault):
                host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
            assert observe(ledger, pki)["owner"] == "alice"
        else:
            _, _, _, epoch = resumed(ledger, pki)
            new = activate(ledger, pki, epoch)
            new_grant = start_grant(new["grant"])
            with pytest.raises(Fault):
                terminal.effects.command(
                    dss, EffectAdmission(gate, old, "simulator", str(uuid.uuid4()))
                )
            ok, receipts = terminal.effects.command(
                dss, EffectAdmission(gate, new_grant, "simulator", str(uuid.uuid4()))
            )
            assert ok and len(receipts) == 5
            import json

            rows = (
                ledger["store"].db.execute("SELECT provenance,state FROM effect_intents").fetchall()
            )
            assert len(rows) == 10 and all(r["state"] == "ACKED" for r in rows)
            assert {json.loads(r["provenance"])["control_epoch"] for r in rows} == {1, 2}
            assert dss.get("state")["core"]["commands_executed"] == 2
        assert terminal.held(ledger) == 1
    finally:
        gate.close()


def runtime(ledger, pki, tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "handoff_runtime",
        Path(__file__).resolve().parents[2] / "host_runtime/python/handoff_runtime.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    epoch = tmp_path / "epoch"
    epoch.write_text(ledger["grant"].request_id)
    body = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(ledger["grant"]),
        runtime_capability=ledger["runtime_capabilities"][ledger["grant"].execution_id],
    )
    route = Route(
        f"https://localhost:{ledger['server'].server_port}",
        pki["context-a"]["pin"],
        pki["worker"]["client"],
    )
    return module.HandoffRuntime(body, route, epoch), epoch


def test_real_worker_rotation_rejects_delayed_native_epoch_and_serializes_threads(
    ledger, pki, tmp_path
):
    worker, path = runtime(ledger, pki, tmp_path)
    old = worker.epoch
    _, _, _, epoch = resumed(ledger, pki)
    path.write_text(epoch)
    with pytest.raises(ValueError, match="Original native operation epoch"):
        worker.ensure(old, native=True)
    assert not worker.rotated
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: worker.ensure(epoch, native=True), range(8)))
    assert worker.rotated and not worker.failed
    assert worker.request["grant"]["control_epoch"] == 2
    with pytest.raises(ValueError, match="Original native operation epoch"):
        worker.ensure(old, native=True)
    assert (
        ledger["store"]
        .db.execute("SELECT COUNT(*) FROM events WHERE type='LIVE_RUNTIME_IDENTITY_ROTATED'")
        .fetchone()[0]
        == 1
    )


def test_lost_activation_reply_never_retries_or_restamps_old_requests(ledger, pki, tmp_path):
    worker, path = runtime(ledger, pki, tmp_path)
    _, _, _, epoch = resumed(ledger, pki)
    path.write_text(epoch)
    original = worker.route.call

    def lost(*args, **kwargs):
        original(*args, **kwargs)
        raise TimeoutError("Simulated lost reply after durable activation")

    worker.route.call = lost
    with pytest.raises(TimeoutError):
        worker.ensure(epoch, native=True)
    with pytest.raises(ValueError, match="uncertain"):
        worker.ensure(epoch, native=True)
    assert worker.failed and not worker.rotated and worker.request["grant"]["control_epoch"] == 1
    assert call(ledger, pki, ledger["grant"], "check")[0] == 403
    assert terminal.held(ledger) == 1
