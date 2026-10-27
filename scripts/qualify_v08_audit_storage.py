"""Exercise native durable writes on a private, small, real disk filesystem."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filesystem-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.filesystem_dir.resolve(strict=True)
    capacity = os.statvfs(directory)
    if (
        directory.is_symlink()
        or not 4 * 1024**2 <= capacity.f_blocks * capacity.f_frsize <= 64 * 1024**2
    ):
        raise ValueError("A private 4–64 MiB disk filesystem is required")
    if list(directory.iterdir()):
        raise ValueError("Fault filesystem directory must initially be empty")
    output = ROOT / ".qualification/v08-audit-storage" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    report = dict(
        schema="openbexi.native-audit-storage/1",
        passed=False,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        git_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        source_sha256={},
        full_v08_qualified=False,
        buffer_policy="No asynchronous queue; 4096-byte restore buffer",
        mandatory_memory_acceptance_replaced=False,
    )
    inputs = [
        Path(__file__),
        ROOT / "host_runtime/native/audit_file.H",
        ROOT / "server/tests/native_audit_file.cpp",
        ROOT / ".github/workflows/v08-audit-storage.yml",
    ]
    report["source_sha256"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs
    }
    path, reserve = (
        directory / "execution.ASRUN",
        directory / "disposable-fault-reserve.bin",
    )
    try:
        binary = output / "audit"
        built = subprocess.run(
            [
                "c++",
                "-std=c++17",
                "-O1",
                "-g",
                "-pthread",
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer",
                "-no-pie",
                "-I" + str(ROOT / "host_runtime/native"),
                str(ROOT / "server/tests/native_audit_file.cpp"),
                "-o",
                str(binary),
            ],
            capture_output=True,
            timeout=60,
        )
        (output / "build.log").write_bytes(built.stdout + built.stderr)
        if built.returncode:
            raise RuntimeError("Native audit harness did not compile")
        # This file is expendable fault-fixture capacity, never an audit record.
        with reserve.open("wb") as stream:
            for _ in range(256):
                stream.write(bytes(4096))
            stream.flush()
            os.fsync(stream.fileno())
        env = dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1",
        )
        run = subprocess.run(
            [str(binary), "full-disk", str(path)],
            capture_output=True,
            timeout=120,
            env=env,
        )
        (output / "full-disk.log").write_bytes(run.stdout + run.stderr)
        acknowledgements = run.stdout.decode().splitlines()
        if run.returncode != 74 or b"errno=28" not in run.stderr:
            raise RuntimeError(
                "Actual ENOSPC did not produce the explicit audit failure exit"
            )
        if acknowledgements != ["ACK " + str(i) for i in range(len(acknowledgements))]:
            raise RuntimeError("Audit acknowledgements have a gap or reversal")
        acknowledged = len(acknowledgements) * 4096
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for _ in acknowledgements:
                record = stream.read(4096)
                if record != b"x" * 4095 + b"\n":
                    raise RuntimeError(
                        "Acknowledged audit bytes are missing or unordered"
                    )
                digest.update(record)
            tail = stream.read(4097)
        if len(tail) > 4096:
            raise RuntimeError("More than one uncertain record after failure")
        original_size = path.stat().st_size
        # Release only the explicitly expendable capacity. Required records and
        # any uncertain tail remain unchanged, then reopen in a fresh process.
        reserve.unlink()
        restart = subprocess.run(
            [str(binary), "append", str(path)], capture_output=True, timeout=30, env=env
        )
        (output / "restart.log").write_bytes(restart.stdout + restart.stderr)
        complete = not tail or tail.endswith(b"\n")
        if complete:
            if restart.returncode != 0:
                raise RuntimeError("Complete durable audit did not recover")
            with path.open("rb") as stream:
                stream.seek(original_size)
                if stream.read() != b"RESTART\n":
                    raise RuntimeError("Restart append differs")
        elif restart.returncode != 74 or b"stage=incomplete_tail" not in restart.stderr:
            raise RuntimeError("Uncertain tail was not preserved and rejected")
        # Retain the actual bytes even after a failed attempt, before unmount.
        report.update(
            passed=True,
            full_disk_errno=28,
            explicit_failure_exit=74,
            acknowledged_records=len(acknowledgements),
            acknowledged_bytes=acknowledged,
            acknowledged_sha256=digest.hexdigest(),
            uncertain_tail_bytes=len(tail),
            restart_complete=complete,
            required_records_deleted=False,
        )
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if path.exists():
            digest = hashlib.sha256()
            with (
                path.open("rb") as source,
                (output / "execution.ASRUN").open("wb") as saved,
            ):
                for block in iter(lambda: source.read(65536), b""):
                    digest.update(block)
                    saved.write(block)
                saved.flush()
                os.fsync(saved.fileno())
            report["retained_audit_sha256"] = digest.hexdigest()
            report["retained_audit_bytes"] = path.stat().st_size
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), error=report.get("error"))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
