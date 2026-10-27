"""Run source-bound ASan/no-swap, optimized/no-swap or ASan/swap experiments.

Normal native qualification and every release-gate file remain untouched.
The only patched sources are in a disposable detached Git worktree.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from v08_memory_experiment import PROFILES, prepare_overlay, validate_profile

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def verify_swap_host(proc=Path("/proc"), sysfs=Path("/sys")):
    """Require the dedicated encrypted CI device; never configure a user's host."""
    name = os.environ.get("OPENBEXI_MEMORY_SWAP_NAME", "")
    if not re.fullmatch(r"openbexi-v08-[0-9]+-[0-9]+", name):
        raise ValueError("missing_dedicated_swap_identity")
    lines = (proc / "swaps").read_text().splitlines()
    if len(lines) != 2:
        raise ValueError("swap_host_must_have_one_dedicated_encrypted_device")
    device, kind, size, used, priority = lines[1].split()
    resolved = Path(device).resolve(strict=True)
    if not re.fullmatch(r"dm-[0-9]+", resolved.name):
        raise ValueError("swap_is_not_a_device_mapper_device")
    dm = sysfs / "class/block" / resolved.name / "dm"
    if (dm / "name").read_text().strip() != name:
        raise ValueError("swap_device_identity_differs")
    if not (dm / "uuid").read_text().startswith("CRYPT-PLAIN-"):
        raise ValueError("swap_encryption_unproven")
    if kind != "partition" or not 2 * 1024**3 - 4096 <= int(size) * 1024 <= 2 * 1024**3:
        raise ValueError("swap_capacity_differs")
    return {
        "encrypted": True,
        "type": "ephemeral-dm-crypt",
        "capacity_bytes": int(size) * 1024,
        "used_bytes_at_start": int(used) * 1024,
        "priority": int(priority),
        "persistent_config_changed": False,
    }


def run_child(command, cwd, log, timeout):
    """Give the existing harness a chance to execute its own failure cleanup."""
    child = subprocess.Popen(
        command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    try:
        return child.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(child.pid, signal.SIGINT)
        try:
            child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--scenario", choices=("handoff", "ide"), required=True)
    parser.add_argument("--soak-seconds", type=int, default=300)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate exact overlay without claiming runtime execution",
    )
    args = parser.parse_args(argv)
    validate_profile(args.profile, args.soak_seconds)
    output = ROOT / ".qualification/v08-memory-comparison" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    report = {
        "schema": "openbexi.native-memory-comparison/1",
        "profile": args.profile,
        "scenario": args.scenario,
        "soak_seconds": args.soak_seconds,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "executed": False,
        "diagnostic_only": True,
        "full_v08_qualified": False,
        "eligible_for_publication": False,
        "publication_performed": False,
        "failures": [],
        "source_sha": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
    }
    workspace = None
    retain = False
    start = time.monotonic()
    try:
        if git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("comparison_requires_clean_tracked_sources")
        if not args.prepare_only:
            if os.getuid() == 0 or not shutil.which("docker"):
                raise ValueError("requires_non_root_docker_host")
            if args.profile == "asan-swap":
                report["swap_host"] = verify_swap_host()
        workspace = Path(tempfile.mkdtemp(prefix="spell-memory-comparison-"))
        git(
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(workspace),
            report["source_sha"],
        )
        overlay = prepare_overlay(workspace, args.profile, args.soak_seconds)
        (output / "overlay.json").write_text(json.dumps(overlay, indent=2) + "\n")
        (output / "overlay.patch").write_text(
            git("diff", "--no-ext-diff", cwd=workspace) + "\n"
        )
        report["overlay_sha256"] = hashlib.sha256(
            (output / "overlay.patch").read_bytes()
        ).hexdigest()
        report["prepared"] = True
        if not args.prepare_only:
            with (output / "execution.log").open("w") as stream:
                report["executed"] = True
                report["exit_code"] = run_child(
                    [
                        sys.executable,
                        str(workspace / "scripts/qualify_v08_native_launch.py"),
                        "--native-" + args.scenario,
                    ],
                    workspace,
                    stream,
                    1500 + args.soak_seconds,
                )
            paths = list((workspace / ".qualification/v08-native-launch").glob("run-*"))
            if len(paths) != 1:
                raise ValueError("missing_or_ambiguous_native_evidence")
            # Copy failure evidence before evaluating any result.
            shutil.copytree(paths[0], output / "evidence")
            native = json.loads((paths[0] / "result.json").read_text())
            retain = bool(native.get("container_cleanup_failed"))
            report["native_passed"] = native.get("passed") is True
            report["native_error"] = native.get("error")
            report["candidate_worker_image"] = native.get("candidate_worker_image")
            report["native_build"] = native.get("native_context_build", {})
            report["paired_ide"] = json.loads(
                (workspace / "docs/v0.8/IDE_PAIR.json").read_text()
            )
            for relative, expected in native.get("source_sha256", {}).items():
                path = (workspace / relative).resolve()
                if (
                    not path.is_relative_to(workspace)
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    raise ValueError("executed_source_inventory_mismatch")
            if (
                not native.get("source_sha256")
                or native.get("git_head") != report["source_sha"]
            ):
                raise ValueError("executed_source_identity_missing")
            resource_path = paths[0] / "native-resource-acceptance.json"
            if resource_path.is_file():
                resources = json.loads(resource_path.read_text())
                report["resources"] = resources
                if (
                    resources.get("schema")
                    != "openbexi.native-memory-comparison-resources/1"
                    or resources.get("profile") != args.profile
                ):
                    raise ValueError("comparison_receipt_identity_differs")
            else:
                raise ValueError("memory_comparison_incomplete")
            if (
                not native.get("memory_comparison_only")
                or native.get("full_v08_qualified") is not False
            ):
                raise ValueError("comparison_mislabelled_as_release_evidence")
            if (
                args.profile == "optimized-noswap"
                and report["native_build"].get("native_build_profile") != "optimized"
            ):
                raise ValueError("optimized_build_identity_unproven")
            if (
                args.profile == "asan-o2-noswap"
                and report["native_build"].get("native_build_profile") != "asan-o2"
            ):
                raise ValueError("controlled_sanitizer_build_identity_unproven")
            report["passed"] = (
                report["exit_code"] == 0
                and report["native_passed"]
                and resources.get("passed") is True
                and not retain
            )
    except (Exception, KeyboardInterrupt) as error:
        report["failures"].append(type(error).__name__ + ": " + str(error))
        # A timeout or interrupted harness might still own mounted files.
        if isinstance(error, (subprocess.TimeoutExpired, KeyboardInterrupt)):
            retain = True
        if workspace:
            evidence = workspace / ".qualification/v08-native-launch"
            if evidence.exists() and not (output / "evidence").exists():
                shutil.copytree(evidence, output / "incomplete-evidence")
    finally:
        if workspace is not None:
            if retain:
                report["workspace_retained"] = str(workspace)
                report["cleanup_unproven"] = True
                report["passed"] = False
            else:
                try:
                    git("worktree", "remove", "--force", str(workspace))
                except subprocess.CalledProcessError:
                    report["workspace_cleanup_failed"] = True
                    report["passed"] = False
        report["elapsed_seconds"] = time.monotonic() - start
        report["evidence_sha256"] = {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*"))
            if p.is_file()
        }
        (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "prepared": report.get("prepared", False),
                "executed": report["executed"],
                "output": str(output),
            }
        )
    )
    return (
        0
        if report["passed"]
        or (args.prepare_only and report.get("prepared") and not report["failures"])
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
