"""Audit collection must retain invalid data and refuse live-writer ownership changes."""

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "audit_storage", ROOT / "scripts/v08_audit_storage.py"
)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def test_records_and_prior_generations_are_hashed_without_rewriting(tmp_path):
    folder = tmp_path / "native-audit/worker"
    folder.mkdir(parents=True)
    original = b"# header\n2026-10-27 00:00:00\t0\tINIT\n2026-10-27 00:00:01\t1\tLINE\n"
    (folder / "execution.ASRUN.archive.0").write_bytes(original)
    (folder / "execution.ASRUN").write_bytes(original)
    calls = []
    report = {}
    candidate.expose_after_stop(lambda *args: calls.append(args), tmp_path, report)
    result = json.loads((tmp_path / "native-audit-files.json").read_text())
    assert len(calls) == 1 and calls[0][:4] == ("sudo", "-n", "chown", "-hR")
    assert len(result["files"]) == 2
    assert all(r["records"] == 2 and r["last_sequence"] == 1 for r in result["files"])
    assert all(p.read_bytes() == original for p in folder.iterdir())
    assert result["required_records_deleted"] is False


def test_possibly_live_writer_prevents_ownership_change_and_collection(tmp_path):
    (tmp_path / "native-audit/worker").mkdir(parents=True)
    calls = []
    with pytest.raises(RuntimeError, match="possibly live writer"):
        candidate.expose_after_stop(
            lambda *a: calls.append(a), tmp_path, {"container_cleanup_failed": True}
        )
    assert not calls and not (tmp_path / "native-audit-files.json").exists()


@pytest.mark.parametrize(
    "contents",
    [
        b"2026-10-27 00:00:00\t0\tINIT\n2026-10-27 00:00:01\t2\tGAP\n",
        b"2026-10-27 00:00:00\t1\tLINE\n2026-10-27 00:00:01\t0\tREVERSED\n",
        b"2026-10-27 00:00:00\t0\tINCOMPLETE",
    ],
)
def test_gap_reversal_and_uncertain_tail_fail_without_deleting_records(tmp_path, contents):
    folder = tmp_path / "native-audit/worker"
    folder.mkdir(parents=True)
    path = folder / "execution.ASRUN"
    path.write_bytes(contents)
    with pytest.raises(RuntimeError):
        candidate.expose_after_stop(lambda *a: None, tmp_path, {})
    assert path.read_bytes() == contents
    result = json.loads((tmp_path / "native-audit-files.json").read_text())
    assert result["validation_passed"] is False
    assert result["files"][0]["sha256"] == hashlib.sha256(contents).hexdigest()
    assert result["files"][0]["bytes"] == len(contents)


def test_uncertain_file_does_not_hide_other_raw_records_and_generations(tmp_path):
    folder = tmp_path / "native-audit/worker"
    folder.mkdir(parents=True)
    contents = {
        "a-uncertain.ASRUN": b"2026-10-27 00:00:00\t0\tPARTIAL",
        "b-oversized.ASRUN": b"x" * (2 * 1024 * 1024 + 27) + b"\n",
        "c-complete.ASRUN.archive.0": b"2026-10-27 00:00:00\t0\tCOMPLETE\n",
    }
    for name, value in contents.items():
        (folder / name).write_bytes(value)
    report = {}
    with pytest.raises(RuntimeError, match="all raw files retained"):
        candidate.expose_after_stop(lambda *a: None, tmp_path, report)
    result = report["native_audit_storage"]
    assert result["validation_failures"] == ["incomplete_tail", "record_exceeds_verifier_bound"]
    assert len(result["files"]) == 3
    for row in result["files"]:
        original = contents[Path(row["path"]).name]
        assert row["sha256"] == hashlib.sha256(original).hexdigest()
        assert row["bytes"] == len(original)
        assert (tmp_path / row["path"]).read_bytes() == original


@pytest.mark.parametrize("label", ["../outside", "x/y", "x\n", ""])
def test_invalid_worker_storage_identity_has_no_filesystem_or_command_effect(tmp_path, label):
    calls = []
    with pytest.raises(ValueError):
        candidate.provision(lambda *a: calls.append(a), tmp_path, label)
    assert not calls and not list(tmp_path.iterdir())


def test_temporary_memory_backing_is_not_accepted_for_durable_records(tmp_path):
    calls = []

    def command(*args):
        calls.append(args)
        return "tmpfs\n"

    with pytest.raises(ValueError, match="durable disk backing"):
        candidate.provision(command, tmp_path, "worker")
    assert len(calls) == 1
