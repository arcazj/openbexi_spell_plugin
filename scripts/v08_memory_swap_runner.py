"""Prepare only unused scratch swap on disposable GitHub-hosted Linux runners.

The default remains refusal. An explicit opt-in may temporarily disable one
allowlisted, unused, root-owned regular swap file, never remove its backing.
Every hosted preparation attempt emits a receipt, including early refusals.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FILES = frozenset(("/mnt/swapfile", "/swapfile", "/swap.img"))
GIB = 1024**3


def parse_swaps(text):
    lines = text.splitlines()
    if not lines or lines[0].split() != [
        "Filename",
        "Type",
        "Size",
        "Used",
        "Priority",
    ]:
        raise ValueError("invalid_swap_inventory")
    entries = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 5 or "\\" in fields[0]:
            raise ValueError("ambiguous_swap_inventory")
        path, kind, size, used, priority = fields
        size, used, priority = int(size), int(used), int(priority)
        if size <= 0 or not 0 <= used <= size or not -32768 <= priority <= 32767:
            raise ValueError("invalid_swap_counters")
        entries.append(
            dict(path=path, kind=kind, size_kib=size, used_kib=used, priority=priority)
        )
    if len({entry["path"] for entry in entries}) != len(entries):
        raise ValueError("duplicate_swap_inventory")
    return entries


class SwapHost:
    def snapshot(self):
        return parse_swaps(Path("/proc/swaps").read_text())

    def identity(self, entry):
        path = Path(entry["path"])
        if str(path) not in ALLOWED_FILES or path.resolve(strict=True) != path:
            raise ValueError("runner_swap_file_not_allowlisted")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            raise ValueError("runner_swap_file_identity_untrusted")
        if info.st_mode & 0o022:
            raise ValueError("runner_swap_file_is_writable_by_others")
        return [
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_uid,
            stat.S_IMODE(info.st_mode),
        ]

    def validate(self, entry):
        if entry["kind"] != "file" or entry["used_kib"] != 0:
            raise ValueError("runner_swap_is_not_an_unused_file")
        if entry["size_kib"] * 1024 > 8 * GIB or entry["priority"] < -2:
            raise ValueError("runner_swap_capacity_or_priority_unsupported")
        available = re.search(
            r"^MemAvailable:\s+([0-9]+) kB$", Path("/proc/meminfo").read_text(), re.M
        )
        if not available or int(available[1]) * 1024 < 4 * GIB:
            raise ValueError("insufficient_ram_for_runner_swap_isolation")
        identity = self.identity(entry)
        if identity[2] < entry["size_kib"] * 1024 or identity[2] > 8 * GIB:
            raise ValueError("runner_swap_backing_size_differs")
        return identity

    def disable(self, entry):
        subprocess.run(
            ["sudo", "-n", "swapoff", "--", entry["path"]], check=True, timeout=120
        )

    def restore(self, entry):
        args = ["sudo", "-n", "swapon"]
        if entry["priority"] >= 0:
            args += ["--priority", str(entry["priority"])]
        subprocess.run(args + ["--", entry["path"]], check=True, timeout=120)

    def run(self, command):
        # The original encrypted-swap helper remains non-root and refuses ANY
        # active host swap. Its cleanup must finish before restoration below.
        child = subprocess.Popen(
            ["bash", str(ROOT / "scripts/v08_memory_swap_device.sh"), *command],
            start_new_session=True,
        )
        try:
            return child.wait(timeout=2400)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            for sig, timeout in (
                (signal.SIGINT, 60),
                (signal.SIGTERM, 15),
                (signal.SIGKILL, 10),
            ):
                if child.poll() is not None:
                    break
                try:
                    os.killpg(child.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    continue
            raise


def prepare_and_run(host, output, command, *, isolate_unused=False):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="openbexi.native-memory-swap-setup/1",
        diagnostic_only=True,
        full_v08_qualified=False,
        eligible_for_publication=False,
        publication_performed=False,
        passed=False,
        isolate_unused_runner_swap=isolate_unused,
        comparison_command_started=False,
        existing_backing_removed=False,
        persistent_config_changed=False,
        started_at=datetime.now(timezone.utc).isoformat(),
        failures=[],
    )
    previous = None
    identity = None
    disable_attempted = False
    exit_code = 2
    try:
        before = host.snapshot()
        report["host_swap_before"] = before
        if before:
            if not isolate_unused:
                raise ValueError("existing_host_swap_requires_explicit_isolation")
            if len(before) != 1:
                raise ValueError("multiple_existing_swap_devices_refused")
            previous = before[0]
            identity = host.validate(previous)
            report["previous_backing_identity"] = identity
            # Recheck immediately before changing this one named resource.
            if host.snapshot() != before or host.identity(previous) != identity:
                raise ValueError("runner_swap_changed_before_isolation")
            disable_attempted = True
            host.disable(previous)
            report["unused_runner_swap_disabled"] = True
        if host.snapshot():
            raise ValueError("runner_swap_isolation_unproven")
        report["runner_prepared"] = True
        report["comparison_command_started"] = True
        exit_code = host.run(command)
        report["comparison_command_exit_code"] = exit_code
        if exit_code:
            report["failures"].append("comparison_command_failed")
    except KeyboardInterrupt:
        exit_code = 130
        report["failures"].append("comparison_interrupted")
    except Exception as error:
        # Do not retain arbitrary subprocess arguments or environment secrets.
        label = str(error) if isinstance(error, ValueError) else type(error).__name__
        report["failures"].append(
            label if label.isidentifier() else type(error).__name__
        )
    finally:
        try:
            active = host.snapshot()
            if disable_attempted:
                if host.identity(previous) != identity:
                    raise ValueError("runner_swap_backing_changed_before_restore")
                if active and not (
                    len(active) == 1
                    and all(
                        active[0][k] == previous[k]
                        for k in ("path", "kind", "size_kib", "priority")
                    )
                ):
                    raise ValueError("experiment_swap_cleanup_unproven")
                if not active:
                    host.restore(previous)
                restored = host.snapshot()
                if len(restored) != 1 or any(
                    restored[0][k] != previous[k]
                    for k in ("path", "kind", "size_kib", "priority")
                ):
                    raise ValueError("runner_swap_restoration_unproven")
                report["previous_swap_restored"] = True
            elif report["comparison_command_started"] and active:
                raise ValueError("experiment_swap_cleanup_unproven")
            report["host_swap_after"] = host.snapshot()
        except Exception as error:
            label = (
                str(error) if isinstance(error, ValueError) else type(error).__name__
            )
            report["failures"].append(
                label if label.isidentifier() else type(error).__name__
            )
            report["cleanup_unproven"] = True
        report["source_sha256"] = {
            "scripts/" + name: hashlib.sha256(
                (ROOT / "scripts" / name).read_bytes()
            ).hexdigest()
            for name in (
                "v08_memory_swap_ci.sh",
                "v08_memory_swap_runner.py",
                "v08_memory_swap_device.sh",
            )
        }
        report["passed"] = exit_code == 0 and not report["failures"]
        (output / "swap-setup.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"passed": report["passed"], "output": str(output), "setup_only": True}
        )
    )
    return 0 if report["passed"] else (exit_code if exit_code else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolate-unused-runner-swap", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("RUNNER_OS") == "Linux"
        and re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ID", ""))
        and re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ATTEMPT", ""))
        and args.command
        and os.getuid() != 0
    ):
        print(
            "Refusing swap setup outside an ordinary GitHub-hosted Linux runner account",
            file=sys.stderr,
        )
        return 2
    output = (
        ROOT / ".qualification/v08-memory-comparison" / ("run-swap-" + uuid.uuid4().hex)
    )

    def terminate(_signum, _frame):
        raise KeyboardInterrupt()

    old = signal.signal(signal.SIGTERM, terminate)
    try:
        return prepare_and_run(
            SwapHost(),
            output,
            args.command,
            isolate_unused=args.isolate_unused_runner_swap,
        )
    finally:
        signal.signal(signal.SIGTERM, old)


if __name__ == "__main__":
    raise SystemExit(main())
