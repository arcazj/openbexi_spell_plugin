"""Actual failed subprocesses remain failed, with usable qualification logs."""

import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "qualification_runner_test", ROOT / "scripts/qualify_v08_server.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_actual_timed_out_check_keeps_progress_and_failure_without_a_pass(tmp_path):
    command = [
        sys.executable,
        "-I",
        "-c",
        "import os,time;os.write(1,b'bounded-progress\\n');time.sleep(30)",
    ]
    result = module.run_check("timed", command, ROOT, dict(os.environ), tmp_path, 0.3)
    assert result["timed_out"] is True and result["exit_code"] == 124
    assert b"bounded-progress" in (tmp_path / "timed.log").read_bytes()


def test_actual_nonzero_check_is_retained_as_failed_without_timeout(tmp_path):
    command = [sys.executable, "-I", "-c", "print('rejected-check',flush=True);raise SystemExit(3)"]
    result = module.run_check("rejected", command, ROOT, dict(os.environ), tmp_path, 2)
    assert result["timed_out"] is False and result["exit_code"] == 3
    assert b"rejected-check" in (tmp_path / "rejected.log").read_bytes()
