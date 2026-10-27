"""Compile exact native monitor bodies and preserve release/restore semantics."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "include/SPELL_UTIL/SPELLpythonMonitors.H"


def builder():
    spec = importlib.util.spec_from_file_location(
        "thread_labels_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source(tmp_path):
    path = tmp_path / RELATIVE
    path.parent.mkdir(parents=True)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        path.write_bytes(archive.read(RELATIVE))
    return path


def body(text):
    start = text.index("class SPELLsafeThreadOperations\n")
    return text[start : text.index("\n};", start) + 3]


def test_literal_monitor_preserves_nested_unwind_and_avoids_allocations(tmp_path):
    path = source(tmp_path)
    before = body(path.read_text())
    builder().avoid_native_thread_label_copies(tmp_path)
    after = body(path.read_text())
    (tmp_path / "before.inc").write_text(before.replace("SPELLsafeThreadOperations", "Before"))
    (tmp_path / "after.inc").write_text(after.replace("SPELLsafeThreadOperations", "After"))
    binary = tmp_path / "monitor"
    compiled = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(tmp_path),
            str(ROOT / "server/tests/native_thread_labels.cpp"),
            "-o",
            str(binary),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        timeout=30,
        env=dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["same_size"] and receipt["semantics_passed"]
    assert receipt["before_allocations"] == 20_000
    assert receipt["after_allocations"] == 0
    (tmp_path / "measurement.json").write_text(json.dumps(receipt, indent=2) + "\n")


@pytest.mark.parametrize("change", ["drift", "reapply"])
def test_monitor_preimage_rejected_without_writing(tmp_path, change):
    path = source(tmp_path)
    if change == "drift":
        path.write_text(path.read_text().replace("m_where = where;", "m_where = where + 'x';"))
    else:
        builder().avoid_native_thread_label_copies(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="preimage differs"):
        builder().avoid_native_thread_label_copies(tmp_path)
    assert path.read_bytes() == before
