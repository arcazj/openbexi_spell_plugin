"""Durable agent-observed roster over real mTLS; no physical attestation claim."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.contracts import Fault, canonical, policy
from openbexi_spell_server.control import NativeControlJournal
from openbexi_spell_server.store import ContextStore
from test_launch import call
import test_child_gate as gates
import test_control as controls
import test_family as families

source = gates.source
setup = gates.setup
family = gates.family
provider = gates.provider


@pytest.fixture
def journal(family):
    return NativeControlJournal(family["app"].authority)


def member(**changes):
    return dict(
        dict(
            target_admission_id=None,
            instance_id="main#1",
            pid=1234,
            parent_pid=1000,
            start_ticks=99,
            executable_sha256="a" * 64,
        ),
        **changes,
    )


def bind(family, pki, body=None, **options):
    return call(family, pki, family["grant"], "member-bind", **(body or member()), **options)


def rows(family):
    return family["store"].db.execute("SELECT * FROM native_members").fetchall()


def test_registration_route_requires_control_profile(family, pki):
    assert bind(family, pki)[0] == 404


@pytest.mark.parametrize("certificate", ["alice", "bob", "observer", "listener"])
def test_registration_rejects_non_worker(journal, family, pki, certificate):
    assert bind(family, pki, certificate=certificate)[0] in (403, 404)
    assert not rows(family)


def test_registration_original_winner_only_and_no_proof_escalation(journal, family, pki):
    assert bind(family, pki, runtime_capability="0" * 64)[0] == 403
    code, reply = bind(family, pki)
    assert code == 200
    receipt = reply["result"]
    assert receipt["state"] == "REGISTERED_UNPROVEN"
    assert receipt["registered"] and receipt["hold_retained"]
    assert all(
        receipt[key] is False
        for key in ("host_attested", "quiescence_proven", "effective_transfer", "runtime_enabled")
    )
    assert bind(family, pki)[0] == 409
    text = canonical([dict(row) for row in rows(family)]).decode()
    assert family["grant"].token not in text
    assert family["runtime_capabilities"][family["grant"].execution_id] not in text
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_registration_100_way_race_has_one_winner(journal, family, pki):
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: bind(family, pki)[0], range(100)))
    assert replies.count(200) == 1 and replies.count(409) == 99
    assert len(rows(family)) == 1


@pytest.mark.parametrize(
    "instance",
    [
        "other#1",
        "main#01",
        "main#1/..",
        "main#١",
        "main#-1",
        "main#1e2",
        "main#1000000000",
        True,
    ],
)
def test_registration_requires_exact_source_instance(journal, family, pki, instance):
    assert bind(family, pki, member(instance_id=instance))[0] == 400
    assert not rows(family)


@pytest.mark.parametrize(
    "change",
    [
        dict(pid=True),
        dict(pid=0),
        dict(pid=2**31),
        dict(parent_pid=1234),
        dict(parent_pid=False),
        dict(start_ticks=0),
        dict(start_ticks=1.0),
        dict(start_ticks=2**63),
        dict(executable_sha256="A" * 64),
        dict(quiescence_proven=True),
    ],
)
def test_registration_rejects_invalid_identity_or_extra_proof(journal, family, pki, change):
    assert bind(family, pki, member(**change))[0] == 400
    assert not rows(family)


def test_run_forward_and_consumption_require_durable_member(journal, family, pki):
    body = controls.operation()
    assert controls.admit(family, pki, body)[0] == 200
    assert controls.forward(family, pki, body)[0] == 403
    assert controls.consume(family, pki, body)[0] == 403
    assert bind(family, pki)[0] == 200
    assert controls.forward(family, pki, body)[0] == 200
    assert controls.consume(family, pki, body)[0] == 200
    assert rows(family)[0]["state"] == "REGISTERED_UNPROVEN"


def test_canonical_zero_root_suffix_retains_one_immutable_target(journal, family, pki):
    assert bind(family, pki, member(instance_id="main#0"))[0] == 200
    assert bind(family, pki, member(instance_id="main#1", pid=1235))[0] == 409
    assert len(rows(family)) == 1


def test_native_zero_child_suffix_can_forward_and_consume_once(journal, family, pki):
    # Frozen SPELLexecutorManager::getInstanceId starts a new procedure at #0.
    assert bind(family, pki)[0] == 200
    child = families.admit(family, pki)[1]["result"]["child_grant"]
    assert families.consume(family, pki, child)[0] == 200
    child_body = member(target_admission_id=child["admission_id"], instance_id="child#0", pid=1235)
    assert bind(family, pki, child_body)[0] == 200
    assert bind(family, pki, dict(child_body, instance_id="child#1", pid=1236))[0] == 409
    operation = dict(controls.operation(), target_admission_id=child["admission_id"])
    assert controls.admit(family, pki, operation)[0] == 200
    assert controls.forward(family, pki, operation)[0] == 200
    assert controls.consume(family, pki, operation)[0] == 200
    assert controls.consume(family, pki, operation)[0] == 409
    assert len(rows(family)) == 2


def test_children_require_consumed_target_and_original_registered_parent(journal, family, pki):
    assert bind(family, pki, member(target_admission_id=str(uuid.uuid4())))[0] == 403
    child = families.admit(family, pki)[1]["result"]["child_grant"]
    child_body = member(target_admission_id=child["admission_id"], instance_id="child#1", pid=1235)
    assert bind(family, pki, child_body)[0] == 403
    assert families.consume(family, pki, child)[0] == 200
    assert bind(family, pki, child_body)[0] == 403
    assert bind(family, pki)[0] == 200
    assert bind(family, pki, dict(child_body, parent_pid=1001))[0] == 403
    assert bind(family, pki, dict(child_body, executable_sha256="b" * 64))[0] == 403
    assert bind(family, pki, dict(child_body, pid=1234))[0] == 409
    assert bind(family, pki, child_body)[0] == 200
    assert bind(family, pki, dict(child_body, pid=1236, instance_id="child#2"))[0] == 409
    assert len(rows(family)) == 2
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


@pytest.mark.parametrize("fence", ["disconnect", "revoked", "source_changed", "manifest_changed"])
def test_registration_rechecks_live_origin_and_source(journal, family, pki, fence):
    if fence == "disconnect":
        family["controller"]("session.close", dict(connection_id=family["connection"]))
    elif fence == "revoked":
        family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    elif fence == "source_changed":
        family["app"].catalog.entries["procedure"]["runtime_image"] = "sha256:" + "b" * 64
    else:
        entry = family["app"].catalog.entries["procedure"]
        manifest = json.loads(entry["manifest"])
        manifest["entrypoint"] = "child.py"
        entry["manifest"] = json.dumps(manifest)
    assert bind(family, pki)[0] == 403
    assert not rows(family)


def test_child_registration_cannot_use_changed_catalog_binding(journal, family, pki):
    assert bind(family, pki)[0] == 200
    child = families.admit(family, pki)[1]["result"]["child_grant"]
    assert families.consume(family, pki, child)[0] == 200
    family["app"].catalog.entries["child"]["runtime_image"] = "sha256:" + "b" * 64
    child_body = member(target_admission_id=child["admission_id"], instance_id="child#1", pid=1235)
    assert bind(family, pki, child_body)[0] == 403
    assert len(rows(family)) == 1
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


def test_registration_audit_failure_rolls_back_and_retains_hold(journal, family, pki):
    store = family["store"]
    store.max_events = store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert bind(family, pki)[0] == 503
    assert not rows(family)
    assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1


def test_restart_fences_roster_without_replacing_member_identity(journal, family, pki):
    assert bind(family, pki)[0] == 200
    before = dict(rows(family)[0])
    old = family["store"]
    directory = Path(old.db.execute("PRAGMA database_list").fetchone()[2]).parent
    old.close()
    store = ContextStore(directory, "A")
    try:
        authority = ExecutionAuthority(store, family["app"].subjects)
        restarted = NativeControlJournal(authority)
        after = dict(store.db.execute("SELECT * FROM native_members").fetchone())
        assert after == dict(before, state="RESTART_FENCED")
        with pytest.raises(Fault):
            restarted.bind_member(family["grant"], member())
        assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        store.close()


@pytest.mark.parametrize("outcome", ["lost", "forged"])
def test_agent_cannot_rebind_after_lost_or_forged_receipt(journal, provider, family, outcome):
    session = SimpleNamespace(instance="main#1", request=lambda *_a, **_k: None)
    agent = controls.module.NativeRunJournal(session, provider.request, provider.route, provider)
    route = agent.route

    def change(payload, **options):
        answer = route.call(payload, **options)
        if outcome == "lost":
            raise TimeoutError("Injected registration response loss")
        return dict(answer, host_attested=True)

    agent.route = SimpleNamespace(call=change)
    with pytest.raises(TimeoutError if outcome == "lost" else ValueError):
        agent.bind_member("main#1", 1234, 1000, 99, "a" * 64)
    with pytest.raises(ValueError, match="already attempted"):
        agent.bind_member("main#1", 1235, 1000, 100, "a" * 64)
    assert not agent.bound_members and len(rows(family)) == 1
    assert rows(family)[0]["state"] == "REGISTERED_UNPROVEN"


def test_failed_durable_registration_closes_pin_without_allowing_member():
    server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
    server.gate = SimpleNamespace(started={"main#1": None})
    server.executor = Path("/candidate/executor")
    server.executor_sha256 = "a" * 64
    server.context_pid = 1000
    server.members, server.member_pids = {}, {}
    read_fd, write_fd = os.pipe()
    server.pin_process = lambda *_args: read_fd
    server.process_identity = lambda *_args: "99"

    def unavailable(*_args):
        raise TimeoutError("Injected durable registration outage")

    server.controls = SimpleNamespace(bind_member=unavailable)
    try:
        with pytest.raises(TimeoutError):
            server.register(dict(schema="openbexi.native-member/1", instance_id="main#1", pid=1234))
        with pytest.raises(OSError):
            os.fstat(read_fd)
        assert not server.members and not server.member_pids
    finally:
        os.close(write_fd)


@pytest.mark.parametrize("role", ["context", "executor"])
def test_native_peer_death_during_identity_read_cannot_authorize_callback(role):
    """Real pidfd death after a held identity result; wire/proc checks run separately."""
    import struct
    import subprocess
    import sys

    child = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time;time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
    server.listener = lambda: SimpleNamespace(pid=os.getpid(), poll=lambda: None)
    server.executable = server.executor = Path(sys.executable).resolve()
    server.context_pid = child.pid if role == "context" else os.getpid()
    server.pidfd = os.pidfd_open(server.context_pid)
    server.members, server.member_pids = {}, {}
    member_fd = None
    if role == "executor":
        member_fd = os.pidfd_open(child.pid)
        server.members["main#1"] = (child.pid, member_fd)
        server.member_pids[child.pid] = "main#1"

    def die_after_read(*_args):
        # Inject the interval immediately after a successful metadata check.
        # Real SO_PEERCRED and /proc validation have mandatory hosted controls.
        child.terminate()
        child.wait(timeout=3)
        return "99"

    server.process_identity = die_after_read
    stream = SimpleNamespace(
        getsockopt=lambda *_args: struct.pack("3i", child.pid, os.getuid(), os.getgid())
    )
    try:
        with pytest.raises(ValueError, match="incarnation differs"):
            server.authenticate(stream)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        os.close(server.pidfd)
        if member_fd is not None:
            os.close(member_fd)
