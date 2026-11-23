"""Capture a live Context SQLite audit and restore a verified copy into a new directory."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import time


def database(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Expected a regular Context database")
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def identity(db):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("Context database integrity check failed")
    meta = dict(db.execute("SELECT name,value FROM meta WHERE name IN ('context_id','incarnation')"))
    if set(meta) != {"context_id", "incarnation"} or not all(meta.values()):
        raise ValueError("Missing Context identity")
    audit = hashlib.sha256()
    count, last = 0, 0
    for sequence, event, body in db.execute("SELECT sequence,type,body FROM events ORDER BY sequence"):
        if not isinstance(sequence, int) or sequence <= last:
            raise ValueError("Invalid Context audit sequence")
        audit.update(json.dumps([sequence, event, body], ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        count, last = count + 1, sequence
    return dict(meta, user_version=db.execute("PRAGMA user_version").fetchone()[0],
                audit_events=count, last_sequence=last, audit_sha256=audit.hexdigest())


def checksum(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def sync(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def finish(directory):
    sync(directory)
    sync(directory.parent)


def capture(state, archive, expected):
    source = database(state / "context.sqlite3")
    try:
        archive.mkdir(mode=0o700, exist_ok=False)
        try:
            target = archive / "context.sqlite3"
            destination = sqlite3.connect(target)
            try:
                deadline = time.monotonic() + 60
                def progress(status, remaining, total):
                    if time.monotonic() > deadline:
                        raise TimeoutError("Online checkpoint exceeded 60 seconds")
                source.backup(destination, pages=128, progress=progress, sleep=0.05)
                details = identity(destination)
            finally:
                destination.close()
            if details["context_id"] != expected:
                raise ValueError("Unexpected Context identity")
            target.chmod(0o600)
            sync(target)
            result = dict(format="openbexi.context-checkpoint/1", database_sha256=checksum(target), **details)
            manifest = archive / "manifest.json"
            with manifest.open("x", encoding="utf-8") as file:
                json.dump(result, file, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            finish(archive)
            return dict(result, manifest_sha256=checksum(manifest))
        except BaseException:
            # Only this previously nonexistent, exclusively created directory belongs to this operation.
            shutil.rmtree(archive)
            raise
    finally:
        source.close()


def restore(archive, target, expected, manifest_sha256):
    manifest = archive / "manifest.json"
    original = archive / "context.sqlite3"
    if not stat.S_ISREG(manifest.lstat().st_mode) or not stat.S_ISREG(original.lstat().st_mode):
        raise ValueError("Expected regular checkpoint files")
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError("Checkpoint manifest differs from the capture receipt")
    meta = json.loads(raw)
    if meta.get("format") != "openbexi.context-checkpoint/1" or meta.get("context_id") != expected:
        raise ValueError("Invalid checkpoint format or Context identity")
    if os.path.lexists(target):
        raise FileExistsError("Restore target already exists")
    # The Linux deployment only sees the destination after verification and fsync.
    # RENAME_NOREPLACE also prevents a concurrent restore from replacing an empty directory.
    stage = Path(tempfile.mkdtemp(prefix=".openbexi-restore-", dir=target.parent))
    try:
        path = stage / "context.sqlite3"
        with original.open("rb") as src, path.open("xb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        path.chmod(0o600)
        if checksum(path) != meta["database_sha256"]:
            raise ValueError("Checkpoint database checksum mismatch")
        db = database(path)
        try:
            verified = dict(format=meta["format"], database_sha256=meta["database_sha256"], **identity(db))
        finally:
            db.close()
        if verified != meta:
            raise ValueError("Checkpoint metadata or recorded audit differs")
        sync(path)
        sync(stage)
        library = ctypes.CDLL(None, use_errno=True)
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(stage), -100, os.fsencode(target), 1):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(target))
        sync(target.parent)
        return dict(verified, manifest_sha256=manifest_sha256)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("capture", "restore"):
        part = sub.add_parser(name)
        part.add_argument("--context", required=True)
        part.add_argument("--archive", type=Path, required=True)
        part.add_argument("--state" if name == "capture" else "--target", type=Path, required=True)
        if name == "restore":
            part.add_argument("--manifest-sha256", required=True, help="Trusted digest from the original capture receipt")
    args = parser.parse_args()
    if args.operation == "capture":
        result = capture(args.state, args.archive, args.context)
    else:
        result = restore(args.archive, args.target, args.context, args.manifest_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
