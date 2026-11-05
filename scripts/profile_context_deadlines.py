"""Run each original deadline check in isolation, with optional external tracing.

This is diagnostic tooling, not a qualification gate or a substitute for the
complete foundation suite. Never changes timeouts, fixtures, assertions or PRAGMAs.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

CHECKS = {
    "burst2": "test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss[2]",
    "burst3": "test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss[3]",
    "barrier": "test_ten_pending_receipts_bound_eleventh_rpc_without_effect[complete]",
}


def snapshot():
    result = {"monotonic_ns": time.monotonic_ns()}
    for name in (
        "cpu.stat",
        "memory.current",
        "memory.swap.current",
        "memory.events",
        "cpu.pressure",
        "io.pressure",
        "memory.pressure",
        "io.stat",
        "pids.current",
    ):
        path = Path("/sys/fs/cgroup") / name
        if path.exists():
            result[name] = path.read_text()
    result["loadavg"] = Path("/proc/loadavg").read_text()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("profile", "control"),
        default=["profile", "control"],
    )
    parser.add_argument("--checks", nargs="+", choices=CHECKS, default=list(CHECKS))
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = {}
    for folder in (
        "server",
        "driver_plugin/src",
        "src/dss",
        "scripts/deadline_observer",
    ):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".c", ".json", ".lock"}:
                inputs[str(path.relative_to(root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    packages = {
        d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
    }
    (output / "inputs.json").write_text(
        json.dumps(
            dict(
                source_sha256=inputs,
                python=sys.version,
                executable=sys.executable,
                sqlite=sqlite3.sqlite_version,
                platform=platform.platform(),
                packages=packages,
                tempdir=os.environ.get("TMPDIR", "/tmp"),
                original_deadlines_seconds=[2, 3, 1.5],
                timing_categories_overlap=True,
                diagnostic_only=True,
            ),
            indent=2,
        )
    )
    observer = root / "scripts/deadline_observer"
    library = output / "durable_io.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            str(observer / "durable_io.c"),
            "-o",
            str(library),
        ],
        check=True,
    )
    results = []
    for repeat in range(args.repeat):
        for mode in args.modes:
            for check in args.checks:
                target = output / f"{repeat}-{mode}-{check}"
                target.mkdir()
                env = dict(
                    os.environ,
                    PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                    OPENBEXI_SERVER_EVIDENCE_DIR=str(target),
                    QT_QPA_PLATFORM="offscreen",
                )
                nodeid = "server/tests/test_native_driver.py::" + CHECKS[check]
                command = [
                    sys.executable,
                    "-m",
                    "pytest",
                    nodeid,
                    "-v",
                    "-W",
                    "error",
                    "--tb=long",
                    "--junitxml=" + str(target / "tests.xml"),
                ]
                if mode == "profile":
                    env.update(
                        OPENBEXI_DEADLINE_TRACE=str(target),
                        OPENBEXI_DEADLINE_ROOT=str(root),
                        PYTHONPATH=str(observer),
                        LD_PRELOAD=str(library),
                    )
                    command.extend(["-p", "observer"])
                started = time.monotonic()
                with (
                    (target / "command.log").open("wb") as log,
                    (target / "runner.jsonl").open("w") as telemetry,
                ):
                    process = subprocess.Popen(
                        command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                    expired = False
                    while process.poll() is None:
                        telemetry.write(json.dumps(snapshot()) + "\n")
                        telemetry.flush()
                        if time.monotonic() - started > 90:
                            expired = True
                            process.kill()
                            process.wait()
                            break
                        time.sleep(0.25)
                result = dict(
                    check=check,
                    mode=mode,
                    repeat=repeat,
                    command=command,
                    exit_code=process.returncode,
                    outer_timeout=expired,
                    elapsed_seconds=time.monotonic() - started,
                )
                if (target / "tests.xml").exists():
                    result["junit"] = ET.parse(target / "tests.xml").getroot()[0].attrib
                results.append(result)
                (output / "results.json").write_text(json.dumps(results, indent=2))
                print(json.dumps(result), flush=True)
    return int(any(result["exit_code"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
