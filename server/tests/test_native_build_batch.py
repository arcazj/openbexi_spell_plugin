"""Changed frozen inputs must fail before any compiler is launched."""

from native_build_batch import NativeBuildBatch
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
