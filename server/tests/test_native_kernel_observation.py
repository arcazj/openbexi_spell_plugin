"""Real util-linux boot timestamps and redacted host-query failure provenance."""

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
endurance = importlib.import_module("v08_endurance")
launch = importlib.import_module("qualify_v08_native_launch")


def kill_line(pid, stamp):
    return (
        f"[{stamp // 10**9:5d}.{stamp % 10**9 // 1000:06d}] Memory cgroup out of memory: "
        f"Killed process {pid} (SPELL-Context) total-vm:123kB, anon-rss:45kB, "
        "file-rss:6kB, shmem-rss:7kB, UID:1000 pgtables:8kB oom_score_adj:0"
    )


def test_real_dmesg_file_preserves_default_boot_timestamp(tmp_path):
    binary = shutil.which("dmesg")
    assert binary, "util-linux dmesg is required by the native host observer"
    pid, stamp = os.getpid(), time.monotonic_ns()
    source = tmp_path / "kernel.log"
    source.write_text("<3>" + kill_line(pid, stamp) + "\n")
    fd = os.pidfd_open(pid)
    calls = []

    def command(*args, timeout):
        calls.append(args)
        # Real util-linux invocation with the production observer's options.
        # Reading a fixture needs neither sudo nor kernel ring-buffer access.
        assert args[:3] == ("sudo", "-n", "dmesg")
        result = subprocess.run(
            [binary, "--file", str(source), *args[3:]],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        return result.stdout

    try:
        result = endurance.process_failure_observation(
            {pid: fd},
            {"Id": "fixture", "State": {"Pid": pid}},
            command=command,
            earliest_ns=stamp - 10**9,
        )
    finally:
        os.close(fd)
    assert len(calls) == 1
    assert result["kernel_query_returncode"] == 0
    assert result["kernel_victim_pid_observed"] is True
    (event,) = result["kernel_events"]
    assert event["host_pid"] == pid
    assert abs(event["kernel_boot_ns"] - stamp) < 1000
    assert result["kernel_query_start_ns"] <= result["kernel_query_end_ns"]
    assert result["oom_cause_inferred"] is False


@pytest.mark.parametrize(
    "failure", [RuntimeError("SECRET"), subprocess.TimeoutExpired("SECRET", 10)]
)
def test_failed_query_preserves_type_time_and_available_exit_code(failure):
    failure.returncode = 7

    def command(*_args, **_kwargs):
        raise failure

    result = endurance.process_failure_observation(
        {},
        {"Id": "fixture", "State": {"Pid": 1}},
        command=command,
    )
    assert result["kernel_observation_error"] == type(failure).__name__
    assert result["kernel_query_returncode"] == 7
    assert result["kernel_query_start_ns"] <= result["kernel_query_end_ns"]
    assert not result["kernel_victim_pid_observed"]
    assert "SECRET" not in json.dumps(result)


def test_host_command_retains_exit_status_without_raw_output():
    with pytest.raises(RuntimeError) as caught:
        launch.command(sys.executable, "-c", "import sys;print('SECRET');sys.exit(23)")
    assert caught.value.returncode == 23
    assert "SECRET" not in str(caught.value)
