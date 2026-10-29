"""Changed frozen inputs must fail before any compiler is launched."""

from native_build_batch import NativeBuildBatch
import json
import subprocess
import pytest


def test_frozen_compiler_snapshot_refuses_drift(tmp_path, request):
    source = tmp_path / "source"
    source.mkdir()
    (source / "value.H").write_text("constexpr int value=1;\n")
    (source / "main.cpp").write_text('#include "value.H"\nint main(){return value;}\n')
    binary = source / "component"
    batch = NativeBuildBatch(source, request)
    batch.add(["c++", "-std=c++17", str(source / "main.cpp"), "-o", str(binary)], timeout=60)
    (batch.snapshots / "0/value.H").write_text("constexpr int value=2;\n")
    with pytest.raises(ValueError, match="Frozen compiler input drift"):
        batch.run()
    assert not binary.exists()
    assert (source / "value.H").read_text() == "constexpr int value=1;\n"


def prepared(tmp_path, request, label, *, macro=0, source="int main(){return VALUE;}\n"):
    folder = tmp_path / (tmp_path.name + "-" + label)
    folder.mkdir()
    (folder / "main.cpp").write_text(source)
    batch = NativeBuildBatch(folder, request)
    batch.add(
        [
            "c++",
            "-std=c++17",
            f"-DVALUE={macro}",
            str(folder / "main.cpp"),
            "-o",
            str(folder / "component"),
        ],
        timeout=60,
    )
    return batch, folder / "component"


def test_identical_sources_reuse_verified_binary_but_execute_fresh_processes(tmp_path, request):
    cache = {}
    first, original = prepared(tmp_path, request, "first")
    second, reused = prepared(tmp_path, request, "second")
    first.run_cached(cache)
    second.run_cached(cache)
    assert len(cache) == 1 and reused.read_bytes() == original.read_bytes()
    receipt = json.loads((second.records / "0.reuse.json").read_text())
    assert receipt["fresh_scenario_processes_required"]
    for binary in (original, reused):
        assert subprocess.run([str(binary)], timeout=5).returncode == 0


def test_binary_reuse_refuses_tampering_before_copy(tmp_path, request):
    cache = {}
    first, original = prepared(tmp_path, request, "first")
    second, reused = prepared(tmp_path, request, "second")
    first.run_cached(cache)
    original.write_bytes(original.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="Cached native executable byte drift"):
        second.run_cached(cache)
    assert not reused.exists()


def test_binary_reuse_refuses_extra_frozen_input_before_copy(tmp_path, request):
    cache = {}
    first, _original = prepared(tmp_path, request, "first")
    second, reused = prepared(tmp_path, request, "second")
    first.run_cached(cache)
    (second.snapshots / "0/extra.H").write_text("unused but unexpected input\n")
    with pytest.raises(ValueError, match="Frozen compiler input drift before reuse"):
        second.run_cached(cache)
    assert not reused.exists()


def test_compiler_flag_change_requires_separate_actual_build(tmp_path, request):
    cache = {}
    first, original = prepared(tmp_path, request, "first")
    second, changed = prepared(tmp_path, request, "second", macro=1)
    first.run_cached(cache)
    second.run_cached(cache)
    assert len(cache) == 2 and not list(second.records.glob("*.reuse.json"))
    assert subprocess.run([str(original)], timeout=5).returncode == 0
    assert subprocess.run([str(changed)], timeout=5).returncode == 1


def test_expanded_source_filename_difference_prevents_binary_reuse(tmp_path, request):
    source = "#include <cstdio>\nint main(){std::puts(__FILE__);}\n"
    cache = {}
    first, original = prepared(tmp_path, request, "first", source=source)
    second, changed = prepared(tmp_path, request, "second", source=source)
    first.run_cached(cache)
    second.run_cached(cache)
    assert len(cache) == 2 and not list(second.records.glob("*.reuse.json"))
    before = subprocess.check_output([str(original)], timeout=5)
    after = subprocess.check_output([str(changed)], timeout=5)
    assert str(first.snapshots).encode() in before
    assert str(second.snapshots).encode() in after and before != after


def test_external_header_comment_drift_requires_a_separate_build(tmp_path, request):
    header = tmp_path / "external.H"
    header.write_text("// first source identity\n")
    source = f'#include "{header}"\nint main(){{return 0;}}\n'
    cache = {}
    first, _original = prepared(tmp_path, request, "first", source=source)
    second, changed = prepared(tmp_path, request, "second", source=source)
    first.run_cached(cache)
    header.write_text("// changed source identity, identical executable tokens\n")
    second.run_cached(cache)
    assert len(cache) == 2 and not list(second.records.glob("*.reuse.json"))
    assert subprocess.run([str(changed)], timeout=5).returncode == 0
