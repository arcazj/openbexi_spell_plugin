"""Real mTLS child admission/consumption; native before-RUN hook is still gated."""

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import shutil
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.contracts import Fault, canonical, digest, envelope, policy
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.launch import WorkerLaunch
from openbexi_spell_server.pause import NativePauseBarrier
from openbexi_spell_server.snapshots import git_manifest
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.worker import preflight
from test_launch import call
from test_pause import accept
from test_services import request
import conftest as conf
import test_preflight as helpers

base_source = conf.source


@pytest.fixture
def source(tmp_path):
    data = base_source.__wrapped__(tmp_path)
    for name in ("child.py", "grand.py"):
        (data["root"] / name).write_text("RESULT=42\n")
    revision = conf.commit(data["root"])
    data["revision"] = revision
    data["manifest"] = git_manifest(data["root"], revision, "main.py")
    for f in data["manifest"]["files"]:
        shutil.copy2(data["root"] / f["path"], data["directory"] / f["path"])
    data["config"]["procedure"]["revision"] = revision
    for name in ("child", "grand"):
        data["config"][name] = dict(
            data["config"]["procedure"], entrypoint=name + ".py", aliases=[name + "-alias"]
        )
    return data


@pytest.fixture
def setup(tmp_path, pki, source):
    yield from helpers.worker_setup.__wrapped__(tmp_path, pki, source)


@pytest.fixture
def family(setup, pki):
    app = setup["app"]
    app.launch = WorkerLaunch(app.preflight)
    setup["family"] = FamilyAdmission(app.authority, app.catalog)
    preflight(setup["config"])
    setup["grant"] = app.authority.admit_start("alice", helpers.proof(setup["execution"]))
    assert call(setup, pki, setup["grant"])[0] == 200
    return setup


def payload(**changes):
    value = dict(
        request_id=str(uuid.uuid4()),
        parent_admission_id=None,
        entrypoint="child.py",
        arguments_sha256=digest({"value": 42}),
        mode=dict(automatic=True, visible=True, blocking=False),
    )
    value.update(changes)
    return value


def admit(setup, pki, body=None, **changes):
    value = payload() if body is None else dict(body)
    value.update(changes)
    return call(setup, pki, setup["grant"], "child-admit", **value)


def consume(setup, pki, child, **changes):
    return call(setup, pki, setup["grant"], "child-consume", child_grant=dict(child, **changes))


def test_default_profile_has_no_child_routes(setup, pki):
    setup["app"].launch = WorkerLaunch(setup["app"].preflight)
    preflight(setup["config"])
    grant = setup["app"].authority.admit_start("alice", helpers.proof(setup["execution"]))
    assert call(setup, pki, grant)[0] == 200
    assert call(setup, pki, grant, "child-admit", **payload())[0] == 404
    assert call(setup, pki, grant, "child-consume", child_grant={})[0] == 404


def test_child_grant_is_single_use_original_bound_and_never_native_start_proof(family, pki):
    setup = family
    code, reply = admit(setup, pki)
    assert code == 200
    result = reply["result"]
    child = result["child_grant"]
    assert result["native_start_qualified"] is False
    assert child["execution_id"] == setup["grant"].execution_id
    assert child["origin_hash"] == setup["family"].origin(setup["grant"])
    assert child["procedure_id"] == "child"
    assert consume(setup, pki, child)[0] == 200
    assert consume(setup, pki, child)[0] == 403
    store = setup["store"]
    assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2
    assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == 10
    assert child["token"] not in repr([tuple(r) for r in store.db.execute("SELECT * FROM events")])
    row = store.db.execute("SELECT * FROM child_admissions").fetchone()
    assert child["token"] not in repr(tuple(row))


def test_100_child_admissions_have_one_winner_and_retained_logical_identity(family, pki):
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: admit(family, pki), range(100)))
    diagnostics = dict(Counter((code, reply.get("error")) for code, reply in replies))
    assert sum(code == 200 for code, _ in replies) == 1, diagnostics
    assert sum(code == 409 for code, _ in replies) == 99, diagnostics
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 1


def test_duplicate_request_cannot_redeliver_token_or_restamp_child_identity(family, pki):
    body = payload()
    code, first = admit(family, pki, body)
    assert code == 200
    token = first["result"]["child_grant"]["token"]
    replay = admit(family, pki, body)[1]["result"]
    assert replay["replayed"] and replay["token_delivery"] == "unavailable"
    assert token not in canonical(replay).decode() and "child_grant" not in replay
    assert admit(family, pki, body, arguments_sha256="0" * 64)[0] == 409
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


def test_one_of_20_child_consumptions_wins_without_retry_authority(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: consume(family, pki, child)[0], range(20)))
    assert codes.count(200) == 1 and codes.count(403) == 19


@pytest.mark.parametrize(
    "path", ["main.py", "lib/helper.py", "../child.py", "child", "child.py/../grand.py"]
)
def test_recursive_unapproved_or_ambiguous_child_path_is_denied(family, pki, path):
    code, _ = admit(family, pki, entrypoint=path)
    assert code in (400, 403, 409)
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "field,value", [("runtime_image", "sha256:" + "0" * 64), ("driver_binding", "other")]
)
def test_child_cannot_change_parent_runtime_or_driver(family, pki, field, value):
    family["app"].catalog.entries["child"][field] = value
    assert admit(family, pki)[0] == 403


@pytest.mark.parametrize(
    "field,value", [("runtime_image", "sha256:" + "0" * 64), ("driver_binding", "changed")]
)
def test_catalog_update_cannot_rebind_already_admitted_parent(family, pki, field, value):
    catalog = family["app"].catalog
    catalog.entries["procedure"][field] = value
    catalog.entries["child"][field] = value
    code, response = admit(family, pki)
    assert code == 403 and response["error"] == "child_parent_source_binding_changed"
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"token": "0" * 64},
        {"operation_digest": "0" * 64},
        {"execution_id": str(uuid.uuid4())},
        {"entrypoint": "grand.py"},
        {"authority_incarnation": str(uuid.uuid4())},
    ],
)
def test_child_grant_tampering_is_denied(family, pki, changes):
    child = admit(family, pki)[1]["result"]["child_grant"]
    assert consume(family, pki, child, **changes)[0] == 403
    assert (
        family["store"].db.execute("SELECT state FROM child_admissions").fetchone()[0] == "ADMITTED"
    )


def test_nested_admission_requires_consumed_same_family_parent(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    assert (
        admit(family, pki, entrypoint="grand.py", parent_admission_id=child["admission_id"])[0]
        == 403
    )
    assert consume(family, pki, child)[0] == 200
    code, nested = admit(
        family, pki, entrypoint="grand.py", parent_admission_id=child["admission_id"]
    )
    assert (
        code == 200
        and nested["result"]["child_grant"]["parent_admission_id"] == child["admission_id"]
    )
    assert consume(family, pki, nested["result"]["child_grant"])[0] == 200
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 3


def test_top_level_alias_and_child_share_atomic_reservation_namespace(family, pki):
    setup = family
    entry = setup["app"].catalog.entries["child"]
    body = dict(
        procedure_id="child-alias",
        connection_id=setup["connection"],
        **{
            k: entry[k]
            for k in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
        },
    )

    def top():
        return request(
            setup["server"],
            pki["listener"]["client"],
            "/v1/rpc",
            subject=None,
            payload=envelope("A", "alice", "execution.reserve", body, str(uuid.uuid4())),
        )[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(top)
        b = pool.submit(lambda: admit(setup, pki)[0])
        assert sorted([a.result(), b.result()]) == [200, 409]
    assert (
        setup["store"]
        .db.execute("SELECT COUNT(*) FROM reservations WHERE procedure_id='child'")
        .fetchone()[0]
        == 1
    )


def test_no_original_config_clone_can_admit_or_consume_children(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    assert (
        call(
            family,
            pki,
            family["grant"],
            "child-admit",
            runtime_capability="0" * 64,
            **payload(entrypoint="grand.py"),
        )[0]
        == 403
    )

    assert (
        call(
            family,
            pki,
            family["grant"],
            "child-consume",
            runtime_capability="0" * 64,
            child_grant=child,
        )[0]
        == 403
    )
    assert (
        call(family, pki, family["grant"], "child-consume", certificate="alice", child_grant=child)[
            0
        ]
        == 403
    )


def test_child_consume_suffix_does_not_bypass_consumption_winner_proof(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    body = dict(
        schema="openbexi.worker/2", context_id="A", grant=asdict(family["grant"]), child_grant=child
    )
    code, response = request(
        family["server"],
        pki["worker"]["client"],
        "/v1/worker/child-consume",
        subject=None,
        payload=body,
    )
    assert code == 403 and response["error"] == "worker_consumption_proof_required"
    assert consume(family, pki, child)[0] == 200


def test_live_role_revocation_precedes_replay_disclosure(family, pki):
    body = payload()
    assert admit(family, pki, body)[0] == 200
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert admit(family, pki, body)[0] == 403


def test_transfer_barrier_fences_child_admission_and_consumption(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    NativePauseBarrier(family["app"].authority)
    assert accept(family)[0]["state"] == "PAUSING"
    assert admit(family, pki, entrypoint="grand.py")[0] == 403
    assert consume(family, pki, child)[0] == 403
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


def test_audit_failure_rolls_back_child_reservation_and_consumption(family, pki):
    store = family["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert admit(family, pki)[0] == 503
    assert store.db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    store.max_events += 10
    child = admit(family, pki)[1]["result"]["child_grant"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert consume(family, pki, child)[0] == 503
    assert store.db.execute("SELECT state FROM child_admissions").fetchone()[0] == "ADMITTED"


def test_authority_restart_fences_child_grants_and_retains_reservations(family, pki):
    child = admit(family, pki)[1]["result"]["child_grant"]
    directory = Path(family["store"].db.execute("PRAGMA database_list").fetchone()[2]).parent
    family["store"].close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(
            store,
            family["app"].authority.subjects,
            worker_slots={"one": "worker-1", "two": "worker-2"},
        )
        coordinator = FamilyAdmission(authority, family["app"].catalog)
        with pytest.raises(Fault):
            coordinator.consume(family["grant"], child)
        assert (
            store.db.execute("SELECT state FROM child_admissions").fetchone()[0] == "RESTART_FENCED"
        )
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2
    finally:
        store.close()


def test_duplicate_coordinator_cannot_invalidate_live_admissions(family, pki):
    assert admit(family, pki)[0] == 200
    with pytest.raises(ValueError):
        FamilyAdmission(family["app"].authority, family["app"].catalog)
    assert (
        family["store"].db.execute("SELECT state FROM child_admissions").fetchone()[0] == "ADMITTED"
    )
