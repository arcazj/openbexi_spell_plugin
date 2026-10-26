"""Run source-bound reliability fault probes; no historical cause or release claim."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".qualification/v08-faults" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    inputs = [
        *sorted((root / "server/src").rglob("*.py")),
        *sorted((root / "server/tests").rglob("*.py")),
        *sorted((root / "driver_plugin/src").rglob("*.py")),
        *sorted((root / "src/dss").rglob("*.py")),
        *sorted((root / "src/dss/data").glob("*.json")),
        *sorted((root / "host_runtime/python").glob("*.py")),
        *sorted((root / "host_runtime/native").glob("*.H")),
        root / "server/tests/native_admission_harness.cpp",
        root / "server/tests/native_spawn_legacy.cpp",
        root / "host_runtime/build_admission_context.py",
        root / "server/pyproject.toml",
        root / "server/requirements-test.lock",
        root / ".github/workflows/v08-server-foundation.yml",
        Path(__file__),
    ]
    report = dict(
        schema="openbexi.v08.fault-reproduction/1",
        git_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        python=platform.python_version(),
        source_sha256={
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
        passed=False,
        full_v08_qualified=False,
        historical_failure_causes_established=False,
        scope="Controlled ledger/DSS stage faults and restart; controller TLS/recovery boundaries; compiled native spawn, admission deadline and post-binding reply faults",
        process_identity_scope="Native binding tests use fixture peer roles/process pins and recovery tests use fixture host proof; Context mTLS/SQLite, client process death and native Unix client are real",
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        "-W",
        "error",
        "server/tests/test_dss_fault_reproduction.py",
        "server/tests/test_dss_lifecycle.py",
        "server/tests/test_native_binding_faults.py",
        "server/tests/test_native_spawn.py",
        "server/tests/test_controller_network_recovery.py",
        "server/tests/test_controller_liveness.py",
        "server/tests/test_controller_liveness_tls.py",
        "server/tests/test_native_admission_channel.py",
        "server/tests/test_driver_timing.py",
        "--junitxml=" + str(output / "tests.xml"),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env=dict(os.environ, OPENBEXI_SERVER_EVIDENCE_DIR=str(output)),
            capture_output=True,
            timeout=180,
        )
        (output / "tests.log").write_bytes(result.stdout + result.stderr)
        report["exit_code"] = result.returncode
        suites = ET.parse(output / "tests.xml").getroot()
        report["junit"] = {
            key: sum(int(s.attrib.get(key, 0)) for s in suites.iter("testsuite"))
            for key in ("tests", "failures", "errors", "skipped")
        }
        report["passed"] = result.returncode == 0 and report["junit"] == dict(
            tests=95, failures=0, errors=0, skipped=0
        )
    except subprocess.TimeoutExpired as error:
        (output / "tests.log").write_bytes(
            (error.stdout or b"") + (error.stderr or b"")
        )
        report.update(
            exit_code=124, error="Fault harness exceeded its 180-second suite budget"
        )
    except Exception as error:
        report["error"] = type(error).__name__
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                passed=report["passed"],
                output=str(output),
                junit=report.get("junit"),
                error=report.get("error"),
            )
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
