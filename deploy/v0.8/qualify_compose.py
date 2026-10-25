"""Executed HTTPS/mTLS Compose prelaunch integration acceptance (not v0.8 release).

Actual network probes cover desktop certificates, gateway, Listener, two
isolated stateful Contexts, denied permissions and restart persistence.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import ssl
import time
import uuid


class Probe:
    def __init__(self, root, port):
        self.root, self.port = Path(root), port
        self.expected = json.loads((self.root / "pins.json").read_text())["gateway"]

    def call(self, subject, method, path, data=None, key=None):
        directory = self.root / subject
        tls = ssl.create_default_context(cafile=str(directory / "ca.pem"))
        tls.minimum_version = ssl.TLSVersion.TLSv1_3
        tls.load_cert_chain(str(directory / "tls.crt"), str(directory / "tls.key"))
        client = http.client.HTTPSConnection("127.0.0.1", self.port, context=tls, timeout=3)
        try:
            client.connect()
            certificate = client.sock.getpeercert(binary_form=True)
            if hashlib.sha256(certificate).hexdigest() != self.expected:
                raise AssertionError("Pinned gateway leaf differs before any request")
            headers = {}
            raw = None
            if method == "POST":
                headers["Content-Type"] = "application/json"
                headers["Idempotency-Key"] = key or str(uuid.uuid4())
                raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
            client.request(method, path, raw, headers)
            response = client.getresponse()
            packet = response.read(65537)
            return response.status, json.loads(packet)
        finally:
            client.close()


def expect(probe, subject, path, status=200, method="GET", data=None, key=None):
    code, body = probe.call(subject, method, path, data, key)
    if code != status:
        # Never print credential material, raw request, variable data or token.
        raise AssertionError(f"Redacted {subject} {method} {path}: HTTP {code}, expected {status}")
    if code != 200:
        return None
    if body.get("schema") != "openbexi.listener/1":
        raise AssertionError("Expected certificate gateway -> Listener envelope")
    if path.startswith("/v1/contexts/"):
        nested = body.get("result")
        if not isinstance(nested, dict) or nested.get("schema") != "openbexi.context/1":
            raise AssertionError("Context mTLS delegation envelope missing")
        return nested["result"]
    return body


def ready(probe):
    end = time.monotonic() + 65
    last_failure = "no_probe_attempt"
    while time.monotonic() < end:
        try:
            code, body = probe.call("alice", "GET", "/v1/contexts/A/health")
            if code == 200:
                inner = body.get("result", {})
                if (inner.get("schema") == "openbexi.context/1"
                        and inner.get("result", {}).get("status") == "ready"):
                    return
            last_failure = "HTTP_" + str(code)
        except (OSError, TimeoutError, ssl.SSLError) as error:
            last_failure = type(error).__name__
        time.sleep(0.4)
    raise RuntimeError("mTLS Compose gateway/Context readiness: " + last_failure)


def run(root, port, phase, previous):
    probe = Probe(root, port)
    ready(probe)
    visible = expect(probe, "alice", "/v1/contexts")
    assert visible["contexts"] == ["A", "B"]
    assert expect(probe, "bob", "/v1/contexts")["contexts"] == ["B"]
    assert expect(probe, "observer", "/v1/contexts")["contexts"] == ["A"]
    expect(probe, "bob", "/v1/contexts/A/health", 403)
    expect(probe, "observer", "/v1/contexts/B/health", 403)
    health_a = expect(probe, "alice", "/v1/contexts/A/health")
    health_b = expect(probe, "alice", "/v1/contexts/B/health")
    observer = expect(probe, "observer", "/v1/contexts/A/health")
    assert observer["subject"] == "observer"
    assert "execution:control" not in observer["permissions"]
    assert health_a["context_id"] == "A" and health_b["context_id"] == "B"
    assert health_a["runtime_enabled"] is False and health_b["runtime_enabled"] is False
    # The public runtime must remain inaccessible even to the owner.
    expect(
        probe, "alice", "/v1/contexts/A/authority", 404, "POST",
        {"method": "execution.command", "payload": {}},
    )
    expect(
        probe, "observer", "/v1/contexts/A/blackboard", 403, "POST",
        {"key": "compose-check", "expected_revision": 0, "value": {"qualified": False}},
    )
    board_b = expect(probe, "alice", "/v1/contexts/B/blackboard")
    assert "compose-check" not in board_b["blackboard"]
    if phase == "before":
        board_a = expect(probe, "alice", "/v1/contexts/A/blackboard")
        assert "compose-check" not in board_a["blackboard"]
        key = str(uuid.uuid4())
        payload = {
            "key": "compose-check",
            "expected_revision": 0,
            "value": {"qualified": False, "scope": "prelaunch-only"},
        }
        written = expect(
            probe, "alice", "/v1/contexts/A/blackboard", 200, "POST", payload, key
        )
        replay = expect(
            probe, "alice", "/v1/contexts/A/blackboard", 200, "POST", payload, key
        )
        assert replay == written and written["revision"] == 1
        expect(
            probe, "alice", "/v1/contexts/A/blackboard", 409, "POST",
            {**payload, "expected_revision": 0},
        )
        cases = ["certificate_scope", "observer_write_denied", "runtime_disabled",
                 "isolated_state", "durable_cas_idempotency", "wrong_revision_denied"]
    else:
        if previous is None:
            raise ValueError("After-restart qualification requires original receipt")
        board_a = expect(probe, "alice", "/v1/contexts/A/blackboard")
        stored = board_a["blackboard"].get("compose-check")
        assert stored == {
            "revision": 1, "value": {"qualified": False, "scope": "prelaunch-only"}
        }
        assert health_a["incarnation"] != previous["incarnation_a"]
        assert health_b["incarnation"] == previous["incarnation_b"]
        assert "compose-check" not in board_b["blackboard"]
        cases = ["context_a_restart_incarnation_rotated",
                 "context_b_incarnation_unchanged", "context_a_durable_state",
                 "cross_context_isolation", "runtime_remains_disabled"]
    return {
        "schema": "openbexi.v08.compose-prelaunch/1",
        "phase": phase, "passed": True, "executed_checks": cases,
        "incarnation_a": health_a["incarnation"], "incarnation_b": health_b["incarnation"],
        "prelaunch_only": True, "native_runtime_qualified": False,
        "full_v08_qualified": False, "production_migration_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--port", type=int, default=19443)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous else None
    receipt = run(args.root, args.port, args.phase, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"phase": args.phase, "passed": True, "checks": len(receipt["executed_checks"])}))


if __name__ == "__main__":
    main()
