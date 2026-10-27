"""Retained disk ASRUN directories for disposable native qualification workers."""

import hashlib
import json
import os
import re
import stat


def provision(command, output, label):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", label):
        raise ValueError("Invalid native audit storage identity")
    directory = (output / "native-audit" / label).absolute()
    directory.mkdir(mode=0o700, parents=True)
    if directory.is_symlink():
        raise ValueError("Native audit directory is a symlink")
    filesystem = command("stat", "-f", "-c", "%T", directory).strip()
    if filesystem in {"tmpfs", "ramfs"}:
        raise ValueError("Native audit storage must have durable disk backing")
    command("sudo", "-n", "chown", "10003:10003", "--", directory)
    return [
        "--mount",
        f"type=bind,src={directory},dst=/audit",
        "--env",
        "OPENBEXI_V08_AUDIT_ROOT=/audit",
    ]


def expose_after_stop(command, output, report):
    """Never change ownership or inspect records while a worker could write."""
    root = output / "native-audit"
    if not root.exists():
        return
    if report.get("container_cleanup_failed"):
        raise RuntimeError("Native audit storage retained with possibly live writer")
    command("sudo", "-n", "chown", "-hR", f"{os.getuid()}:{os.getgid()}", "--", root)
    records = []
    failures = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise RuntimeError("Unexpected native audit file type")
        digest = hashlib.sha256()
        count = 0
        previous = None
        complete = True
        ordering_valid = True
        oversized = False
        continuation = False
        with path.open("rb") as stream:
            for line in iter(lambda: stream.readline(1024 * 1024 + 1), b""):
                # Hash every byte, including uncertain tails and oversized
                # records. A bad file must not hide other retained generations.
                digest.update(line)
                complete = line.endswith(b"\n")
                if continuation:
                    continuation = not complete
                    continue
                if len(line) > 1024 * 1024:
                    oversized = True
                    continuation = not complete
                    continue
                if not complete:
                    continue
                fields = line.rstrip(b"\n").split(b"\t", 2)
                if (
                    len(fields) != 3
                    or not re.match(rb"^[0-9]{4}[-./][0-9]", fields[0])
                    or not fields[1].isdigit()
                ):
                    continue  # Original procedure headers remain byte-for-byte.
                sequence = int(fields[1])
                if previous is not None and sequence not in {previous, previous + 1}:
                    ordering_valid = False
                previous = sequence
                count += 1
        file_failures = []
        if not complete:
            file_failures.append("incomplete_tail")
        if not ordering_valid:
            file_failures.append("sequence_gap_or_reversal")
        if oversized:
            file_failures.append("record_exceeds_verifier_bound")
        failures.extend(file_failures)
        records.append(
            dict(
                path=path.relative_to(output).as_posix(),
                bytes=info.st_size,
                sha256=digest.hexdigest(),
                records=count,
                last_sequence=previous,
                complete_lines=complete,
                ordering_valid=ordering_valid,
                validation_failures=file_failures,
            )
        )
    if report.get("passed") and not any(r["records"] for r in records):
        failures.append("required_records_missing")
    result = dict(
        schema="openbexi.native-audit-files/1",
        files=records,
        total_bytes=sum(r["bytes"] for r in records),
        buffer_policy="Synchronous native writes; no asynchronous queue",
        required_records_deleted=False,
        full_v08_qualified=False,
        validation_passed=not failures,
        validation_failures=sorted(set(failures)),
    )
    (output / "native-audit-files.json").write_text(json.dumps(result, indent=2) + "\n")
    report["native_audit_storage"] = result
    if failures:
        raise RuntimeError("Native audit validation failed; all raw files retained")
