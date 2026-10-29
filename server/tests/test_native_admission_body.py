"""Own temporary JSON without copying; preserve the actual admission channel."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "c920349c2c54ce3fe968de4b1d47046203e30516"
BASELINE_SHA256 = "ec80c474c5c332163274f01d60a396d9166384b978927e323567b0bedb58b4d5"


@pytest.fixture(scope="session")
def admission_body_binaries(tmp_path_factory, request):
    include = Path("/usr/include")
    if not (include / "nlohmann/json.hpp").is_file():
        import nlohmann_json

        include = Path(nlohmann_json.get_include())
    folder = tmp_path_factory.mktemp("native-admission-body")
    builds = NativeBuildBatch(folder, request)
    baseline = (ROOT / "server/tests/native_admission_body_before_dev79.H").read_bytes()
    assert hashlib.sha256(baseline).hexdigest() == BASELINE_SHA256
    binaries = {}
    for name in ("before", "after"):
        headers = folder / name
        headers.mkdir()
        flags = []
        if name == "before":
            (headers / "admission_ipc.H").write_bytes(baseline)
        else:
            flags.append("-DV08_OWNED_BODY")
        binary = folder / (name + "-admission-body")
        command = [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(headers),
            "-I" + str(ROOT / "host_runtime/native"),
            "-I" + str(include),
            *flags,
            str(ROOT / "server/tests/native_admission_body.cpp"),
            "-o",
            str(binary),
        ]
        builds.add(command, timeout=90)
        binaries[name] = binary
    for name, compiled in zip(binaries, builds.run()):
        (folder / (name + "-compile.log")).write_bytes(compiled.stdout + compiled.stderr)
    names = [
        "host_runtime/native/admission_ipc.H",
        "host_runtime/native/admission_channel.H",
        "server/tests/native_admission_body.cpp",
        "server/tests/test_native_admission_body.py",
        "server/tests/native_admission_body_before_dev79.H",
    ]
    (folder / "inputs.json").write_text(
        json.dumps(
            {
                "component_only": True,
                "baseline": BASELINE,
                "source_sha256": {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names
                },
                "json_header_sha256": hashlib.sha256(
                    (include / "nlohmann/json.hpp").read_bytes()
                ).hexdigest(),
                "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[
                    0
                ],
                "binary_sha256": {
                    name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for name, path in binaries.items()
                },
            },
            indent=2,
        )
        + "\n"
    )
    return binaries


def invoke(binary, mode, directory):
    with tempfile.TemporaryDirectory(prefix="admission-body-") as short:
        result = subprocess.run(
            [str(binary), mode, str(directory / "epoch"), str(Path(short) / "agent.sock")],
            capture_output=True,
            timeout=60,
            env=dict(
                os.environ,
                ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
                UBSAN_OPTIONS="halt_on_error=1",
            ),
        )
    (directory / (binary.name + "-" + mode + ".stdout")).write_bytes(result.stdout)
    (directory / (binary.name + "-" + mode + ".stderr")).write_bytes(result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode == "failures":
        lines = result.stderr.splitlines()
        assert len(lines) == 2 and all(line.startswith(b"V08_ADMISSION ") for line in lines)
        assert all(
            json.loads(line[14:])["reason"]
            in {"admission_denied", "reply_lost", "channel_unavailable"}
            for line in lines
        )
    else:
        assert not result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("case", ["ownership", "failures", "concurrency", "cancellation"])
def test_owned_admission_preserves_real_transport_and_lifetimes(
    admission_body_binaries, tmp_path, case
):
    result = invoke(admission_body_binaries["after"], case, tmp_path)
    assert result


def test_frozen_const_reference_and_failure_behavior_matches(admission_body_binaries, tmp_path):
    for case in ("ownership", "failures"):
        before = invoke(admission_body_binaries["before"], case, tmp_path)
        after = invoke(admission_body_binaries["after"], case, tmp_path)
        assert after == before


@pytest.mark.parametrize("mode", ["benchmark", "benchmark-lvalue"])
def test_exact_json_copy_cost_and_identical_native_packets(admission_body_binaries, tmp_path, mode):
    results = {
        name: invoke(binary, mode, tmp_path) for name, binary in admission_body_binaries.items()
    }
    before, after = results["before"], results["after"]
    assert before["requests"] == after["requests"] == 10000
    for key in ("wire_bytes", "wire_fnv1a64", "one_body_copy_allocations", "one_body_copy_bytes"):
        assert before[key] == after[key]
    assert (
        before["all_packets_match_independent_literal_oracle"]
        and after["all_packets_match_independent_literal_oracle"]
    )
    assert before["fresh_epoch_rotation"] and after["fresh_epoch_rotation"]
    copies = 0 if mode == "benchmark-lvalue" else 10000
    assert (
        before["caller_allocations"] - after["caller_allocations"]
        == copies * before["one_body_copy_allocations"]
    )
    assert (
        before["caller_allocated_bytes"] - after["caller_allocated_bytes"]
        == copies * before["one_body_copy_bytes"]
    )
    assert after["caller_allocations"] > 0  # JSON encoding and fresh epoch work remain measured.
    (tmp_path / "measurements.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"mode": mode, "measurements": results}))
