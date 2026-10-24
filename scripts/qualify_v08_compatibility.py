"""Portable preparation/RPC compatibility subset, not full native v0.8 approval."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

TESTS = [
    "tests/test_legacy_compare_syntax.py",
    "tests/test_command_rpc.py",
    "tests/test_command_catalog_rpc.py",
    "tests/test_command_group_rpc.py",
    "tests/test_telemetry_features_rpc.py",
    "tests/test_limit_features_rpc.py",
    "tests/test_memory_features_rpc.py",
    "tests/test_ranging_complete_rpc.py",
    "tests/test_rng_state_patch.py",
    "tests/test_gcs_display_application.py",
    "tests/test_original_driver.py",
]


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".qualification/v08-compatibility" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema=1,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        scope="legacy syntax preparation and real protobuf/DSS TCP compatibility subset",
        passed=False,
        runtime_enabled=False,
        full_compatibility_qualified=False,
        native_executor_tested=False,
        v08_actual_send_fencing_tested=False,
        python=platform.python_version(),
        git_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        source_sha256={},
        tools={
            name: importlib.metadata.version(name)
            for name in ("pytest", "grpcio", "protobuf")
        },
    )
    inputs = [root / path for path in TESTS]
    for directory in ("src", "driver_plugin/src", "source_port"):
        inputs.extend(sorted((root / directory).rglob("*.py")))
    inputs.extend(
        [
            Path(__file__),
            root / "pyproject.toml",
            root / "driver_plugin/pyproject.toml",
            root / "conformance/limit_features_cases.py",
            root / "docs/reference/SPELL2.6.10-src.zip",
        ]
    )
    inputs.extend(sorted((root / "src/dss/data").glob("*.json")))
    for path in inputs:
        report["source_sha256"][path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    command = [
        sys.executable,
        "-m",
        "pytest",
        *TESTS,
        "-q",
        "-W",
        "error",
        "--tb=short",
        "--junitxml=" + str(output / "tests.xml"),
    ]
    report["command"] = command
    try:
        if sys.version_info[:2] != (3, 13):
            raise RuntimeError("CPython 3.13 required")
        with (output / "tests.log").open("wb") as log:
            run = subprocess.run(
                command,
                cwd=root,
                env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
        report["exit_code"] = run.returncode
        if (output / "tests.xml").exists():
            suites = list(ET.parse(output / "tests.xml").getroot().iter("testsuite"))
            report["junit"] = {
                key: sum(int(s.get(key, 0)) for s in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
        report["passed"] = run.returncode == 0
    except Exception as error:
        report["error"] = str(error)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], junit=report.get("junit"), output=str(output))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
