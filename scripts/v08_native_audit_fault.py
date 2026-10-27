"""Independent host fault injection on a private disk; no worker gains mount authority."""

from contextlib import closing
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import select
import sqlite3
import stat
import sys
import time

MIB = 1024**2


def independent_control(temporary):
    # Earlier owner-resume qualification intentionally leaves its opened marker
    # as evidence. A fresh execution must never inherit that fixture state.
    control = temporary / "audit-full-control"
    control.mkdir(mode=0o755)
    (control / "start").write_text("Start this separately admitted fixture once\n")
    return control


def provision(command, output, name, report):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name):
        raise ValueError("Invalid fault volume identity")
    root = (output / "native-audit-fault" / name).absolute()
    root.mkdir(parents=True)
    mount = root / "mount"
    mount.mkdir()
    volume = dict(root=str(root), mount=str(mount), worker=name, mounted=False)
    report.setdefault("native_audit_fault_volumes", []).append(volume)
    command("truncate", "-s", "8M", root / "disk.img")
    command("mkfs.ext4", "-q", "-F", "-m", "0", root / "disk.img")
    command(
        "sudo",
        "-n",
        "mount",
        "-o",
        "loop,nosuid,nodev,noexec",
        root / "disk.img",
        mount,
    )
    volume["mounted"] = True
    command("sudo", "-n", "mkdir", "-m", "700", mount / "audit")
    command("sudo", "-n", "chown", "10003:10003", mount / "audit")
    return [
        "--mount",
        f"type=bind,src={mount / 'audit'},dst=/audit",
        "--env",
        "OPENBEXI_V08_AUDIT_ROOT=/audit",
    ], volume


def snapshot_records(source, destination, uid, gid):
    """Copy flat regular records through no-follow descriptors, with bounded I/O."""
    destination.mkdir(mode=0o700)
    os.chown(destination, uid, gid)
    records = []
    directory = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        entries = sorted(os.listdir(directory))
        if len(entries) > 64:
            raise RuntimeError("Fault audit inventory exceeds bound")
        total = 0
        for name in entries:
            if not re.fullmatch(r"[A-Za-z0-9_.#-]{1,255}", name):
                raise RuntimeError("Unexpected audit filename")
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                before = os.fstat(fd)
                total += before.st_size
                if not stat.S_ISREG(before.st_mode) or total > 16 * MIB:
                    raise RuntimeError("Fault audit file policy differs")
                target = os.open(
                    destination / name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                digest = hashlib.sha256()
                copied = 0
                last = b""
                try:
                    while copied < before.st_size:
                        data = os.read(fd, min(4096, before.st_size - copied))
                        if not data:
                            raise RuntimeError("Fault audit changed during copy")
                        digest.update(data)
                        last = data[-1:]
                        copied += len(data)
                        view = memoryview(data)
                        while view:
                            written = os.write(target, view)
                            if written <= 0:
                                raise RuntimeError("Fault audit evidence write failed")
                            view = view[written:]
                    os.fsync(target)
                    os.fchown(target, uid, gid)
                finally:
                    os.close(target)
                after = os.fstat(fd)
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                ):
                    raise RuntimeError("Fault audit changed during copy")
                records.append(
                    dict(
                        name=name,
                        bytes=copied,
                        sha256=digest.hexdigest(),
                        complete_tail=not copied or last == b"\n",
                    )
                )
            finally:
                os.close(fd)
        destfd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(destfd)
        finally:
            os.close(destfd)
    finally:
        os.close(directory)
    return records


def privileged(command, action, *arguments):
    return json.loads(
        command(
            "sudo",
            "-n",
            sys.executable,
            "-I",
            Path(__file__).resolve(),
            action,
            *arguments,
        )
    )


def fill_disk(path):
    capacity = os.statvfs(path.parent)
    if not 4 * MIB <= capacity.f_blocks * capacity.f_frsize <= 16 * MIB:
        raise RuntimeError("Fault requires its own small disk filesystem")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    written = 0
    try:
        try:
            for _ in range(8192):
                written += os.write(fd, bytes(4096))
            raise RuntimeError("Fault filesystem did not reach ENOSPC")
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise
        try:
            os.fsync(fd)
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise
    finally:
        os.close(fd)
    return dict(
        errno=errno.ENOSPC, disposable_bytes=written, audit_records_deleted=False
    )


def qualify(
    *,
    volume,
    command,
    execution,
    connection,
    controller,
    control,
    state,
    name,
    worker_image,
    await_event,
    host_processes,
    events,
    report,
):
    await_event([name], "native-owner-resume-ready", seconds=45)
    original = host_processes(name)
    executor = next(p["host_pid"] for p in original if "Executor" in p["executable"])
    descriptor = os.pidfd_open(executor)
    try:
        proof = dict(
            execution_id=execution["id"],
            connection_id=connection,
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
            target_admission_id=None,
        )
        witness = [
            r
            for r in controller("execution.list", {})["executions"]
            if r["id"] != execution["id"]
        ]
        commands = []
        for native, event in (
            ("CMD_RUN", "native-owner-run-started"),
            ("CMD_PAUSE", "native-owner-paused"),
        ):
            commands.append(
                controller("execution.command", dict(proof, command=native))[
                    "command_id"
                ]
            )
            await_event([name], event, seconds=20)
        root = Path(volume["root"])
        prefix = privileged(
            command,
            "snapshot",
            Path(volume["mount"]) / "audit",
            root / "prefix",
            os.getuid(),
            os.getgid(),
        )
        if not prefix or not all(
            row["bytes"] and row["complete_tail"] for row in prefix
        ):
            raise RuntimeError("Native acknowledged audit prefix is incomplete")
        volume["acknowledged_prefix"] = prefix
        volume["fault"] = privileged(
            command, "fill", Path(volume["mount"]) / "disposable-fault-reserve.bin"
        )
        (control / "owner-resume").write_text(
            "Open fixture barrier; await original fresh RUN\n"
        )
        time.sleep(5)  # Preserve the existing independent pause observation.
        commands.append(
            controller("execution.command", dict(proof, command="CMD_RUN"))[
                "command_id"
            ]
        )
        if len(set(commands)) != 3:
            raise RuntimeError("Fault probe reused an owner command")
        if command("docker", "wait", name, timeout=90) != "1":
            raise RuntimeError("Native full-disk worker did not fail explicitly")
        info = json.loads(command("docker", "inspect", name))[0]
        if (
            info["State"]["Running"]
            or info["State"]["OOMKilled"]
            or info["Image"] != worker_image
        ):
            raise RuntimeError("Native disk failure identity or process exit differs")
        if not select.select([descriptor], [], [], 0)[0]:
            raise RuntimeError("Original native Executor did not exit")
        records = events(name)
        failures = [r for r in records if r["event"] == "native-worker-failed"]
        audit_errors = [
            match.group(1)
            for row in failures
            for cause in row.get("causes", [])
            if (
                match := re.search(
                    r"stage=(write|record_sync) errno=28", cause.get("message", "")
                )
            )
        ]
        if (
            any(
                r["event"] in {"native-finished", "native-owner-resume-finished"}
                for r in records
            )
            or not audit_errors
        ):
            raise RuntimeError(
                "Real native ENOSPC lacks explicit audit failure evidence"
            )
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            if (
                db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 2
                or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
                or db.execute(
                    "SELECT owner,epoch FROM executions WHERE id=?", (execution["id"],)
                ).fetchone()
                != ("alice", execution["epoch"])
            ):
                raise RuntimeError("Audit failure released a hold or changed authority")
        if witness != [
            r
            for r in controller("execution.list", {})["executions"]
            if r["id"] != execution["id"]
        ]:
            raise RuntimeError("Audit failure changed an unrelated reserved witness")
        report["native_audit_full_disk"] = dict(
            passed=False,
            write_failure_observed=True,
            actual_native_executor=True,
            original_executor_exited=True,
            explicit_native_audit_errno=28,
            observed_native_failure_stages=sorted(set(audit_errors)),
            worker_exit_code=1,
            false_completion=False,
            holds_retained=2,
            spent_workers=1,
            original_owner_epoch_retained=True,
            full_v08_qualified=False,
        )
    finally:
        os.close(descriptor)


def finalize(command, output, report):
    if report.get("container_cleanup_failed"):
        raise RuntimeError("Fault filesystem retained with possibly live writer")
    for volume in report.get("native_audit_fault_volumes", []):
        if not volume["mounted"]:
            continue
        root = Path(volume["root"])
        final = privileged(
            command,
            "snapshot",
            Path(volume["mount"]) / "audit",
            root / "final",
            os.getuid(),
            os.getgid(),
        )
        for record in volume.get("acknowledged_prefix", []):
            old, new = root / "prefix" / record["name"], root / "final" / record["name"]
            with old.open("rb") as before, new.open("rb") as after:
                while data := before.read(4096):
                    if after.read(len(data)) != data:
                        raise RuntimeError(
                            "Acknowledged native audit prefix changed after ENOSPC"
                        )
        volume["retained_records"] = final
        volume["acknowledged_prefix_preserved"] = bool(
            volume.get("acknowledged_prefix")
        )
        command("sudo", "-n", "umount", volume["mount"])
        volume["mounted"] = False
        # The whole image is retained, including the disposable filler and every
        # required record. No audit record is deleted to make this probe pass.
        volume["image_retained"] = str((root / "disk.img").relative_to(output))
        if volume["acknowledged_prefix_preserved"] and report.get(
            "native_audit_full_disk", {}
        ).get("write_failure_observed"):
            report["native_audit_full_disk"]["passed"] = True
            report["native_audit_full_disk"]["audit_retention_verified"] = True


if __name__ == "__main__":
    if sys.argv[1] == "fill" and len(sys.argv) == 3:
        result = fill_disk(Path(sys.argv[2]))
    elif sys.argv[1] == "snapshot" and len(sys.argv) == 6:
        result = snapshot_records(
            Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        )
    else:
        raise SystemExit("Unsupported host fault operation")
    print(json.dumps(result))
