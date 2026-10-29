"""Compare the actual bridge line loop with the immutable dev81 input loop.

This component measures line allocations and checks stream/parser behavior.
It does not execute the bridge transport or qualify whole-family memory use.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def line_binary(tmp_path_factory, request):
    folder = tmp_path_factory.mktemp("native-bridge-line")
    baseline = (ROOT / "server/tests/native_bridge_line_before_dev81.inc").read_text()
    assert hashlib.sha256(baseline.encode()).hexdigest() == (
        "26016481a3af6f0b6ac5cecf7b4714637fcd8647247803189d8866366935b949"
    )
    current = (ROOT / "host_runtime/native/private_bridge.cpp").read_text()
    start = current.index("        // Keep one input buffer for this connection;")
    end = current.index("            Json request=Json::parse(line);", start)
    candidate = current[start:end]
    loops = []
    for name, body in (("Before", baseline), ("After", candidate)):
        loops.append(
            f"template<class Consume> void bridgeLine{name}(std::istream& input,Consume consume) {{\n"
            + body.replace("std::cin", "input")
            + "            consume(line);\n        }\n}\n"
        )
    (folder / "bridge_line_loops.inc").write_text("\n".join(loops))
    binary = folder / "bridge-line"
    builds = NativeBuildBatch(folder, request)
    builds.add(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(folder),
            str(ROOT / "server/tests/native_bridge_line_harness.cpp"),
            "-o",
            str(binary),
        ],
        text=True,
        timeout=60,
    )
    builds.run()
    return binary


def run(binary, mode):
    result = subprocess.run(
        [str(binary), mode],
        capture_output=True,
        text=True,
        timeout=30,
        env=dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
        ),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "empty_line",
        "unterminated",
        "crlf",
        "empty_after_valid",
        "embedded_nul",
        "malformed",
        "unicode",
        "binary_escape",
        "mixed_sizes",
        "limit_minus_one",
        "limit",
        "limit_eof",
        "oversize",
        "oversize_after_small",
        "failbit",
        "badbit",
        "eofbit",
        "eof_exception",
        "fail_exception",
        "invalid_utf8",
    ],
)
def test_line_reuse_preserves_stream_boundaries_and_owned_json(line_binary, case):
    run(line_binary, case)


@pytest.mark.parametrize("width", ["short", "long"])
@pytest.mark.parametrize("consumer", ["raw", "parse"])
def test_line_reuse_removes_measured_allocations(line_binary, width, consumer):
    before = run(line_binary, f"alloc_{width}_{consumer}_before")
    after = run(line_binary, f"alloc_{width}_{consumer}_after")
    assert before["iterations"] == after["iterations"] == 10000
    assert before["digest"] == after["digest"]
    assert before["allocations"] > after["allocations"]
    assert before["allocated_bytes"] > after["allocated_bytes"]
    if consumer == "raw":
        assert after["allocations"] == after["allocated_bytes"] == 0
