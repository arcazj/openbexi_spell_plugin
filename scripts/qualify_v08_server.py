"""Preserve services and prelaunch authority checks; no native/deployment qualification."""

import hashlib
import importlib.metadata
import importlib.util
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


def run_check(name, command, root, environment, output, timeout):
    timed_out = False
    try:
        result = subprocess.run(
            command, cwd=root, env=environment, capture_output=True, timeout=timeout
        )
        raw, exit_code = result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        # A timed-out suite is failed evidence. Retain its progress and result
        # instead of losing the report through an unhandled runner exception.
        raw = (error.stdout or b"") + (error.stderr or b"")
        exit_code, timed_out = 124, True
    (output / (name + ".log")).write_bytes(raw)
    return dict(
        name=name,
        command=command,
        exit_code=exit_code,
        timed_out=timed_out,
        timeout_seconds=timeout,
    )


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
        scope="services, prelaunch authority, opt-in retained launch RPC, source preflight and private driver seam with independent DSS process",
        worker_identity_authenticated=True,
        worker_identity_scope="operator-provisioned certificate pins; preflight only",
        kubernetes_worker_identity_tested=False,
        runtime_image_attested=False,
        readonly_mount_attested=False,
        native_pause_tested=False,
        native_pause_barrier_rpc_tested=False,
        driver_effect_seam_tested=False,
        native_context_driver_rpc_tested=False,
        independent_dss_process_tested=False,
        source_inventory_verified=True,
        source_inventory_scope="bounded approved Git objects and worker directory; configured catalog only",
        passed=False,
        runtime_enabled=False,
        native_executor_tested=False,
        python=platform.python_version(),
        openssl=ssl.OPENSSL_VERSION,
        source_sha256={},
        ide_client_inputs={},
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
        + sorted((root / "src/dss").rglob("*.py"))
        + sorted((root / "src/dss/data").glob("*.json"))
        + sorted((root / "driver_plugin/src").rglob("*.py"))
        + [
            root / "server/pyproject.toml",
            root / "server/requirements-test.lock",
            root / "server/README.md",
            root / "server/LICENSE",
            root / "server/MANIFEST.in",
            root / ".github/workflows/v08-server-foundation.yml",
            Path(__file__),
            root / "docs/v0.8/IDE_PAIR.json",
            root / "docs/v0.8/RELEASE_GATES.json",
            root / "scripts/check_v08_release.py",
            root / "host_runtime/python/v08_worker.py",
            root / "host_runtime/python/thread_barrier.py",
            root / "host_runtime/python/child_gate.py",
            root / "host_runtime/python/control_journal.py",
            root / "host_runtime/python/prompt_replies.py",
            root / "host_runtime/build_admission_context.py",
            root / "host_runtime/native_prompt_patch.py",
            root / "host_runtime/native_terminal_patch.py",
            root / "server/tests/native_prompt_harness.cpp",
            root / "server/tests/native_terminal_harness.cpp",
            *sorted((root / "host_runtime/native").glob("*.H")),
            root / "host_runtime/python/children.py",
            root / "host_runtime/python/native.py",
            root / "scripts/qualify_v08_native_launch.py",
            root / "scripts/qualify_v08_native_terminal_build.py",
            root / "scripts/v08_listener_survival.py",
            root / "scripts/v08_native_consumption.py",
        ]
    )
    for path in inputs:
        if "__pycache__" not in path.parts:
            report["source_sha256"][path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    pair = json.loads((root / "docs/v0.8/IDE_PAIR.json").read_text())
    if importlib.metadata.version("openbexi-ide") != pair["ide_version"]:
        raise RuntimeError("Installed IDE version differs from approved pair")
    for relative, expected in pair["ide_source_sha256"].items():
        module = relative.removeprefix("src/").removesuffix(".py").replace("/", ".")
        spec = importlib.util.find_spec(module)
        if spec is None or spec.origin is None:
            raise RuntimeError("Required IDE module is missing")
        actual = hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(
                "Installed IDE source differs from approved pair: " + module
            )
        report["ide_client_inputs"][module] = actual
    report["ide_commit"] = pair["ide_commit"]
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
                "driver_plugin/src/openbexi_spell_dss/fenced_transport.py",
                "driver_plugin/src/openbexi_spell_dss/context_driver.py",
                "driver_plugin/src/openbexi_spell_dss/context_server.py",
                "host_runtime/python/v08_worker.py",
                "host_runtime/python/thread_barrier.py",
                "host_runtime/python/child_gate.py",
                "host_runtime/python/control_journal.py",
                "host_runtime/python/prompt_replies.py",
                "host_runtime/build_admission_context.py",
                "host_runtime/native_prompt_patch.py",
                "host_runtime/native_terminal_patch.py",
                "scripts/qualify_v08_native_launch.py",
                "scripts/qualify_v08_native_terminal_build.py",
                "scripts/v08_listener_survival.py",
                "scripts/v08_native_consumption.py",
                "scripts/check_v08_release.py",
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
                "driver_plugin/src/openbexi_spell_dss/fenced_transport.py",
                "driver_plugin/src/openbexi_spell_dss/context_driver.py",
                "driver_plugin/src/openbexi_spell_dss/context_server.py",
                "host_runtime/python/v08_worker.py",
                "host_runtime/python/thread_barrier.py",
                "host_runtime/python/child_gate.py",
                "host_runtime/python/control_journal.py",
                "host_runtime/python/prompt_replies.py",
                "host_runtime/build_admission_context.py",
                "host_runtime/native_prompt_patch.py",
                "host_runtime/native_terminal_patch.py",
                "scripts/qualify_v08_native_launch.py",
                "scripts/qualify_v08_native_terminal_build.py",
                "scripts/v08_listener_survival.py",
                "scripts/v08_native_consumption.py",
                "scripts/check_v08_release.py",
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
                "-v",
                "-W",
                "error",
                "--tb=short",
                "--durations=15",
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
        check = run_check(
            name,
            command,
            root,
            environment,
            output,
            timeout=300 if name == "tests" else 180,
        )
        report["checks"].append(check)
        if check["exit_code"]:
            break
    report["passed"] = len(report["checks"]) == len(commands) and all(
        c["exit_code"] == 0 for c in report["checks"]
    )
    report["driver_effect_seam_tested"] = report["passed"]
    report["native_context_driver_rpc_tested"] = report["passed"]
    report["native_pause_barrier_rpc_tested"] = report["passed"]
    report["independent_dss_process_tested"] = report["passed"]
    if (output / "tests.xml").exists():
        try:
            suites = list(ET.parse(output / "tests.xml").getroot().iter("testsuite"))
            report["junit"] = {
                key: sum(int(s.get(key, 0)) for s in suites)
                for key in ("tests", "errors", "failures", "skipped")
            }
        except (ET.ParseError, OSError, ValueError):
            report["passed"] = False
            report["junit_error"] = "incomplete_or_invalid_junit"
            for flag in (
                "driver_effect_seam_tested",
                "native_context_driver_rpc_tested",
                "native_pause_barrier_rpc_tested",
                "independent_dss_process_tested",
            ):
                report[flag] = False
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), junit=report.get("junit"))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
