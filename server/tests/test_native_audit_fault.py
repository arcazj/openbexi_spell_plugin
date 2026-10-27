"""Actual descriptor copies and failure retention; full native disk fault is hosted."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "audit_fault", ROOT / "scripts/v08_native_audit_fault.py"
)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def test_fault_continuation_crosses_existing_audit_block_without_changing_original():
    original = "FIRST = 1\nSECOND = 2\n"
    text = candidate.continuation_fixture(original)
    assert text.startswith(original) and original == "FIRST = 1\nSECOND = 2\n"
    code = compile(text, "audit-full-fixture.py", "exec")
    lines = []

    def observe(frame, event, arg):
        if event == "line" and frame.f_code is code:
            lines.append(frame.f_lineno)
        return observe

    prior = sys.gettrace()
    try:
        sys.settrace(observe)
        namespace = {}
        exec(code, namespace)
    finally:
        sys.settrace(prior)
    assert namespace["AUDIT_PROBE_STEP"] == 1023 and len(lines) >= 2048


def test_captured_ext4_metadata_overhead_does_not_change_physical_image_bound(
    tmp_path, monkeypatch
):
    mount = tmp_path / "mount"
    mount.mkdir()
    image = tmp_path / "disk.img"
    with image.open("wb") as stream:
        stream.truncate(8 * candidate.MIB)
    original_stat = Path.stat

    def mounted(path, *, follow_symlinks=True):
        info = original_stat(path, follow_symlinks=follow_symlinks)
        return SimpleNamespace(st_dev=info.st_dev + 1) if path == mount else info

    monkeypatch.setattr(Path, "stat", mounted)
    monkeypatch.setattr(
        candidate.os, "statvfs", lambda path: SimpleNamespace(f_blocks=892, f_frsize=4096)
    )
    assert candidate.fault_capacity(mount / "filler") == {
        "backing_image_bytes": 8 * candidate.MIB,
        "filesystem_usable_bytes": 892 * 4096,
    }
    with image.open("wb") as stream:
        stream.truncate(16 * candidate.MIB)
    with pytest.raises(RuntimeError, match="8 MiB mounted disk image"):
        candidate.fault_capacity(mount / "filler")


def test_fault_fill_refuses_unmounted_host_directory_before_creating_filler(tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    with (tmp_path / "disk.img").open("wb") as stream:
        stream.truncate(8 * candidate.MIB)
    with pytest.raises(RuntimeError, match="mounted disk image"):
        candidate.fill_disk(mount / "filler")
    assert not list(mount.iterdir())


def test_privileged_operation_failure_cannot_be_accepted_as_fault_injection():
    with pytest.raises(RuntimeError, match="fill failed .*errno=28"):
        candidate.privileged(
            lambda *args: json.dumps({"passed": False, "error_type": "OSError", "errno": 28}),
            "fill",
            "unused",
        )


def test_actual_helper_cli_preserves_records_and_reports_safe_failure(tmp_path):
    source = tmp_path / "audit"
    source.mkdir()
    (source / "execution.ASRUN").write_bytes(b"ACK\n")
    command = [sys.executable, "-I", str(ROOT / "scripts/v08_native_audit_fault.py")]
    value = json.loads(
        subprocess.check_output(
            [
                *command,
                "snapshot",
                str(source),
                str(tmp_path / "saved"),
                str(os.getuid()),
                str(os.getgid()),
            ]
        )
    )
    assert value["passed"] is True and value["value"][0]["bytes"] == 4
    assert (tmp_path / "saved/execution.ASRUN").read_bytes() == b"ACK\n"
    failure = json.loads(
        subprocess.check_output([*command, "fill", str(tmp_path / "unknown/filler")])
    )
    assert failure == {"passed": False, "error_type": "FileNotFoundError", "errno": 2}


def test_prior_resume_marker_cannot_advance_fresh_native_fault_fixture(tmp_path):
    old = tmp_path / "ordinary-control"
    old.mkdir()
    (old / "owner-resume").write_bytes(b"already opened by prior qualification\n")
    fresh = candidate.independent_control(tmp_path)
    program = (
        "import pathlib,sys\n"
        "control=pathlib.Path(sys.argv[1])\n"
        "print('FINISHED' if (control/'owner-resume').exists() else 'HELD',flush=True)\n"
    )
    assert subprocess.check_output([sys.executable, "-I", "-c", program, str(old)]) == b"FINISHED\n"
    assert subprocess.check_output([sys.executable, "-I", "-c", program, str(fresh)]) == b"HELD\n"
    assert (fresh / "start").is_file()
    (fresh / "owner-resume").write_bytes(b"this fixture's fresh release\n")
    assert (
        subprocess.check_output([sys.executable, "-I", "-c", program, str(fresh)]) == b"FINISHED\n"
    )
    assert (old / "owner-resume").read_bytes() == b"already opened by prior qualification\n"


def test_snapshot_retains_exact_regular_bytes_and_uncertain_tail(tmp_path):
    source, destination = tmp_path / "audit", tmp_path / "saved"
    source.mkdir()
    original = b"ACKNOWLEDGED\n" * 5000 + b"UNCERTAIN"
    (source / "owner_resume#1.asrun").write_bytes(original)
    records = candidate.snapshot_records(source, destination, os.getuid(), os.getgid())
    assert (destination / "owner_resume#1.asrun").read_bytes() == original
    assert (source / "owner_resume#1.asrun").read_bytes() == original
    assert records == [
        dict(
            name="owner_resume#1.asrun",
            bytes=len(original),
            sha256=hashlib.sha256(original).hexdigest(),
            complete_tail=False,
        )
    ]


def test_snapshot_does_not_follow_native_owned_symlink(tmp_path):
    source = tmp_path / "audit"
    source.mkdir()
    secret = tmp_path / "outside"
    secret.write_bytes(b"OUTSIDE")
    (source / "execution.asrun").symlink_to(secret)
    with pytest.raises(OSError):
        candidate.snapshot_records(source, tmp_path / "saved", os.getuid(), os.getgid())
    assert secret.read_bytes() == b"OUTSIDE"
    assert not list((tmp_path / "saved").iterdir())


def test_snapshot_refuses_source_mutation_without_deleting_either_copy(tmp_path, monkeypatch):
    source, destination = tmp_path / "audit", tmp_path / "saved"
    source.mkdir()
    path = source / "execution.asrun"
    path.write_bytes(b"ACK\n")
    original = candidate.os.read
    mutated = False

    def changing(fd, size):
        nonlocal mutated
        data = original(fd, size)
        if not mutated:
            mutated = True
            with path.open("ab") as stream:
                stream.write(b"LATER\n")
        return data

    monkeypatch.setattr(candidate.os, "read", changing)
    with pytest.raises(RuntimeError, match="changed during copy"):
        candidate.snapshot_records(source, destination, os.getuid(), os.getgid())
    assert path.read_bytes() == b"ACK\nLATER\n"
    assert (destination / "execution.asrun").read_bytes() == b"ACK\n"


def test_live_writer_cleanup_failure_cannot_be_relabelled_retained(tmp_path):
    calls = []
    report = {"container_cleanup_failed": True, "native_audit_fault_volumes": [dict(mounted=True)]}
    with pytest.raises(RuntimeError, match="possibly live writer"):
        candidate.finalize(lambda *args: calls.append(args), tmp_path, report)
    assert not calls and report["native_audit_fault_volumes"][0]["mounted"]


def test_native_close_preserves_fixed_audit_failure_stage_and_errno(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "audit_native_session", ROOT / "host_runtime/python/native.py"
    )
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    session = native.NativeSession.__new__(native.NativeSession)
    session.context = session.listener = session.process = None
    session.log = io.StringIO("private noise\nV08_AUDIT_FAILURE stage=record_sync errno=28\n")
    removed = []
    session.directory = SimpleNamespace(cleanup=lambda: removed.append(True))
    with pytest.raises(RuntimeError, match="stage=record_sync errno=28") as failure:
        session.close()
    assert "private noise" not in str(failure.value)
    assert removed == [True]
