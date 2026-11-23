"""Controller-to-worker native admission through the public mutual-TLS gateway."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import asdict
import uuid

import pytest

from openbexi_runtime.spell_server_client import SpellServerClient, SpellServerError
from openbexi_spell_server.assigned_launch import AssignedLaunch
from openbexi_spell_server.contracts import canonical
from openbexi_spell_server.gateway import Gateway
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.services import Context, Listener
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.transport import Route
from openbexi_spell_server.worker import preflight, wait_for_assignment
from test_ide_integration import reserve
from test_preflight import proof
from test_services import ALL, request, serving


@pytest.fixture
def assigned_cluster(tmp_path, pki, source):
    with ExitStack() as stack:
        store = ContextStore(tmp_path / "authority", "A")
        stack.callback(store.close)
        context = Context(
            store,
            pki["listener"]["pin"],
            {"alice": ALL, "observer": ["context:read", "execution:read"]},
            worker_slots={"one": "worker-1"},
            worker_credentials={
                "profile": "single-host-preflight",
                "identities": {
                    pki["worker"]["pin"]: {"slot": "one", "incarnation": "worker-1"},
                },
            },
            approved_sources=source["config"],
            worker_launch="assigned-single-use",
            native_children="admission-only",
            native_controls="run-journal",
            native_commands="owner-queue",
        )
        stack.callback(context.close)
        cs = stack.enter_context(serving(context, pki["context-a"]["server"]))
        url = f"https://localhost:{cs.server_port}"
        route = Route(url, pki["context-a"]["pin"], pki["listener"]["client"])
        listener = Listener(
            pki["edge"]["pin"],
            {pki[r]["pin"]: r for r in ("alice", "observer")},
            {"alice": ["A"], "observer": ["A"]},
            {"A": route},
            native_command_contexts=["A"],
            native_launch_contexts=["A"],
        )
        ls = stack.enter_context(serving(listener, pki["listener"]["server"]))
        edge = Gateway(
            f"https://localhost:{ls.server_port}",
            pki["listener"]["pin"],
            pki["edge"]["client"],
            [pki[r]["pin"] for r in ("alice", "observer")],
        )
        gs = stack.enter_context(serving(edge, pki["edge"]["server"]))

        def client(r):
            c = SpellServerClient(
                url=f"https://localhost:{gs.server_port}",
                fingerprint=pki["edge"]["pin"],
                ca=pki["ca"],
                certificate=pki[r]["cert"],
                key=pki[r]["key"],
            )
            stack.callback(c.forget)
            return c

        alice, observer = client("alice"), client("observer")
        execution = reserve(alice)
        entry = alice.read("A", "procedures")["procedures"][0]
        worker = {
            "ca": str(pki["ca"]),
            "certificate": str(pki["worker"]["cert"]),
            "key": str(pki["worker"]["key"]),
            "context_url": url,
            "context_fingerprint": pki["context-a"]["pin"],
            "context_id": "A",
            "worker_slot": "one",
            "worker_incarnation": "worker-1",
            "runtime_image": entry["runtime_image"],
            "snapshots": {entry["source_sha256"]: str(source["directory"])},
        }
        yield alice, observer, listener, context, cs, execution, worker


def test_public_launch_uses_a_private_one_shot_delivery_and_original_worker_proof(
    assigned_cluster, pki
):
    alice, observer, _, context, cs, execution, worker = assigned_cluster
    key = str(uuid.uuid4())
    eid = execution["id"]
    assert observer.read("A", "health")["native_launch"] is False
    assert alice.read("A", "health")["native_launch"] is True
    reserved = alice.read("A", "executions")["executions"][0]
    assert not reserved["native_start_admitted"] and not reserved["native_root_registered"]
    with pytest.raises(SpellServerError):
        observer.authority("A", "execution.prepare", proof(execution), key=key)
    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting = pool.submit(wait_for_assignment, worker, lambda directory: directory)
        receipt = alice.launch("A", eid, key=key)
        inside, raw, verified = waiting.result(timeout=8)
    assert inside["execution_id"] == eid and verified[0]["verified"]
    grant = start_grant(raw)
    assert receipt == {"execution_id": eid, "request_id": grant.request_id, "state": "ADMITTED"}
    assert grant.token not in canonical(receipt).decode()
    admitted = alice.read("A", "executions")["executions"][0]
    assert admitted["native_start_admitted"] and not admitted["native_root_registered"]
    body = {
        "schema": AssignedLaunch.SCHEMA,
        "context_id": "A",
        "execution_id": eid,
        "preparation_id": key,
    }
    assert (
        request(
            cs, pki["worker"]["client"], "/v1/worker/start-delivery", subject=None, payload=body
        )[0]
        == 409
    )
    consume = {"schema": "openbexi.worker/2", "context_id": "A", "grant": asdict(grant)}
    assert (
        request(cs, pki["worker"]["client"], "/v1/worker/consume", subject=None, payload=consume)[0]
        == 200
    )
    assert (
        request(cs, pki["worker"]["client"], "/v1/worker/consume", subject=None, payload=consume)[0]
        == 403
    )
    assert context.store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert alice.read("A", "executions")["executions"][0]["lifecycle"] == "STARTING"
    with pytest.raises(SpellServerError):
        alice.authority("A", "execution.launch", proof(execution), key=key)


def test_launch_needs_verified_source_and_is_fenced_on_disconnect(assigned_cluster, pki):
    alice, _, _, context, cs, execution, worker = assigned_cluster
    key = str(uuid.uuid4())
    owner = proof(execution)
    alice.authority("A", "execution.prepare", owner, key=key)
    assert alice.authority("A", "execution.launch_status", owner, key=key)["ready"] is False
    with pytest.raises(SpellServerError):
        alice.authority("A", "execution.launch", owner, key=key)
    check = {k: v for k, v in worker.items() if k not in ("runtime_image", "snapshots")}
    preflight(
        {
            **check,
            "execution_id": execution["id"],
            "snapshot_directory": next(iter(worker["snapshots"].values())),
        }
    )
    assert alice.authority("A", "execution.launch_status", owner, key=key)["ready"] is True
    alice.authority("A", "execution.launch", owner, key=key)
    alice.authority(
        "A", "session.close", {"connection_id": owner["connection_id"]}, key=str(uuid.uuid4())
    )
    body = {
        "schema": AssignedLaunch.SCHEMA,
        "context_id": "A",
        "execution_id": execution["id"],
        "preparation_id": key,
    }
    assert (
        request(
            cs, pki["worker"]["client"], "/v1/worker/start-delivery", subject=None, payload=body
        )[0]
        == 403
    )
    assert context.store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


def test_listener_must_enable_launch_separately(assigned_cluster):
    alice, _, listener, _, _, execution, _ = assigned_cluster
    listener.native_launch_contexts = frozenset()
    assert alice.read("A", "health")["native_launch"] is False
    with pytest.raises(SpellServerError) as error:
        alice.authority("A", "execution.prepare", proof(execution), key=str(uuid.uuid4()))
    assert error.value.status == 404
