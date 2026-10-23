"""Preserve services and prelaunch authority checks; no native/deployment qualification."""

import hashlib
import json
import os
from pathlib import Path
import platform
import ssl
import subprocess
import sys
import uuid
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    suffix = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    output = root / ".qualification" / "v08-server" / ("run-" + suffix)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema=1,
        scope="internal Listener/Context services and durable prelaunch authority only",
        worker_identity_authenticated=False,
        native_pause_tested=False,
        source_inventory_verified=False,
        passed=False,
        runtime_enabled=False,
        native_executor_tested=False,
        python=platform.python_version(),
        openssl=ssl.OPENSSL_VERSION,
        source_sha256={},
        checks=[],
    )
    report["git_head"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    report["working_tree_dirty"] = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True
        ).strip()
    )
    inputs = (
        sorted((root / "server/src").rglob("*.py"))
        + sorted((root / "server/tests").rglob("*.py"))
        + [
            root / "server/pyproject.toml",
            root / "server/requirements-test.lock",
            root / "server/README.md",
            root / "server/LICENSE",
            root / "server/MANIFEST.in",
            root / ".github/workflows/v08-server-foundation.yml",
            Path(__file__),
        ]
    )
    for path in inputs:
        if "__pycache__" not in path.parts:
            report["source_sha256"][path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    if sys.version_info[:2] != (3, 13):
        report["error"] = "CPython 3.13 required"
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(passed=False, output=str(output), error=report["error"])))
        return 1
    commands = [
        (
            "lint",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "server",
                str(Path(__file__).relative_to(root)),
            ],
        ),
        (
            "format",
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "server",
                str(Path(__file__).relative_to(root)),
            ],
        ),
        (
            "types",
            [
                sys.executable,
                "-m",
                "mypy",
                "--config-file",
                "server/pyproject.toml",
                "server/src",
            ],
        ),
        (
            "tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "server/tests",
                "-q",
                "-W",
                "error",
                "--tb=short",
                "--junitxml=" + str(output / "tests.xml"),
            ],
        ),
    ]
    environment = dict(
        os.environ,
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OPENBEXI_SERVER_EVIDENCE_DIR=str(output),
    )
    for name, command in commands:
        result = subprocess.run(
            command, cwd=root, env=environment, capture_output=True, timeout=180
        )
        (output / (name + ".log")).write_bytes(result.stdout + result.stderr)
        report["checks"].append(
            dict(name=name, command=command, exit_code=result.returncode)
        )
        if result.returncode:
            break
    report["passed"] = len(report["checks"]) == len(commands) and all(
        c["exit_code"] == 0 for c in report["checks"]
    )
    if (output / "tests.xml").exists():
        suites = list(ET.parse(output / "tests.xml").getroot().iter("testsuite"))
        report["junit"] = {
            key: sum(int(s.get(key, 0)) for s in suites)
            for key in ("tests", "errors", "failures", "skipped")
        }
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), junit=report.get("junit"))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
