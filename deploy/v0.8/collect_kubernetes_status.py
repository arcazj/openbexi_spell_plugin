"""Retain bounded rollout status without logs, messages, env or credentials."""

import argparse
import json
from pathlib import Path
import subprocess


def summarize(document):
    pods = []
    for item in document.get("items", [])[:64]:
        status = item.get("status", {})
        containers = []
        for container in status.get("containerStatuses", [])[:8]:
            state = container.get("state", {})
            kind = next((k for k in ("waiting", "running", "terminated") if k in state), "unknown")
            detail = state.get(kind, {})
            containers.append({
                "name": str(container.get("name", ""))[:128],
                "image": str(container.get("image", ""))[:256],
                "ready": container.get("ready") is True,
                "restart_count": container.get("restartCount"),
                "state": kind,
                "reason": str(detail.get("reason", ""))[:128],
                "exit_code": detail.get("exitCode"),
            })
        pods.append({"name": str(item.get("metadata", {}).get("name", ""))[:128],
                     "phase": str(status.get("phase", ""))[:64], "containers": containers})
    return {"schema": "openbexi.v08.kubernetes-status/1", "pods": pods,
            "pod_limit_reached": len(document.get("items", [])) > 64,
            "full_v08_qualified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["kubectl", "--request-timeout=10s", "-n", "openbexi-v08", "get", "pods", "-o", "json"],
            capture_output=True, timeout=15, check=True,
        )
        if len(result.stdout) > 4 * 1024 * 1024:
            raise ValueError("Status response exceeds bound")
        report = summarize(json.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        # API/server error text can contain configuration: keep only its type.
        report = {"schema": "openbexi.v08.kubernetes-status/1",
                  "collection_error_type": type(error).__name__, "full_v08_qualified": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
