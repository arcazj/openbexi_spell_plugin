"""Record the actual runner without exposing credentials or changing acceptance limits."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def command(arguments):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=10)
        return {"exit_code": result.returncode, "stdout": result.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": type(error).__name__}


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def collect(root, profile):
    contract = root / "docs/v0.8/QUALIFICATION_ENVIRONMENTS.json"
    versions = {}
    for name in (
        "openbexi-ide",
        "PySide6-Essentials",
        "shiboken6",
        "grpcio",
        "protobuf",
        "pytest",
        "ruff",
        "mypy",
    ):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    cpuinfo = read("/proc/cpuinfo") or ""
    cpu_model = next(
        (
            line.split(":", 1)[1].strip()
            for line in cpuinfo.splitlines()
            if line.startswith("model name")
        ),
        platform.processor(),
    )
    disk = shutil.disk_usage(root)
    docker = command(["docker", "info", "--format", "{{json .}}"])
    if docker.get("exit_code") == 0:
        try:
            raw = json.loads(docker["stdout"])
            docker = {
                key: raw.get(key)
                for key in (
                    "ServerVersion",
                    "OSType",
                    "Architecture",
                    "KernelVersion",
                    "NCPU",
                    "MemTotal",
                    "Driver",
                    "CgroupVersion",
                    "ContainersRunning",
                )
            }
        except ValueError:
            docker = {"error": "invalid_docker_info"}
    else:
        docker.pop("stdout", None)
    status = command(["git", "-C", str(root), "status", "--porcelain"])
    return {
        "schema": "openbexi.qualification-environment/1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "qualification_pass": False,
        "scope": "Runner observation only; no workload acceptance inferred",
        "contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
        "git_head": command(["git", "-C", str(root), "rev-parse", "HEAD"]),
        "working_tree_dirty": bool(status["stdout"])
        if status.get("exit_code") == 0
        else None,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "os_release": read("/etc/os-release"),
        "cpu_model": cpu_model,
        "cpu_count": os.cpu_count(),
        "cpu_affinity_count": len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "python": sys.version,
        "python_executable_sha256": hashlib.sha256(
            Path(sys.executable).read_bytes()
        ).hexdigest(),
        "packages": versions,
        "memory": read("/proc/meminfo"),
        "disk": {"total_bytes": disk.total, "free_bytes": disk.free},
        "cgroup": {
            name: read("/sys/fs/cgroup/" + name)
            for name in (
                "cpu.max",
                "cpu.stat",
                "memory.max",
                "memory.current",
                "memory.events",
                "memory.swap.max",
                "memory.swap.current",
                "pids.max",
                "pids.current",
            )
        },
        "pressure": {
            name: read("/proc/pressure/" + name) for name in ("cpu", "memory", "io")
        },
        "docker": docker,
        "tools": {
            name: command(args)
            for name, args in (
                ("git", ["git", "--version"]),
                ("compiler", ["c++", "--version"]),
                ("libc", ["ldd", "--version"]),
            )
        },
        "ci": {
            name: os.environ.get(name)
            for name in (
                "ImageOS",
                "ImageVersion",
                "RUNNER_OS",
                "RUNNER_ARCH",
                "GITHUB_SHA",
                "GITHUB_RUN_ID",
                "GITHUB_RUN_ATTEMPT",
                "GITHUB_JOB",
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(Path(__file__).resolve().parents[1], args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({"environment_receipt": str(args.output), "profile": args.profile})
    )


if __name__ == "__main__":
    main()
