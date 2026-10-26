"""Startup evidence is bounded, read only and contains no raw member identity."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "startup_diagnostics", ROOT / "host_runtime/python/startup_diagnostics.py"
)
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def record(**values):
    return dict(member="0123456789abcdef", pid=123, stage="entered", monotonic_ns=1, **values)


def encode(value):
    return b"V08_START " + json.dumps(value).encode() + b"\n"


def test_compiled_diagnostic_is_atomic_and_never_contains_identity_or_arguments(tmp_path):
    source, binary = tmp_path / "trace.cpp", tmp_path / "trace"
    source.write_text("""
#include "startup_trace.H"
#include <thread>
int main() {
    auto trace = [] { for (int n=0;n<100;n++)
        v08_start_trace("private/procedure#1", "entered"); };
    std::thread other(trace); trace(); other.join();
}
""")
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    result = subprocess.run([str(binary)], check=True, capture_output=True, timeout=5)
    assert not result.stdout and b"private" not in result.stderr
    records = diagnostics.trace_records(result.stderr)
    assert len(records) == 200
    assert len({r["member"] for r in records}) == 1
    assert all(r["stage"] == "entered" for r in records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pid", True),
        ("pid", 0),
        ("stage", "secret-value"),
        ("member", "procedure/arguments"),
        ("monotonic_ns", -1),
    ],
)
def test_untrusted_records_cannot_inject_raw_data(field, value):
    changed = record()
    changed[field] = value
    assert diagnostics.trace_records(encode(changed)) == []


def test_malformed_and_extra_fields_are_discarded_and_records_are_bounded():
    assert (
        diagnostics.trace_records(b"V08_START not-json\n" + encode(record(secret="private"))) == []
    )
    assert len(diagnostics.trace_records(encode(record()) * 2000)) == 1024


def test_process_snapshot_never_reads_arguments_environment_or_arbitrary_logs(tmp_path):
    proc, temporary = tmp_path / "proc", tmp_path / "tmp"
    proc.mkdir()
    temporary.mkdir()
    executable = tmp_path / "SPELL-Executor_v3"
    executable.touch()
    process = proc / "23"
    task = process / "task/24"
    task.mkdir(parents=True)
    (process / "exe").symlink_to(executable)
    (process / "stat").write_text("23 (private name) S 12 0 0\n")
    (task / "stat").write_text("24 (private name) S 12 0 0\n")
    (task / "wchan").write_text("futex_wait_queue")
    (process / "cmdline").write_text("private capability arguments")
    (process / "environ").write_text("private secret")
    session = temporary / "spell-host-test"
    session.mkdir()
    (session / "native.log").write_bytes(b"private raw log\n" + encode(record()))
    value = diagnostics.snapshot(proc, temporary)
    assert value["traces"] == [record()]
    assert value["processes"] == [
        dict(
            pid=23,
            ppid=12,
            executable="SPELL-Executor_v3",
            tasks=[dict(tid=24, state="S", wait="futex_wait_queue")],
        )
    ]
    assert "private" not in json.dumps(value)
