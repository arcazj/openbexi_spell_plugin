"""Compile the exact callback before/after; compare branches and allocation churn."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "lib/SPELL_CTX/src/SPELLexecutor.C"


@pytest.fixture(scope="module")
def callback_source(tmp_path_factory):
    folder = tmp_path_factory.mktemp("callback-identifier")
    source = folder / "source"
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        archive.extractall(source)
    saved = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(
            source, ROOT / "docs/reference/SPELL2.6.10-src.zip", folder / "composition"
        )
    finally:
        sys.path[:] = saved
    spec = importlib.util.spec_from_file_location(
        "callback_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.borrow_native_message_callbacks(source)
    return source, builder


def method(source):
    text = (source / RELATIVE).read_text()
    start = text.index("void SPELLexecutor::processMessageFromExecutor(")
    return text[start : text.index("\n}", start) + 2]


def test_exact_compiled_callback_keeps_dispatch_and_avoids_id_copy(callback_source, tmp_path):
    source, builder = callback_source
    candidate = tmp_path / "source"
    shutil.copytree(source, candidate)
    builder.compare_native_callback_identifier(candidate)
    outputs = []
    for name, tree in (("before", source), ("after", candidate)):
        (tmp_path / "callback.inc").write_text(method(tree))
        binary = tmp_path / name
        built = subprocess.run(
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
                str(ROOT / "server/tests/native_callback_identifier.cpp"),
                "-o",
                str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert built.returncode == 0, built.stderr
        result = subprocess.run(
            [str(binary)],
            capture_output=True,
            text=True,
            timeout=30,
            env=dict(
                os.environ,
                ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
                UBSAN_OPTIONS="halt_on_error=1",
            ),
        )
        assert result.returncode == 0, result.stderr
        outputs.append(json.loads(result.stdout))
    before, after = outputs
    assert before["semantics"] == after["semantics"]
    assert before["allocations"] >= 10_000
    assert after["allocations"] == 0
    (tmp_path / "measurement.json").write_text(
        json.dumps(dict(before=before, after=after), indent=2) + "\n"
    )


@pytest.mark.parametrize("duplicate", [False, True])
def test_callback_overlay_rejects_drift_and_duplicate_application(
    callback_source, tmp_path, duplicate
):
    source, builder = callback_source
    candidate = tmp_path / "source"
    shutil.copytree(source, candidate)
    if duplicate:
        builder.compare_native_callback_identifier(candidate)
    else:
        path = candidate / RELATIVE
        path.write_text(
            path.read_text().replace(
                "std::string id = msg.getId();", "std::string id = msg.getId(); // changed"
            )
        )
    old = hashlib.sha256((candidate / RELATIVE).read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="preimage differs"):
        builder.compare_native_callback_identifier(candidate)
    assert hashlib.sha256((candidate / RELATIVE).read_bytes()).hexdigest() == old
