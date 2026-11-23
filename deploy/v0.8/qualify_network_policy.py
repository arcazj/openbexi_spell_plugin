"""Verify the deployed prelaunch network allowlist using the real service Pods."""

import argparse
import json
from pathlib import Path
import subprocess

NS = "openbexi-v08"
CONNECT = """
import json, socket, sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=2):
        outcome = 'connected'
except TimeoutError:
    outcome = 'timeout'
except PermissionError:
    outcome = 'policy_denied'
print(json.dumps({'outcome':outcome}))
"""


def kubectl(*args):
    return subprocess.check_output(["kubectl", *args], text=True, timeout=30)


def verify(output):
    record = {
        "passed": False,
        "scope": "Five prelaunch services on a three-node kind cluster with Calico",
        "checks": [],
    }
    try:
        nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
        record["nodes"] = {
            n["metadata"]["name"]: n["status"]["nodeInfo"]["kubeletVersion"]
            for n in nodes
        }
        assert len(record["nodes"]) == 3
        cni = json.loads(
            kubectl(
                "-n", "calico-system", "get", "daemonset", "calico-node", "-o", "json"
            )
        )
        assert cni["status"]["numberReady"] == len(nodes)
        record["cni_images"] = [
            c["image"] for c in cni["spec"]["template"]["spec"]["containers"]
        ]
        pods = json.loads(kubectl("-n", NS, "get", "pods", "-o", "json"))["items"]
        roles = {
            p["metadata"]["labels"]["app"]: p
            for p in pods
            if p["status"]["phase"] == "Running"
        }
        record["pods"] = {
            k: {"uid": p["metadata"]["uid"], "node": p["spec"]["nodeName"]}
            for k, p in roles.items()
        }
        policies = json.loads(
            kubectl("-n", NS, "get", "networkpolicies", "-o", "json")
        )["items"]
        record["policies"] = {
            p["metadata"]["name"]: p["metadata"]["uid"] for p in policies
        }
        assert "v08-default-deny" in record["policies"]

        def probe(source, target, port, allowed):
            pod_name = roles[source]["metadata"]["name"]
            address = roles[target]["status"]["podIP"]
            raw = kubectl(
                "-n",
                NS,
                "exec",
                pod_name,
                "--",
                "python",
                "-I",
                "-c",
                CONNECT,
                address,
                str(port),
            )
            outcome = json.loads(raw)["outcome"]
            record["checks"].append(
                dict(
                    source=source,
                    target=target,
                    port=port,
                    allowed=allowed,
                    outcome=outcome,
                )
            )
            assert outcome in (
                {"connected"} if allowed else {"timeout", "policy_denied"}
            ), record["checks"][-1]

        for target, port, allowed_peer in (
            ("dss", 8085, "context-a"),
            ("context-a", 9441, "listener"),
        ):
            probe(allowed_peer, target, port, True)
            probe("gateway", target, port, False)
            probe(allowed_peer, target, port, True)
        probe("gateway", "listener", 9444, True)
        record["passed"] = True
    finally:
        output.parent.mkdir(exist_ok=True, parents=True)
        output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    verify(parser.parse_args().output)
