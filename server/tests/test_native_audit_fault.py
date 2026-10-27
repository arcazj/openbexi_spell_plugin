"""Actual descriptor copies and failure retention; full native disk fault is hosted."""

import hashlib
import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "audit_fault", ROOT / "scripts/v08_native_audit_fault.py"
)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


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
