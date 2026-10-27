"""Exact-source trace filtering and scoped CPython filename ownership."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "lib/SPELL_EXC/src/SPELLexecutorImpl.C"
SIGNATURE = "int SPELLexecutorImpl::dispatch("


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "trace_filename_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def method(text):
    start = text.index(SIGNATURE)
    return text[start : text.index("\n}", start) + 2]


@pytest.fixture(scope="session")
def trace_source(tmp_path_factory):
    folder = tmp_path_factory.mktemp("trace-filename-source")
    original = folder / "source"
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed"
    )
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(original)
    saved = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(original)
        apply_native_tree(original, archive, folder / "composition")
    finally:
        sys.path[:] = saved
    assert hashlib.sha256(method((original / RELATIVE).read_text()).encode()).hexdigest() == (
        "4e1946c2c751b938311fb88f89c1202417bd415be60a4cc523ce08d0675ff7b8"
    )
    return original


@pytest.fixture(scope="session")
def filename_binary(trace_source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("trace-filename-compiled")
    candidate = folder / "source"
    shutil.copytree(trace_source, candidate)
    load_builder().reuse_native_trace_filename(candidate)
    for name, source in (("before", trace_source), ("after", candidate)):
        body = method((source / RELATIVE).read_text())
        prefix = body[body.index("{") + 1 : body.index("    // Filter importing state")]
        (folder / ("filename_filter_" + name + ".inc")).write_text(prefix)
    binary = folder / "filename"
    built = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + sysconfig.get_path("include"),
            "-I" + str(ROOT / "host_runtime/native"),
            "-I" + str(folder),
            str(ROOT / "server/tests/native_frame_filename.cpp"),
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert built.returncode == 0, built.stderr
    return binary


def test_compiled_filter_semantics_lifetime_and_allocation_reduction(filename_binary):
    result = subprocess.run(
        [str(filename_binary)],
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
    assert receipt["passed"] and receipt["filter_cases"] == 28
    assert receipt["lookups"] == 30_000
    assert receipt["before_allocations"] >= 30_000
    assert receipt["before_bytes"] > 500_000
    assert receipt["after_allocations"] == receipt["after_bytes"] == 0
    (filename_binary.parent / "measurement.json").write_text(json.dumps(receipt, indent=2) + "\n")


@pytest.mark.parametrize("prompts,terminal", [(False, False), (True, False), (True, True)])
def test_trace_overlay_is_present_in_each_native_composition(
    trace_source, tmp_path, prompts, terminal
):
    source = tmp_path / "source"
    shutil.copytree(trace_source, source)
    before = method((source / RELATIVE).read_text())
    saved = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT / "host_runtime"))
        load_builder().patch_native_tree(source, prompts=prompts, terminal=terminal)
    finally:
        sys.path[:] = saved
    after = method((source / RELATIVE).read_text())
    marker = "    // Filter importing state"
    old_tail = before[before.index(marker) :]
    expected = old_tail.replace(
        "    std::string path = SPELLpython313::filename(frame);",
        "    const std::string& path = file;",
    )
    assert after[after.index(marker) :] == expected
    assert "V08FrameFilename filename(frame);" in after
    assert after.count("fileView.find(") == 2
    assert '#include "/candidate/frame_filename.H"' in (source / RELATIVE).read_text()


@pytest.mark.parametrize("already_patched", [False, True])
def test_trace_patch_rejects_drift_and_reapplication_without_writes(
    trace_source, tmp_path, already_patched
):
    source = tmp_path / "source"
    shutil.copytree(trace_source, source)
    path = source / RELATIVE
    builder = load_builder()
    if already_patched:
        builder.reuse_native_trace_filename(source)
    else:
        path.write_text(
            path.read_text().replace("    // Filter importing state", "    // Changed filter")
        )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="preimage differs"):
        builder.reuse_native_trace_filename(source)
    assert path.read_bytes() == before
