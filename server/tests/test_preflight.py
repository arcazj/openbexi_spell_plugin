"""Real mTLS worker preflight; native user code remains disabled."""

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from openbexi_spell_server.contracts import Actor, Fault, canonical, envelope
from openbexi_spell_server.services import Context, Listener
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.worker import preflight
from openbexi_spell_server.transport import Route
from test_authority import PERMISSIONS
from test_services import request, serving
from test_snapshots import reservation


@pytest.fixture
def worker_setup(tmp_path, pki, source):
    store = ContextStore(tmp_path / "state", "A")
    credentials = dict(
        profile="single-host-preflight",
        identities={pki["worker"]["pin"]: dict(slot="one", incarnation="worker-1")},
    )
    app = Context(
        store,
        pki["listener"]["pin"],
        {"alice": PERMISSIONS, "bob": PERMISSIONS},
        worker_slots={"one": "worker-1", "two": "worker-2"},
        approved_sources=source["config"],
        worker_credentials=credentials,
    )
    try:
        with serving(app, pki["context-a"]["server"]) as server:

            def controller(method, body, *, subject="alice", key=None):
                code, response = request(
                    server,
                    pki["listener"]["client"],
                    "/v1/rpc",
                    subject=None,
                    payload=envelope("A", subject, method, body, key or str(uuid.uuid4())),
                )
                assert code == 200, response
                return response["result"]

            connection = controller("session.open", {})["connection_id"]
            execution = controller("execution.reserve", reservation(source, connection=connection))
            config = dict(
                ca=str(pki["ca"]),
                certificate=str(pki["worker"]["cert"]),
                key=str(pki["worker"]["key"]),
                context_url=f"https://localhost:{server.server_port}",
                context_fingerprint=pki["context-a"]["pin"],
                context_id="A",
                execution_id=execution["id"],
                worker_slot="one",
                worker_incarnation="worker-1",
                snapshot_directory=str(source["directory"]),
            )
            yield dict(
                store=store,
                app=app,
                server=server,
                controller=controller,
                execution=execution,
                config=config,
                credentials=credentials,
                connection=connection,
                source=source,
            )
    finally:
        store.close()


def worker_call(setup, pki, path="challenge", **updates):
    body = dict(
        schema="openbexi.worker/1",
        context_id="A",
        execution_id=setup["execution"]["id"],
        request_id=str(uuid.uuid4()),
    )
    if path == "verify":
        body.pop("request_id")
    body.update(updates)
    return request(
        setup["server"], pki["worker"]["client"], "/v1/worker/" + path, subject=None, payload=body
    )


def proof(execution):
    return dict(
        execution_id=execution["id"],
        connection_id=execution["connection_id"],
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
    )


def test_real_worker_preflight_subprocess_verifies_source_but_does_not_launch_or_spend(
    worker_setup, tmp_path
):
    setup = worker_setup
    config = tmp_path / "private-worker.json"
    config.write_bytes(canonical(setup["config"]))
    code_root = Path(__file__).resolve().parents[1] / "src"
    with subprocess.Popen(
        [sys.executable, "-m", "openbexi_spell_server.worker", "--config", str(config)],
        env=dict(os.environ, PYTHONPATH=str(code_root)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        stdout, stderr = process.communicate(timeout=7)
        assert process.returncode == 0, stderr.decode()
        receipt = json.loads(stdout)
        assert receipt["verified"] is True and receipt["runtime_enabled"] is False
        worker_pid = process.pid
    assert (
        setup["store"].db.execute("SELECT spent FROM workers WHERE slot='one'").fetchone()[0] == 0
    )
    assert (
        setup["app"].authority.list_executions("alice")["executions"][0]["lifecycle"] == "RESERVED"
    )
    if output := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
        Path(output, "worker-preflight-trace.json").write_bytes(
            canonical(
                dict(
                    worker_preflight_pid=worker_pid,
                    context_host_pid=os.getpid(),
                    distinct_processes=worker_pid != os.getpid(),
                    real_mutual_tls=True,
                    source_digest=receipt["source_sha256"],
                    native_executor_tested=False,
                    worker_slot_spent=False,
                    runtime_enabled=False,
                )
            )
        )


def test_source_verified_preflight_is_required_for_private_admission_and_consumption(worker_setup):
    setup = worker_setup
    authority, execution = setup["app"].authority, setup["execution"]
    with pytest.raises(Fault, match="worker_preflight_required"):
        authority.admit_start("alice", proof(execution))
    assert preflight(setup["config"])["verified"]
    grant = authority.admit_start("alice", proof(execution))
    # Exercise the authenticated integration seam; there is no network consume route.
    peer = next(iter(setup["app"].preflight.peers.values()))
    assert authority.consume_start(grant, peer.slot, peer.incarnation)
    assert authority.validate_start_grant(grant)


def test_preflight_expiry_does_not_clear_hold_or_authorize_start(worker_setup):
    setup = worker_setup
    preflight(setup["config"])
    authority = setup["app"].authority
    now = authority.clock()
    authority.clock = lambda: now + 31
    with pytest.raises(Fault, match="worker_preflight_required"):
        authority.admit_start("alice", proof(setup["execution"]))
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    authority.clock = lambda: now
    grant = authority.admit_start("alice", proof(setup["execution"]))
    authority.clock = lambda: now + 31
    with pytest.raises(Fault, match="worker_preflight_required"):
        authority.consume_start(grant, "one", "worker-1")
    assert (
        setup["store"].db.execute("SELECT spent FROM workers WHERE slot='one'").fetchone()[0] == 0
    )


def test_source_aliases_cannot_bypass_reservations_or_idempotency(worker_setup):
    setup = worker_setup
    body = reservation(setup["source"], procedure="alias", connection=setup["connection"])
    with pytest.raises(Fault, match="procedure_reserved"):
        setup["app"].authority.mutate("alice", "execution.reserve", "alias", body)
    changed = {**body, "procedure_id": "forged"}
    with pytest.raises(Fault, match="procedure_not_approved"):
        setup["app"].authority.mutate("alice", "execution.reserve", "forged", changed)


@pytest.mark.parametrize(
    "change", ["changed_source", "extra_file", "wrong_assignment", "wrong_server_pin"]
)
def test_worker_client_failures_never_verify_or_spend_slot(worker_setup, change):
    setup = worker_setup
    config = dict(setup["config"])
    if change == "changed_source":
        Path(config["snapshot_directory"], "main.py").write_text("changed")
    elif change == "extra_file":
        Path(config["snapshot_directory"], "extra.py").write_text("extra")
    elif change == "wrong_assignment":
        config["worker_incarnation"] = "forged"
    else:
        config["context_fingerprint"] = "0" * 64
    with pytest.raises(Fault):
        preflight(config)
    assert (
        setup["store"]
        .db.execute("SELECT COUNT(*) FROM worker_preflights WHERE state='VERIFIED'")
        .fetchone()[0]
        == 0
    )
    assert (
        setup["store"].db.execute("SELECT spent FROM workers WHERE slot='one'").fetchone()[0] == 0
    )


def test_worker_role_cannot_delegate_users_and_other_ca_roles_cannot_preflight(worker_setup, pki):
    setup = worker_setup
    for role in ("listener", "edge", "context-b"):
        assert request(
            setup["server"],
            pki[role]["client"],
            "/v1/worker/challenge",
            subject=None,
            payload=dict(
                schema="openbexi.worker/1",
                context_id="A",
                execution_id=setup["execution"]["id"],
                request_id=str(uuid.uuid4()),
            ),
        )[0] in (403, 404)
    for method in ("session.open", "execution.reserve", "blackboard.get"):
        assert (
            request(
                setup["server"],
                pki["worker"]["client"],
                "/v1/rpc",
                subject=None,
                payload=envelope("A", "alice", method, {}, "forged"),
            )[0]
            == 404
        )
    assert worker_call(setup, pki, context_id="B")[0] == 403
    assert worker_call(setup, pki, worker_slot="other")[0] == 400
    for path in ("start", "consume", "driver", "recover"):
        assert worker_call(setup, pki, path)[0] == 404


def test_delayed_preflight_after_rebind_and_owner_transfer_is_fenced(worker_setup, pki):
    setup = worker_setup
    code, response = worker_call(setup, pki)
    assert code == 200
    challenge = response["result"]
    rebound = setup["controller"](
        "execution.rebind",
        dict(
            execution_id=setup["execution"]["id"],
            connection_id=setup["connection"],
            expected_epoch=1,
        ),
    )
    assert (
        worker_call(
            setup,
            pki,
            "verify",
            challenge_id=challenge["challenge_id"],
            source_sha256=challenge["source_sha256"],
        )[0]
        == 403
    )
    assert preflight(setup["config"])["verified"]
    bob = setup["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = setup["controller"](
        "execution.claim",
        dict(execution_id=rebound["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    accepted = setup["controller"](
        "execution.decide", {**proof(rebound), "claim_id": claim["claim_id"], "decision": "accept"}
    )
    assert accepted["state"] == "ACCEPTED"
    setup["controller"](
        "execution.rebind",
        dict(execution_id=rebound["id"], connection_id=bob, expected_epoch=2),
        subject="bob",
    )
    with pytest.raises(Fault, match="worker_preflight_required"):
        setup["app"].preflight.require_ready(setup["app"].authority._execution(rebound["id"]))


def test_worker_challenge_replay_and_audit_failure_are_bounded_and_atomic(worker_setup, pki):
    setup = worker_setup
    request_id = str(uuid.uuid4())
    first = worker_call(setup, pki, request_id=request_id)
    assert first[0] == 200
    assert worker_call(setup, pki, request_id=request_id) == first
    setup["store"].max_events = (
        setup["store"].db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    )
    assert worker_call(setup, pki, request_id=str(uuid.uuid4()))[0] == 503
    assert setup["store"].db.execute("SELECT COUNT(*) FROM worker_preflights").fetchone()[0] == 1
    assert (
        worker_call(
            setup,
            pki,
            "verify",
            challenge_id=first[1]["result"]["challenge_id"],
            source_sha256=first[1]["result"]["source_sha256"],
        )[0]
        == 503
    )
    assert (
        setup["store"].db.execute("SELECT state FROM worker_preflights").fetchone()[0] == "PENDING"
    )


def test_kubernetes_or_ambiguous_worker_profiles_are_rejected(tmp_path, pki, source):
    for profile in ("kubernetes", "single-host-preflight"):
        store = ContextStore(tmp_path / profile, "A")
        try:
            config = dict(
                profile=profile,
                identities={pki["listener"]["pin"]: dict(slot="one", incarnation="worker-1")},
            )
            with pytest.raises(ValueError):
                Context(
                    store,
                    pki["listener"]["pin"],
                    {"alice": PERMISSIONS},
                    worker_slots={"one": "worker-1"},
                    approved_sources=source["config"],
                    worker_credentials=config,
                )
        finally:
            store.close()


def test_wrong_source_receipt_expiry_replay_and_identity_capacity(worker_setup, pki):
    setup = worker_setup
    first = worker_call(setup, pki)[1]["result"]
    assert (
        worker_call(
            setup, pki, "verify", challenge_id=first["challenge_id"], source_sha256="0" * 64
        )[0]
        == 403
    )
    receipt = worker_call(
        setup,
        pki,
        "verify",
        challenge_id=first["challenge_id"],
        source_sha256=first["source_sha256"],
    )
    assert receipt[0] == 200
    assert (
        worker_call(
            setup,
            pki,
            "verify",
            challenge_id=first["challenge_id"],
            source_sha256=first["source_sha256"],
        )
        == receipt
    )
    for _ in range(7):
        assert worker_call(setup, pki)[0] == 200
    assert worker_call(setup, pki)[0] == 503
    setup["app"].authority.clock = lambda: first["expires_at"] + 1
    assert (
        worker_call(
            setup,
            pki,
            "verify",
            challenge_id=first["challenge_id"],
            source_sha256=first["source_sha256"],
        )[0]
        == 403
    )
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_worker_preflight_is_invalidated_on_context_restart(tmp_path, pki, source):
    directory = tmp_path / "restart-state"
    config = dict(
        worker_slots={"one": "worker-1"},
        approved_sources=source["config"],
        worker_credentials=dict(
            profile="single-host-preflight",
            identities={pki["worker"]["pin"]: dict(slot="one", incarnation="worker-1")},
        ),
    )
    store = ContextStore(directory, "A")
    try:
        app = Context(store, pki["listener"]["pin"], {"alice": PERMISSIONS}, **config)
        session = app.authority.mutate("alice", "session.open", "open", {})["connection_id"]
        execution = app.authority.mutate(
            "alice", "execution.reserve", "reserve", reservation(source, connection=session)
        )
        with serving(app, pki["context-a"]["server"]) as server:
            cfg = dict(
                ca=str(pki["ca"]),
                certificate=str(pki["worker"]["cert"]),
                key=str(pki["worker"]["key"]),
                context_url=f"https://localhost:{server.server_port}",
                context_fingerprint=pki["context-a"]["pin"],
                context_id="A",
                execution_id=execution["id"],
                worker_slot="one",
                worker_incarnation="worker-1",
                snapshot_directory=str(source["directory"]),
            )
            assert preflight(cfg)["verified"]
    finally:
        store.close()
    store = ContextStore(directory, "A")
    try:
        app = Context(store, pki["listener"]["pin"], {"alice": PERMISSIONS}, **config)
        assert (
            store.db.execute("SELECT state FROM worker_preflights").fetchone()[0] == "INVALIDATED"
        )
        assert (
            app.authority.list_executions("alice")["executions"][0]["control_state"]
            == "RECOVERY_REQUIRED"
        )
        with serving(app, pki["context-a"]["server"]) as server:
            cfg["context_url"] = f"https://localhost:{server.server_port}"
            with pytest.raises(Fault):
                preflight(cfg)
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    finally:
        store.close()


def test_catalog_discovery_is_scoped_redacted_and_exposes_usable_approved_binding(
    worker_setup, pki
):
    setup = worker_setup
    route = Route(
        f"https://localhost:{setup['server'].server_port}",
        pki["context-a"]["pin"],
        pki["listener"]["client"],
    )
    listener = Listener(
        pki["edge"]["pin"],
        {"a" * 64: "alice", "b" * 64: "outsider"},
        {"alice": ["A"], "outsider": []},
        {"A": route},
    )
    with serving(listener, pki["listener"]["server"]) as server:
        code, response = request(server, pki["edge"]["client"], "/v1/contexts/A/procedures")
        assert code == 200
        procedure = response["result"]["procedures"][0]
        assert procedure["procedure_id"] == "procedure" and procedure["aliases"] == ["alias"]
        assert procedure["source_sha256"] == reservation(setup["source"])["source_sha256"]
        assert "repository" not in json.dumps(response) and str(
            setup["source"]["root"]
        ) not in json.dumps(response)
        assert (
            request(server, pki["edge"]["client"], "/v1/contexts/A/procedures", subject="b" * 64)[0]
            == 403
        )
        setup["app"].subjects["alice"] = Actor("alice", frozenset({"context:read"}))
        assert request(server, pki["edge"]["client"], "/v1/contexts/A/procedures")[0] == 403
