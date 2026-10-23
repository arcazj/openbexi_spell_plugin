"""Authenticated original-grant launch consumption; native tests run in Docker CI."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import uuid

import pytest

from openbexi_spell_server.contracts import Fault, canonical
from openbexi_spell_server.launch import WorkerLaunch, start_grant
from openbexi_spell_server.services import Context
from openbexi_spell_server.worker import preflight
import test_preflight as helpers
from test_services import request


@pytest.fixture
def setup(tmp_path, pki, source):
    yield from helpers.worker_setup.__wrapped__(tmp_path, pki, source)


def grant(setup):
    preflight(setup["config"])
    return setup["app"].authority.admit_start("alice", helpers.proof(setup["execution"]))


def call(setup, pki, admitted, action="consume", *, certificate="worker", **updates):
    body = dict(schema="openbexi.worker/1", context_id="A", grant=asdict(admitted))
    body.update(updates)
    return request(
        setup["server"],
        pki[certificate]["client"],
        "/v1/worker/" + action,
        subject=None,
        payload=body,
    )


def enable(setup):
    setup["app"].launch = WorkerLaunch(setup["app"].preflight)


def test_launch_rpc_is_disabled_by_default(setup, pki):
    admitted = grant(setup)
    assert call(setup, pki, admitted)[0] == 404
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


def test_original_grant_consumed_once_over_real_mutual_tls(setup, pki):
    enable(setup)
    admitted = grant(setup)
    status, reply = call(setup, pki, admitted)
    assert status == 200 and reply["result"]["consumed"] is True
    assert admitted.token not in canonical(reply).decode()
    assert reply["result"]["request_id"] == admitted.request_id
    assert reply["result"]["hold_retained"] is True
    assert call(setup, pki, admitted)[0] == 403
    assert call(setup, pki, admitted, "check")[0] == 200
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_one_of_100_duplicate_authenticated_consumptions_wins(setup, pki):
    enable(setup)
    admitted = grant(setup)
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: call(setup, pki, admitted)[0], range(100)))
    assert statuses.count(200) == 1 and statuses.count(403) == 99
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("certificate", ["alice", "bob", "listener", "observer"])
def test_non_worker_certificate_cannot_consume(setup, pki, certificate):
    enable(setup)
    admitted = grant(setup)
    assert call(setup, pki, admitted, certificate=certificate)[0] in (403, 404)
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_slot", "two"),
        ("worker_incarnation", "worker-2"),
        ("control_epoch", 2),
        ("connection_generation", 2),
        ("token", "0" * 64),
    ],
)
def test_substituted_assignment_or_provenance_cannot_launch(setup, pki, field, value):
    enable(setup)
    admitted = grant(setup)
    changed = asdict(admitted)
    changed[field] = value
    assert call(setup, pki, admitted, grant=changed)[0] == 403
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("control_epoch", True),
        ("worker_generation", 0),
        ("connection_generation", 2**32),
        ("request_id", "not-a-uuid"),
        ("operation_digest", "bad"),
    ],
)
def test_malformed_grant_is_rejected_before_launch(setup, field, value):
    admitted = asdict(grant(setup))
    admitted[field] = value
    with pytest.raises(Fault):
        start_grant(admitted)


def test_disconnect_after_consume_invalidates_worker_check_and_retains_hold(setup, pki):
    enable(setup)
    admitted = grant(setup)
    assert call(setup, pki, admitted)[0] == 200
    setup["controller"]("session.close", {"connection_id": setup["connection"]})
    assert call(setup, pki, admitted, "check")[0] == 403
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_no_worker_endpoint_can_issue_or_refresh_a_grant(setup, pki):
    enable(setup)
    admitted = grant(setup)
    for action in ("admit", "start", "rebind", "release", "recover"):
        assert call(setup, pki, admitted, action)[0] == 404
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


def test_launch_profile_requires_explicit_source_and_identity_configuration(tmp_path, pki):
    from openbexi_spell_server.store import ContextStore

    for profile in (True, "kubernetes", "retained-single-use"):
        store = ContextStore(tmp_path / str(uuid.uuid4()), "A")
        try:
            with pytest.raises(ValueError):
                Context(store, pki["listener"]["pin"], {}, worker_launch=profile)
        finally:
            store.close()


def test_controller_admission_is_one_shot_only_in_explicit_profile(setup, pki):
    from openbexi_spell_server.contracts import envelope

    enable(setup)
    preflight(setup["config"])
    body = envelope(
        "A", "alice", "execution.start", helpers.proof(setup["execution"]), str(uuid.uuid4())
    )
    status, reply = request(
        setup["server"], pki["listener"]["client"], "/v1/rpc", subject=None, payload=body
    )
    assert status == 200 and reply["result"]["hold_retained"] is True
    admitted = start_grant(reply["result"]["grant"])
    # No plaintext secret is replayed after a lost admission response.
    assert (
        request(setup["server"], pki["listener"]["client"], "/v1/rpc", subject=None, payload=body)[
            0
        ]
        == 403
    )
    assert call(setup, pki, admitted)[0] == 200


def test_worker_cannot_call_controller_admission(setup, pki):
    from openbexi_spell_server.contracts import envelope

    enable(setup)
    preflight(setup["config"])
    body = envelope(
        "A", "alice", "execution.start", helpers.proof(setup["execution"]), str(uuid.uuid4())
    )
    assert (
        request(setup["server"], pki["worker"]["client"], "/v1/rpc", subject=None, payload=body)[0]
        == 404
    )
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


@pytest.mark.parametrize("failure", ["lost_reply", "wrong_receipt", "source_mismatch"])
def test_native_agent_never_launches_or_retries_without_a_definitive_consumption_receipt(
    setup, tmp_path, monkeypatch, failure
):
    import importlib.util
    from pathlib import Path
    import sys
    import types

    admitted = grant(setup)
    native_calls, requests = [], []

    def forbidden(*args, **kwargs):
        native_calls.append(True)
        raise AssertionError("Native process opened without a definitive consumption receipt")

    monkeypatch.setitem(sys.modules, "native", types.SimpleNamespace(NativeSession=forbidden))
    if "openbexi_spell_dss" not in sys.modules:
        parent = types.ModuleType("openbexi_spell_dss")
        parent.__path__ = []
        monkeypatch.setitem(sys.modules, "openbexi_spell_dss", parent)
    monkeypatch.setitem(
        sys.modules, "openbexi_spell_dss.relay", types.SimpleNamespace(Relay=forbidden)
    )
    path = Path(__file__).resolve().parents[2] / "host_runtime/python/v08_worker.py"
    spec = importlib.util.spec_from_file_location("v08_worker_failure_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "readonly_tree", lambda _: tmp_path)
    monkeypatch.setattr(
        module,
        "os",
        types.SimpleNamespace(statvfs=lambda _: types.SimpleNamespace(f_flag=1), ST_RDONLY=1),
    )
    monkeypatch.setattr(
        module,
        "preflight",
        lambda *args, **kwargs: (
            {"source_sha256": "a" * 64},
            {"manifest": {"entrypoint": "main.py"}},
        ),
    )
    monkeypatch.setattr(
        module,
        "verify_directory",
        lambda *args: ("b" if failure == "source_mismatch" else "a") * 64,
    )
    monkeypatch.setattr(module, "tls_context", lambda *args: None)
    monkeypatch.setattr(module, "Relay", forbidden)

    class Route:
        def __init__(self, *args):
            pass

        def call(self, request, **kwargs):
            requests.append(kwargs["path"])
            if failure == "lost_reply":
                raise Fault(503, "context_unavailable")
            return {"consumed": True, "request_id": "a different request"}

    monkeypatch.setattr(module, "Route", Route)
    with pytest.raises((Fault, RuntimeError)):
        module.run(
            dict(
                preflight=setup["config"],
                grant=asdict(admitted),
                start_barrier=str(tmp_path / "start"),
            )
        )
    assert not native_calls
    assert requests == ([] if failure == "source_mismatch" else ["/v1/worker/consume"])
