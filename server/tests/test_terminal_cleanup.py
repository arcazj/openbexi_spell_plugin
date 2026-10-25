"""Cleanup evidence must identify the original isolated process family."""

import importlib.util
from pathlib import Path
import os
import select
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "terminal_cohort", ROOT / "scripts/v08_terminal_cohort.py"
)
cohort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cohort)


@pytest.mark.parametrize(
    "change",
    [
        {"Id": "replacement-container"},
        {"Image": "substituted-image"},
        {"Running": True},
        {"Pid": 1},
        {"OOMKilled": True},
        {"ExitCode": 1},
    ],
)
def test_cleanup_rejects_replacement_survivor_and_unclean_exit(change):
    info = dict(
        Id="original-container",
        Image="exact-image",
        State=dict(Running=False, Pid=0, OOMKilled=False, ExitCode=0),
    )
    cohort.validate_stopped(info, "original-container", "exact-image")
    for key, value in change.items():
        (info if key in {"Id", "Image"} else info["State"])[key] = value
    with pytest.raises(RuntimeError, match="identity or clean exit"):
        cohort.validate_stopped(info, "original-container", "exact-image")


@pytest.mark.skipif(not hasattr(os, "pidfd_open"), reason="Linux pidfd qualification")
def test_original_process_handle_distinguishes_live_from_exited():
    process = subprocess.Popen(["sleep", "30"])
    handles = []
    try:
        handles = cohort.capture_process_handles(
            lambda *args: f"PID\n{process.pid}\n", "original-container"
        )
        assert len(handles) == 1
        assert not select.select(handles, [], [], 0)[0]
        process.terminate()
        process.wait(timeout=5)
        assert select.select(handles, [], [], 1)[0] == handles
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for handle in handles:
            os.close(handle)
