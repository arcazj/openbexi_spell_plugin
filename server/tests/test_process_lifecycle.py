"""Real independent Listener/Context processes. No native Executor is simulated as qualified."""

import http.client
import json
import os
import select
import subprocess
import sys
from pathlib import Path

from openbexi_spell_server.contracts import canonical

ALICE = "a" * 64
ALL = ["context:read", "blackboard:read", "blackboard:admin"]


def test_independent_process_restart_and_durable_context_recovery(tmp_path, pki):
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    running = []
    trace = {"schema": 1, "native_executor_tested": False, "runtime_enabled": False}

    def start(role, name, extra, *, port=0):
        cert = pki[name]
        config = dict(
            ca=str(pki["ca"]),
            certificate=str(cert["cert"]),
            key=str(cert["key"]),
            bind="127.0.0.1",
            port=port,
            allowed_hosts=[],
            max_handlers=16,
            **extra,
        )
        path = tmp_path / (name + ".json")
        path.write_bytes(canonical(config))
        process = subprocess.Popen(
            [sys.executable, "-m", "openbexi_spell_server", role, "--config", str(path)],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        running.append(process)
        ready, _, _ = select.select([process.stdout], [], [], 7)
        assert ready, "Service did not announce readiness"
        line = process.stdout.readline()
        assert line, "Service exited before readiness"
        ready = json.loads(line)
        assert ready["runtime_enabled"] is False
        return process, ready["port"]

    def call(port, path, body=None, key=None):
        client = http.client.HTTPSConnection(
            "localhost", port, context=pki["edge"]["client"], timeout=3
        )
        headers = {"X-OpenBEXI-Client-Fingerprint": ALICE}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = key
        try:
            client.request(
                "GET" if body is None else "POST",
                path,
                None if body is None else canonical(body),
                headers,
            )
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def stop(process, *, crash=False):
        if crash:
            process.kill()
        else:
            process.terminate()
        process.wait(timeout=5)

    a_extra = dict(
        context_id="A",
        state_directory=str(tmp_path / "state-A"),
        listener_fingerprint=pki["listener"]["pin"],
        subjects={"alice": ALL},
    )
    b_extra = dict(
        context_id="B",
        state_directory=str(tmp_path / "state-B"),
        listener_fingerprint=pki["listener"]["pin"],
        subjects={"alice": ALL},
    )
    try:
        a, a_port = start("context", "context-a", a_extra)
        b, b_port = start("context", "context-b", b_extra)
        listener_extra = dict(
            edge_fingerprint=pki["edge"]["pin"],
            identities={ALICE: "alice"},
            scopes={"alice": ["A", "B"]},
            contexts={
                "A": dict(url=f"https://localhost:{a_port}", fingerprint=pki["context-a"]["pin"]),
                "B": dict(url=f"https://localhost:{b_port}", fingerprint=pki["context-b"]["pin"]),
            },
        )
        listener, port = start("listener", "listener", listener_extra)
        status, first = call(port, "/v1/contexts/A/snapshot")
        assert status == 200
        first = first["result"]
        _, before_b = call(port, "/v1/contexts/B/snapshot")
        status, changed = call(
            port,
            "/v1/contexts/A/blackboard",
            dict(key="durable", expected_revision=0, value=42),
            "write-1",
        )
        assert status == 200
        stop(listener, crash=True)
        assert a.poll() is None and b.poll() is None
        listener2, port2 = start("listener", "listener", listener_extra)
        status, same = call(port2, "/v1/contexts/A/snapshot")
        assert status == 200 and same["result"]["incarnation"] == first["incarnation"]
        assert same["result"]["blackboard_revisions"] == {"durable": 1}
        assert call(port2, "/v1/contexts/B/snapshot")[1] == before_b
        stop(a, crash=True)
        assert listener2.poll() is None and b.poll() is None
        assert call(port2, "/v1/contexts/A/health")[0] == 503
        assert call(port2, "/v1/contexts/B/health")[0] == 200
        a2, _ = start("context", "context-a", a_extra, port=a_port)
        status, restored = call(port2, "/v1/contexts/A/blackboard")
        assert status == 200
        restored = restored["result"]
        assert restored["incarnation"] != first["incarnation"]
        assert restored["blackboard"] == {"durable": {"revision": 1, "value": 42}}
        assert restored["sequence"] > changed["result"]["sequence"]
        trace.update(
            listener_pids=[listener.pid, listener2.pid],
            context_a_pids=[a.pid, a2.pid],
            context_b_pid=b.pid,
            initial_incarnation=first["incarnation"],
            recovered_incarnation=restored["incarnation"],
            recovered_sequence=restored["sequence"],
            listener_restart_preserves_contexts=True,
            context_restart_preserves_other=True,
        )
        assert len({listener.pid, listener2.pid, a.pid, a2.pid, b.pid}) == 5
        if destination := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
            target = Path(destination)
            target.mkdir(parents=True, exist_ok=True)
            (target / "process-trace.json").write_bytes(canonical(trace))
    finally:
        for process in reversed(running):
            if process.poll() is None:
                stop(process)
            process.stdout.close()
            process.stderr.close()
