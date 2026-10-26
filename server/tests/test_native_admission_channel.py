"""Compile production transport; real Linux signals/credentials, no native claim."""

import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def admission_binary(tmp_path_factory):
    binary = tmp_path_factory.mktemp("admission-channel") / "harness"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(ROOT / "server/tests/native_admission_harness.cpp"),
            "-Wl,--wrap=send",
            "-Wl,--wrap=recv",
            "-Wl,--wrap=poll",
            "-o",
            str(binary),
        ],
        capture_output=True,
        check=True,
        timeout=60,
    )
    return binary


@pytest.mark.parametrize(
    "case",
    [
        "wait_interrupt",
        "wait_deadline",
        "wait_late_ready",
        "oversize",
        "allow",
        "signal_reply",
        "partial_io",
        "deny",
        "lost_reply",
        "wrong_peer",
        "expired_reply",
        "signal_deadline",
        "late_read",
    ],
)
def test_production_admission_channel(admission_binary, tmp_path, case):
    result = subprocess.run(
        [str(admission_binary), case, str(tmp_path / "agent.sock")],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert b"private-authority" not in result.stderr
    failures = [
        json.loads(line[14:])
        for line in result.stderr.splitlines()
        if line.startswith(b"V08_ADMISSION ")
    ]
    if case in (
        "deny",
        "lost_reply",
        "wrong_peer",
        "expired_reply",
        "signal_deadline",
        "late_read",
    ):
        assert len(failures) == 1
        assert set(failures[0]) == {
            "pid",
            "stage",
            "reason",
            "errno",
            "elapsed_ms",
            "interruptions",
            "monotonic_ns",
        }
        if case == "signal_deadline":
            assert failures[0]["interruptions"] > 0
        if case in ("expired_reply", "signal_deadline", "late_read"):
            assert failures[0]["reason"] == "deadline_expired"
            assert failures[0]["stage"] == "read"
    else:
        assert not failures
