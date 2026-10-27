"""Failed diagnostics must survive teardown; live state must remain intact."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "native_cleanup_candidate", ROOT / "scripts/qualify_v08_native_launch.py"
)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def test_identity_failure_retains_actual_missing_process_and_call_site(monkeypatch):
    calls = []

    def top(*args):
        calls.append(args)
        return "PID COMMAND\n10 python\n11 SPELL-Listener\n12 SPELL-Context\n"

    monkeypatch.setattr(candidate, "command", top)
    report = {"passed": True}
    try:
        candidate.host_processes("worker-3")
    except candidate.NativeIdentityError as error:
        candidate.retain_failure(report, error)
    else:
        pytest.fail("Missing original Executor was accepted")
    assert not report["passed"]
    failure = report["failures"][0]
    assert failure["native_identity"]["observed"] == [
        {"host_pid": 11, "executable": "SPELL-Listener"},
        {"host_pid": 12, "executable": "SPELL-Context"},
    ]
    assert failure["native_identity"]["expected_executors"] == 1
    assert failure["native_identity"]["container"] == "worker-3"
    assert failure["frames"][-1]["function"] == "host_processes"
    assert calls == [("docker", "top", "worker-3", "-eo", "pid,comm")]


def test_complete_native_identity_preserves_exact_original_processes(monkeypatch):
    monkeypatch.setattr(
        candidate,
        "command",
        lambda *args: "PID COMMAND\n11 SPELL-Listener\n12 SPELL-Context\n13 SPELL-Executor\n",
    )
    assert [row["host_pid"] for row in candidate.host_processes("worker")] == [11, 12, 13]


def test_cleanup_cannot_hide_native_failure(monkeypatch, tmp_path):
    directory = tmp_path / "authority"
    directory.mkdir()
    (directory / "receipt").write_text("original failure evidence")
    monkeypatch.setattr(candidate.tempfile, "mkdtemp", lambda **k: str(directory))

    def cleanup(_):
        raise OSError("Directory not empty")

    monkeypatch.setattr(candidate.shutil, "rmtree", cleanup)
    report = {"passed": False}
    with pytest.raises(TimeoutError, match="member binding"):
        with candidate.qualification_workspace(report):
            raise TimeoutError("Native member binding timed out")
    assert report["error"] == "TimeoutError: Native member binding timed out"
    assert [f["phase"] for f in report["failures"]] == ["qualification", "workspace_cleanup"]
    assert (directory / "receipt").read_text() == "original failure evidence"


def test_cleanup_failure_is_failed_evidence_even_after_success(monkeypatch, tmp_path):
    directory = tmp_path / "result"
    directory.mkdir()
    monkeypatch.setattr(candidate.tempfile, "mkdtemp", lambda **k: str(directory))

    def cleanup(_):
        raise PermissionError("cleanup denied")

    monkeypatch.setattr(candidate.shutil, "rmtree", cleanup)
    report = {"passed": True}
    with candidate.qualification_workspace(report):
        pass
    assert not report["passed"] and "PermissionError" in report["error"]


def test_one_failed_container_removal_does_not_skip_others_or_delete_live_state(
    monkeypatch, tmp_path
):
    directory = tmp_path / "live"
    directory.mkdir()
    (directory / "context.sqlite3").write_bytes(b"held authority state")
    monkeypatch.setattr(candidate.tempfile, "mkdtemp", lambda **k: str(directory))
    calls = []

    def remove(args, **kwargs):
        calls.append(args)
        if args[-1] == "worker":
            raise subprocess.TimeoutExpired(args, 20)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate.subprocess, "run", remove)
    report = {"passed": True}
    with candidate.qualification_workspace(report):
        candidate.cleanup_resources(["authority", "worker"], ["internal-network"], report)
    assert [args[-1] for args in calls] == ["worker", "authority", "internal-network"]
    assert not report["passed"] and report["container_cleanup_failed"]
    assert (directory / "context.sqlite3").read_bytes() == b"held authority state"
