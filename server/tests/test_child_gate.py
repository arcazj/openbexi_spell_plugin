"""Native provider control flow over real Context mTLS; C++/native run in CI."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from openbexi_spell_server.contracts import Fault, policy
from openbexi_spell_server.transport import Route
import test_family as families


@pytest.fixture
def source(tmp_path):
    return families.source.__wrapped__(tmp_path)


@pytest.fixture
def setup(tmp_path, pki, source):
    yield from families.setup.__wrapped__(tmp_path, pki, source)


@pytest.fixture
def family(setup, pki):
    return families.family.__wrapped__(setup, pki)


spec = importlib.util.spec_from_file_location(
    "native_child_gate_test",
    Path(__file__).resolve().parents[2] / "host_runtime/python/child_gate.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NativeChildGate = module.NativeChildGate


def body(entrypoint="child.py", parent="main#1", **changes):
    value = dict(
        schema="openbexi.native-start/1",
        instance_id=entrypoint[:-3] + "#1",
        parent_instance_id=parent,
        entrypoint=entrypoint,
        arguments="{'value': 42}",
        mode=dict(automatic=True, visible=True, blocking=False),
    )
    value.update(changes)
    return value


@pytest.fixture
def provider(family, pki):
    request = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(family["grant"]),
        runtime_capability=family["runtime_capabilities"][family["grant"].execution_id],
    )
    route = Route(family["config"]["context_url"], pki["context-a"]["pin"], pki["worker"]["client"])
    gate = NativeChildGate(request, route, "main.py", "main#1", "{}", lambda: None)
    gate.admit(body("main.py", "", arguments="{}"))
    return gate


def test_original_family_consumes_before_native_callback_and_preserves_nested_parent(
    provider, family
):
    provider.admit(body())
    provider.admit(body("grand.py", "child#1"))
    rows = (
        family["store"]
        .db.execute("SELECT id,parent_id,state FROM child_admissions ORDER BY rowid")
        .fetchall()
    )
    assert len(rows) == 2 and all(row["state"] == "CONSUMED" for row in rows)
    assert rows[0]["parent_id"] is None and rows[1]["parent_id"] == rows[0]["id"]
    with pytest.raises(ValueError, match="already attempted"):
        provider.admit(body())
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 3


@pytest.mark.parametrize("visible", [True, False])
@pytest.mark.parametrize("automatic", [True, False])
@pytest.mark.parametrize("blocking", [True, False])
def test_all_mode_bindings_use_same_before_spawn_authority(
    provider, family, visible, automatic, blocking
):
    provider.admit(body(mode=dict(visible=visible, automatic=automatic, blocking=blocking)))
    assert (
        family["store"].db.execute("SELECT state FROM child_admissions").fetchone()[0] == "CONSUMED"
    )


@pytest.mark.parametrize("stage", ["child-admit", "child-consume"])
def test_lost_authority_reply_never_retries_or_permits_native_start(provider, family, stage):
    real = provider.route
    calls = []

    def lost(payload, **kwargs):
        calls.append(kwargs["path"])
        reply = real.call(payload, **kwargs)
        if kwargs["path"].endswith(stage):
            raise TimeoutError("Injected lost reply after real durable commit")
        return reply

    provider.route = SimpleNamespace(call=lost)
    with pytest.raises(TimeoutError):
        provider.admit(body())
    assert "child#1" not in provider.started
    with pytest.raises(ValueError, match="already attempted"):
        provider.admit(body())
    assert calls.count("/v1/worker/" + stage) == 1
    expected = "ADMITTED" if stage == "child-admit" else "CONSUMED"
    assert (
        family["store"].db.execute("SELECT state FROM child_admissions").fetchone()[0] == expected
    )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 2


def test_20_concurrent_provider_requests_consume_one_admission(provider, family):
    def attempt(_):
        try:
            provider.admit(body())
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(20))) == 1
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 1


def test_revoked_parent_denies_before_native_callback(provider, family):
    family["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    with pytest.raises(Fault):
        provider.admit(body())
    assert "child#1" not in provider.started
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "changes",
    [
        dict(parent_instance_id="unknown#1"),
        dict(parent_instance_id=""),
        dict(instance_id="child#0"),
        dict(instance_id="child#01"),
        dict(instance_id="child#1/../../main"),
        dict(entrypoint="../child.py"),
        dict(arguments=42),
        dict(mode=dict(visible=1, automatic=True, blocking=False)),
    ],
)
def test_unbound_native_identity_or_configuration_cannot_spawn(provider, family, changes):
    with pytest.raises((ValueError, Fault)):
        provider.admit(body(**changes))
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 0


def test_copied_original_configuration_has_no_consumer_proof(provider, family):
    provider.request = {**provider.request, "runtime_capability": "0" * 64}
    with pytest.raises(Fault):
        provider.admit(body())
    assert family["store"].db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0] == 0


def test_native_context_peer_uses_exact_owned_parent_executable_and_incarnation(tmp_path):
    # Exercise real Linux SO_PEERCRED/pidfd, without claiming this Python helper
    # is a native Context or bypassing the production readonly-image check.
    server = module.NativeAdmissionServer.__new__(module.NativeAdmissionServer)
    import os

    server.listener = lambda: SimpleNamespace(pid=os.getpid(), poll=lambda: None)
    server.executable = Path(sys.executable).resolve()
    server.context_pid, server.pidfd = None, None
    endpoint = str(tmp_path / "peer.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(endpoint)
    listener.listen(2)
    listener.settimeout(3)
    script = "import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1]);s.recv(1);s.close()"
    first = subprocess.Popen([sys.executable, "-I", "-c", script, endpoint])
    try:
        with listener.accept()[0] as stream:
            server.authenticate(stream)
            assert server.context_pid == first.pid
            stream.sendall(b"x")
        assert first.wait(timeout=3) == 0
        second = subprocess.Popen([sys.executable, "-I", "-c", script, endpoint])
        try:
            with listener.accept()[0] as stream:
                with pytest.raises(ValueError, match="incarnation differs"):
                    server.authenticate(stream)
                stream.sendall(b"x")
            assert second.wait(timeout=3) == 0
        finally:
            if second.poll() is None:
                second.kill()
                second.wait()
    finally:
        listener.close()
        if first.poll() is None:
            first.kill()
            first.wait()
        if server.pidfd is not None:
            os.close(server.pidfd)
