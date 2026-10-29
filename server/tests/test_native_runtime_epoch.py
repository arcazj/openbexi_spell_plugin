"""Exact old/new file semantics, actual Unix admissions and measured retention."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = "892914f10f12bd9a3043a69e07f363a143445ec3"
EPOCH = b"11111111-1111-4111-8111-111111111111"


@pytest.fixture(scope="session")
def epoch_binaries(tmp_path_factory, request):
    include = Path("/usr/include")
    if not (include / "nlohmann/json.hpp").is_file():
        import nlohmann_json

        include = Path(nlohmann_json.get_include())
    folder = tmp_path_factory.mktemp("native-runtime-epoch")
    builds = NativeBuildBatch(folder, request)
    source = folder / "native_runtime_epoch.cpp"
    source.write_bytes((ROOT / "server/tests/native_runtime_epoch.cpp").read_bytes())
    (folder / "inputs.json").write_text(
        json.dumps(
            {
                "component_only": True,
                "baseline": REFERENCE,
                "source_sha256": {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                    for name in [
                        "host_runtime/native/admission_ipc.H",
                        "host_runtime/native/admission_channel.H",
                        "server/tests/native_runtime_epoch.cpp",
                        "server/tests/test_native_runtime_epoch.py",
                    ]
                },
                "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[
                    0
                ],
            },
            indent=2,
        )
        + "\n"
    )
    binaries = {}
    for name in ("before", "after"):
        headers = folder / name
        headers.mkdir()
        flags = []
        if name == "before":
            baseline = (ROOT / "server/tests/native_runtime_epoch_baseline.H").read_bytes()
            assert (
                hashlib.sha256(baseline).hexdigest()
                == "c6ddab63d76616b7e8a0b93513d62434b1a71bc1c158e083bd0c533784016bdd"
            )
            (headers / "admission_ipc.H").write_bytes(baseline)
            flags.append("-DV08_FROZEN_EPOCH")
        binary = folder / (name + "-epoch")
        builds.add(
            [
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
                str(source),
                "-Wl,--wrap=open",
                "-Wl,--wrap=read",
                "-Wl,--wrap=__read_chk",
                "-o",
                str(binary),
            ],
            timeout=60,
        )
        binaries[name] = binary
    builds.run()
    return binaries


def invoke(binary, mode, path, *args):
    result = subprocess.run(
        [str(binary), mode, str(path), *map(str, args)],
        capture_output=True,
        timeout=30,
        env=dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1",
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "content",
    [
        EPOCH,
        EPOCH + b"\n",
        b"",
        b"\n",
        EPOCH[:-1],
        EPOCH + b"X",
        EPOCH + b"\r\n",
        EPOCH + b"\n\n",
        EPOCH + b"\nX",
        b"\n" + EPOCH,
        b"x" * 100000,
        b"x" * 35 + b"\x00",
        b"x" * 36,
    ],
    ids=[
        "uuid",
        "uuid-lf",
        "empty",
        "empty-line",
        "short",
        "long",
        "crlf",
        "extra-lf",
        "extra-record",
        "leading-lf",
        "oversized",
        "nul-preserved",
        "non-uuid-preserved",
    ],
)
def test_epoch_reader_matches_frozen_exact_file_contract(epoch_binaries, tmp_path, content):
    path = tmp_path / "epoch"
    path.write_bytes(content)
    before = invoke(epoch_binaries["before"], "read", path)
    after = invoke(epoch_binaries["after"], "read", path)
    assert after == before


def test_missing_epoch_is_denied(epoch_binaries, tmp_path):
    assert invoke(epoch_binaries["after"], "read", tmp_path / "missing") == {"accepted": False}


@pytest.mark.parametrize("mode", ["faults", "concurrent", "cancel"])
def test_epoch_read_ownership_concurrency_and_cancellation(epoch_binaries, tmp_path, mode):
    path = tmp_path / "epoch"
    path.write_bytes(EPOCH + b"\n")
    assert invoke(epoch_binaries["after"], mode, path)


def test_full_admissions_remove_the_measured_eight_kib_file_allocations(epoch_binaries, tmp_path):
    path = tmp_path / "epoch"
    path.write_bytes(EPOCH + b"\n")
    measurements = {}
    with tempfile.TemporaryDirectory(prefix="epoch-sockets-") as short:
        for name, binary in epoch_binaries.items():
            path.write_bytes(EPOCH + b"\n")
            measurements[name] = invoke(binary, "measure", path, Path(short) / (name + ".sock"))
    before, after = measurements["before"], measurements["after"]
    assert before["requests"] == after["requests"] == 10000
    assert before["fresh_epoch_rotated"] and after["fresh_epoch_rotated"]
    assert before["file_buffer_allocations"] == 10000 and after["file_buffer_allocations"] == 0
    assert before["heap_growth_bytes"] - after["heap_growth_bytes"] > 60 * 1024**2
    assert abs(after["live_after"] - before["live_after"]) < 8192
    (tmp_path / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
    print(json.dumps(measurements))


def test_epoch_reader_removes_measured_file_buffer_retention(epoch_binaries, tmp_path):
    path = tmp_path / "epoch"
    path.write_bytes(EPOCH + b"\n")
    measurements = {
        name: invoke(binary, "measure-reader", path) for name, binary in epoch_binaries.items()
    }
    before, after = measurements["before"], measurements["after"]
    assert before["reads"] == after["reads"] == 10000
    assert before["file_buffer_allocations"] == 10000 and after["file_buffer_allocations"] == 0
    assert before["heap_growth_bytes"] - after["heap_growth_bytes"] > 60 * 1024**2
    assert abs(after["live_after"] - before["live_after"]) < 8192
    (tmp_path / "reader-measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
    print(json.dumps(measurements))
