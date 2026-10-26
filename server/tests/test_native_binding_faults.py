"""Compiled admission channel plus real Context mTLS/durable member binding.

The admitted peer role and process pins are fixtures. This tests the post-bind
reply boundary, not native process identity, image immutability or historical cause.
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import threading
from types import SimpleNamespace

import pytest

import test_members as members
import test_native_admission_channel as channel

source = members.source
setup = members.setup
family = members.family
provider = members.provider
journal = members.journal
admission_binary = channel.admission_binary


@pytest.mark.parametrize("fault", ["timely", "drop_after_bind", "delay_after_bind"])
def test_native_reply_after_durable_binding_never_rebinds(
    admission_binary, journal, provider, family, tmp_path, fault
):
    session = SimpleNamespace(instance="main#1", request=lambda *_a, **_k: None)
    agent = members.controls.module.NativeRunJournal(
        session, provider.request, provider.route, provider
    )
    server = members.gates.module.NativeAdmissionServer.__new__(
        members.gates.module.NativeAdmissionServer
    )
    server.stop = threading.Event()
    server.runtime = None
    server.gate, server.controls = provider, agent
    server.executor, server.executor_sha256 = Path("/fixture/executor"), "a" * 64
    server.context_pid = 1000
    server.members, server.member_pids = {}, {}
    context_read, context_write = os.pipe()
    member_read, member_write = os.pipe()
    server.pidfd = os.dup(context_read)
    server.pin_process = lambda *_: os.dup(member_read)
    server.process_identity = lambda *_: "99"
    server.authenticate = lambda _stream: ("context", None)
    server.gui = SimpleNamespace(close=lambda: None)
    bound, denied = threading.Event(), threading.Event()
    reports, accepted = [], []

    def report(event, **details):
        reports.append(dict(event=event, **details))
        if event == "native-executor-bound":
            bound.set()
            if fault == "delay_after_bind":
                # Deliberately cross the unchanged native four-second deadline.
                threading.Event().wait(4.2)
            elif fault == "drop_after_bind":
                accepted[-1].shutdown(socket.SHUT_RDWR)
        if event == "native-before-spawn-denied":
            denied.set()

    server.report = report
    endpoint = str(tmp_path / "bound.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(endpoint)
    listener.listen(2)
    listener.settimeout(0.1)

    def accept():
        stream, address = listener.accept()
        accepted.append(stream)
        return stream, address

    server.socket = SimpleNamespace(accept=accept, close=listener.close)
    server.thread = threading.Thread(target=server.serve)
    server.thread.start()
    try:
        result = subprocess.run(
            [str(admission_binary), "member_exchange", endpoint, str(os.getpid())],
            capture_output=True,
            timeout=8,
        )
        assert result.returncode == 0, result.stderr
        outcome = json.loads(result.stdout)
        assert bound.is_set() and len(accepted) == 1
        if fault == "timely":
            assert outcome["admitted"] and not outcome["reason"]
        else:
            assert not outcome["admitted"]
            assert denied.wait(2), "Provider did not report its failed reply"
            failure = next(r for r in reports if r["event"] == "native-before-spawn-denied")
            assert failure["phase"] == "reply"
            assert failure["error_type"] == "BrokenPipeError"
            if fault == "delay_after_bind":
                assert outcome["reason"] == "deadline_expired"
                assert 3900 <= outcome["elapsed_ms"] < 5000
            else:
                assert outcome["reason"] in {"reply_lost", "channel_unavailable"}
        rows = members.rows(family)
        assert len(rows) == 1 and rows[0]["state"] == "REGISTERED_UNPROVEN"
        assert set(agent.bound_members) == {"main#1"}
        with pytest.raises(ValueError, match="already bound"):
            server.register(dict(schema="openbexi.native-member/1", instance_id="main#1", pid=1234))
        with pytest.raises(ValueError, match="already attempted"):
            agent.bind_member("main#1", 1235, 1000, 100, "a" * 64)
        assert len(members.rows(family)) == len(accepted) == 1
        assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
        evidence = os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR")
        if evidence:
            with (Path(evidence) / "reliability-faults.jsonl").open("a") as trace:
                trace.write(
                    json.dumps(
                        dict(
                            fault=fault,
                            passed=True,
                            native_outcome=outcome,
                            provider_events=reports,
                            bindings=1,
                            connections=1,
                            rebinding_denied=True,
                            holds_retained=True,
                            peer_role_and_process_pins="fixtures",
                            historical_cause_established=False,
                        )
                    )
                    + "\n"
                )
    finally:
        server.close()
        for descriptor in (context_read, context_write, member_read, member_write):
            os.close(descriptor)
