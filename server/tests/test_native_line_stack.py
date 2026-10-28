"""Compile actual native stack/LINE methods and retain identical output bytes."""

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
METHODS = {
    "lib/SPELL_EXC/src/SPELLcallstack.C": [
        "const std::string SPELLcallstack::getStack()",
        "const std::string SPELLcallstack::getFullStack()",
        "void SPELLcallstack::v08StackInto(",
        "void SPELLcallstack::v08FullStackInto(",
        "void v08CopyCallstackSnapshot(",
    ],
    "lib/SPELL_CIF/src/SPELLcif.C": [
        "std::string SPELLcif::getAvailableStack()",
        "void SPELLcif::v08AvailableStackInto(",
        "void  SPELLcif::notifyLine()",
    ],
    "lib/SPELL_CIFS/src/SPELLserverCif.C": ["void SPELLserverCif::completeMessage("],
}


@pytest.fixture(scope="module")
def line_stack_source(tmp_path_factory):
    folder = tmp_path_factory.mktemp("line-stack-source")
    source = folder / "before"
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(source)
    saved = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, archive, folder / "composition")
    finally:
        sys.path[:] = saved
    spec = importlib.util.spec_from_file_location(
        "line_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.reuse_native_timestamp_and_asrun(source)
    return source, builder


def test_exact_methods_preserve_bytes_reentrancy_and_reduce_allocations(
    line_stack_source, tmp_path
):
    source, builder = line_stack_source
    candidate = tmp_path / "after-source"
    shutil.copytree(source, candidate)
    builder.reuse_native_line_stack(candidate)
    results = []
    for name, tree in [("before", source), ("after", candidate)]:
        methods = []
        for relative, signatures in METHODS.items():
            text = (tree / relative).read_text()
            for signature in signatures:
                if signature not in text:
                    assert name == "before" and (
                        "::v08" in signature or signature.startswith("void v08")
                    )
                    continue
                start = text.index(signature)
                methods.append(text[start : text.index("\n}", start) + 2])
        (tmp_path / "line_methods.inc").write_text("\n".join(methods))
        # Compile through the actual frozen/candidate interface. Transport and
        # unused dispatch-listener methods remain explicit component adapters.
        for directory in ["SPELL_EXC", "SPELL_UTIL"]:
            (tmp_path / directory).mkdir(exist_ok=True)
        shutil.copyfile(
            tree / "include/SPELL_EXC/SPELLcallstackIF.H", tmp_path / "SPELL_EXC/SPELLcallstackIF.H"
        )
        (tmp_path / "SPELL_EXC/SPELLdispatchListener.H").write_text(
            "#pragma once\nstruct SPELLdispatchListener {};\n"
        )
        (tmp_path / "SPELL_EXC/SPELLstepOverMode.H").write_text(
            "#pragma once\nstruct SPELLstepOverMode {};\n"
        )
        (tmp_path / "SPELL_UTIL/SPELLbase.H").write_text("#pragma once\n#include <string>\n")
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
                "-I" + str(ROOT / "host_runtime/native"),
                "-DV08_STACK_REUSE=" + str(int(name == "after")),
                str(ROOT / "server/tests/native_line_stack.cpp"),
                "-o",
                str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert built.returncode == 0, built.stderr
        run = subprocess.run(
            [str(binary), str(tmp_path / (name + ".ASRUN"))],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                "ASAN_OPTIONS": "detect_leaks=0:abort_on_error=1",
                "UBSAN_OPTIONS": "halt_on_error=1",
            },
        )
        (tmp_path / (name + ".stdout")).write_text(run.stdout)
        (tmp_path / (name + ".stderr")).write_text(run.stderr)
        assert run.returncode == 0, run.stdout + run.stderr
        results.append(json.loads(run.stdout))
    before, after = results
    left, right = [(tmp_path / (name + ".ASRUN")).read_bytes() for name in ["before", "after"]]
    assert left == right and len(left.splitlines()) == 10004
    assert before["notification_allocations"] >= 10000
    assert before["metadata_allocations"] >= 10000
    assert after["notification_allocations"] == after["metadata_allocations"] == 0
    assert before["metadata_digest"] == after["metadata_digest"]
    (tmp_path / "measurement.json").write_text(
        json.dumps(
            {
                "before": before,
                "after": after,
                "audit_sha256": hashlib.sha256(left).hexdigest(),
                "audit_bytes": len(left),
            },
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("duplicate", [False, True])
def test_stack_overlay_rejects_drift_before_writing(line_stack_source, tmp_path, duplicate):
    source, builder = line_stack_source
    target = tmp_path / "source"
    shutil.copytree(source, target)
    if duplicate:
        builder.reuse_native_line_stack(target)
    else:
        path = target / "lib/SPELL_CIFS/src/SPELLserverCif.C"
        path.write_text(
            path.read_text().replace(
                "std::string stack = getAvailableStack();",
                "std::string stack = getAvailableStack(); // changed",
            )
        )
    before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="preimage differs|boundary differs"):
        builder.reuse_native_line_stack(target)
    assert before == {
        str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()
    }
