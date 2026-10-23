"""Bounded approved Git inventories and no-symlink worker directory verification.

This reads source objects; it never checks out, imports or executes procedure code.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import time

from .contracts import Fault, canonical, digest, exact, fingerprint, identifier

MAX_FILES, MAX_FILE, MAX_TOTAL = 64, 65536, 1048576


def source_path(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 192
        or len(value.split("/")) > 16
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", p) or p in (".", "..", ".git")
            for p in value.split("/")
        )
    ):
        raise Fault(400, "invalid_source_path")
    return value


def validate_manifest(value):
    exact(value, {"schema", "revision", "entrypoint", "files"})
    if (
        value["schema"] != "openbexi.snapshot/1"
        or not isinstance(value["revision"], str)
        or not re.fullmatch("[0-9a-f]{40}", value["revision"])
    ):
        raise Fault(400, "invalid_source_manifest")
    source_path(value["entrypoint"])
    files = value["files"]
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        raise Fault(400, "source_inventory_limit")
    names, total = [], 0
    for item in files:
        exact(item, {"path", "mode", "bytes", "sha256"})
        names.append(source_path(item["path"]))
        if (
            item["mode"] not in ("100644", "100755")
            or type(item["bytes"]) is not int
            or not 0 <= item["bytes"] <= MAX_FILE
        ):
            raise Fault(400, "invalid_source_manifest")
        fingerprint(item["sha256"])
        total += item["bytes"]
    if names != sorted(set(names)) or value["entrypoint"] not in names or total > MAX_TOTAL:
        raise Fault(400, "invalid_source_manifest")
    # A file may not also be an ancestor directory.
    if any(
        parent in names
        for name in names
        for parent in ["/".join(name.split("/")[:n]) for n in range(1, len(name.split("/")))]
    ):
        raise Fault(400, "invalid_source_manifest")
    return value


def git_manifest(repository, revision, entrypoint):
    source_path(entrypoint)
    if not isinstance(revision, str) or not re.fullmatch("[0-9a-f]{40}", revision):
        raise Fault(400, "invalid_source_revision")
    repository = Path(repository).resolve(strict=True)
    deadline = time.monotonic() + 10
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }

    def git(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Fault(503, "source_inventory_timeout")
        try:
            with subprocess.Popen(
                ["git", "--no-replace-objects", "-C", str(repository), *args],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            ) as process:
                assert process.stdout is not None
                data = b""
                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if (
                            remaining <= 0
                            or not select.select([process.stdout], [], [], remaining)[0]
                        ):
                            raise Fault(503, "source_inventory_timeout")
                        chunk = os.read(
                            process.stdout.fileno(), min(8192, MAX_FILE + 1 - len(data))
                        )
                        if not chunk:
                            break
                        data += chunk
                        if len(data) > MAX_FILE:
                            raise Fault(413, "source_inventory_limit")
                    if process.wait(timeout=max(0.01, deadline - time.monotonic())):
                        raise Fault(503, "source_inventory_unavailable")
                    return data
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Fault(503, "source_inventory_unavailable") from error

    def object_bytes(kind, oid):
        data = git("cat-file", kind, oid)
        actual = hashlib.sha1(
            kind.encode() + b" " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        if actual != oid:
            raise Fault(503, "source_object_hash_mismatch")
        return data

    configuration = git("config", "--null", "--list", "--includes")
    for setting in configuration.split(b"\0"):
        key = setting.split(b"\n", 1)[0].lower()
        if key == b"extensions.partialclone" or (
            key.startswith(b"remote.") and key.endswith(b".promisor")
        ):
            raise Fault(400, "partial_clone_not_supported")
    commit = object_bytes("commit", revision)
    line = commit.split(b"\n", 1)[0]
    if not re.fullmatch(b"tree [0-9a-f]{40}", line):
        raise Fault(400, "invalid_source_commit")
    files: list[dict] = []
    total, nodes = 0, 0

    def walk_tree(oid, prefix):
        nonlocal total, nodes
        nodes += 1
        if nodes > MAX_FILES * 2 or prefix.count("/") > 16:
            raise Fault(413, "source_inventory_limit")
        data = object_bytes("tree", oid)
        offset = 0
        while offset < len(data):
            stop = data.find(b"\0", offset)
            if stop < 0 or stop + 21 > len(data):
                raise Fault(400, "invalid_source_tree")
            try:
                mode, name = data[offset:stop].decode("ascii").split(" ", 1)
                path = source_path(prefix + name)
            except (ValueError, UnicodeError) as error:
                raise Fault(400, "invalid_source_tree") from error
            child_oid = data[stop + 1 : stop + 21].hex()
            offset = stop + 21
            if mode == "40000":
                walk_tree(child_oid, path + "/")
            elif mode in ("100644", "100755"):
                if len(files) >= MAX_FILES:
                    raise Fault(413, "source_inventory_limit")
                blob = object_bytes("blob", child_oid)
                total += len(blob)
                if total > MAX_TOTAL:
                    raise Fault(413, "source_inventory_limit")
                files.append(
                    dict(
                        path=path,
                        mode=mode,
                        bytes=len(blob),
                        sha256=hashlib.sha256(blob).hexdigest(),
                    )
                )
            else:
                raise Fault(400, "unsupported_source_object")

    walk_tree(line[5:].decode(), "")
    return validate_manifest(
        dict(
            schema="openbexi.snapshot/1",
            revision=revision,
            entrypoint=entrypoint,
            files=sorted(files, key=lambda item: item["path"]),
        )
    )


def verify_directory(directory, manifest):
    """Verify all bytes/modes and reject links, special files, omissions and extras.

    Uses open directory descriptors with O_NOFOLLOW. The mount must additionally
    be read-only for native launch; this preflight does not establish mount policy.
    """
    validate_manifest(manifest)
    # Open each root component too: O_NOFOLLOW on only the last name would
    # still follow an ancestor symlink in the configured snapshot path.
    path = Path(directory)
    if not path.is_absolute() or ".." in path.parts:
        raise Fault(400, "unsafe_source_object")
    parts = path.parts[1:]
    if len(parts) > 64:
        raise Fault(400, "unsafe_source_object")
    root = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            os.close(root)
            root = child
    except OSError as error:
        os.close(root)
        raise Fault(400, "unsafe_source_object") from error
    observed: list[dict] = []
    total, nodes = 0, 0
    expected_dirs = {
        "/".join(item["path"].split("/")[:n])
        for item in manifest["files"]
        for n in range(1, len(item["path"].split("/")))
    }

    def walk(fd, prefix):
        nonlocal total, nodes
        names = []
        with os.scandir(fd) as entries:
            for entry in entries:
                nodes += 1
                if nodes > MAX_FILES * 4:
                    raise Fault(400, "source_inventory_limit")
                names.append(entry.name)
        for name in sorted(names):
            relative = source_path(prefix + name)
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                if relative not in expected_dirs:
                    raise Fault(409, "source_inventory_mismatch")
                if len(relative.split("/")) > 16:
                    raise Fault(400, "source_inventory_limit")
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    walk(child, relative + "/")
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if len(observed) >= MAX_FILES or info.st_size > MAX_FILE or info.st_nlink != 1:
                    raise Fault(400, "source_inventory_limit")
                source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    before = os.fstat(source)
                    if (
                        not stat.S_ISREG(before.st_mode)
                        or before.st_size > MAX_FILE
                        or before.st_nlink != 1
                    ):
                        raise Fault(400, "unsafe_source_object")
                    data = b""
                    while len(data) <= MAX_FILE:
                        block = os.read(source, MAX_FILE + 1 - len(data))
                        if not block:
                            break
                        data += block
                    after = os.fstat(source)
                    if (
                        before.st_dev,
                        before.st_ino,
                        before.st_size,
                        before.st_mtime_ns,
                        before.st_ctime_ns,
                    ) != (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ) or len(data) != before.st_size:
                        raise Fault(409, "source_changed_during_verification")
                    total += len(data)
                    if total > MAX_TOTAL:
                        raise Fault(400, "source_inventory_limit")
                    observed.append(
                        dict(
                            path=relative,
                            mode="100755" if before.st_mode & 0o111 else "100644",
                            bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest(),
                        )
                    )
                finally:
                    os.close(source)
            else:
                raise Fault(400, "unsafe_source_object")

    try:
        walk(root, "")
    except OSError as error:
        raise Fault(400, "unsafe_source_object") from error
    finally:
        os.close(root)
    if sorted(observed, key=lambda item: item["path"]) != manifest["files"]:
        raise Fault(409, "source_inventory_mismatch")
    return digest(manifest)


class SnapshotCatalog:
    def __init__(self, config):
        if type(config) is not dict or not 1 <= len(config) <= 10:
            raise ValueError("At most ten approved procedures")
        self.entries: dict = {}
        self.aliases: dict[str, str] = {}
        seen = set()
        for procedure, entry in config.items():
            identifier(procedure)
            exact(
                entry,
                {
                    "repository",
                    "revision",
                    "entrypoint",
                    "runtime_image",
                    "driver_binding",
                    "aliases",
                },
            )
            if not isinstance(entry["runtime_image"], str) or not re.fullmatch(
                "sha256:[0-9a-f]{64}", entry["runtime_image"]
            ):
                raise ValueError("Image must be an approved digest")
            identifier(entry["driver_binding"])
            if type(entry["aliases"]) is not list or len(entry["aliases"]) > 10:
                raise ValueError("Invalid procedure aliases")
            binding = (entry["revision"], entry["entrypoint"])
            if binding in seen:
                raise ValueError("A source entrypoint cannot have two logical identities")
            seen.add(binding)
            manifest = git_manifest(entry["repository"], entry["revision"], entry["entrypoint"])
            self.entries[procedure] = dict(
                manifest=canonical(manifest),
                source_revision=entry["revision"],
                source_sha256=digest(manifest),
                runtime_image=entry["runtime_image"],
                driver_binding=entry["driver_binding"],
            )
            for alias in [procedure, *entry["aliases"]]:
                identifier(alias)
                if alias in self.aliases:
                    raise ValueError("Procedure alias is ambiguous")
                self.aliases[alias] = procedure

    def approve(self, payload):
        canonical_id = self.aliases.get(payload["procedure_id"])
        if canonical_id is None:
            raise Fault(403, "procedure_not_approved")
        expected = self.entries[canonical_id]
        if any(
            payload[key] != expected[key]
            for key in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
        ):
            raise Fault(403, "source_binding_not_approved")
        return {**payload, "procedure_id": canonical_id}

    def metadata(self):
        """No repository path, source bytes or credentials leave the catalog."""
        return {
            "procedures": [
                dict(
                    procedure_id=name,
                    aliases=sorted(
                        alias
                        for alias, canonical_id in self.aliases.items()
                        if canonical_id == name and alias != name
                    ),
                    source_revision=entry["source_revision"],
                    source_sha256=entry["source_sha256"],
                    runtime_image=entry["runtime_image"],
                    driver_binding=entry["driver_binding"],
                    entrypoint=json.loads(entry["manifest"])["entrypoint"],
                )
                for name, entry in sorted(self.entries.items())
            ],
            "runtime_enabled": False,
        }
