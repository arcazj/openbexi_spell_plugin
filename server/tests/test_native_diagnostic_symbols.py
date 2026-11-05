"""Faster fixture metadata must retain sanitizer checks and source backtraces."""

import hashlib
import os
from pathlib import Path
import subprocess

import pytest


@pytest.fixture(scope="module")
def diagnostic_binaries(tmp_path_factory):
    directory = tmp_path_factory.mktemp("native-diagnostic-symbols")
    source = directory / "diagnostic.cpp"
    source.write_text(
        "#include <climits>\n"
        "__attribute__((noinline)) int overflow(int count) {\n"
        "    volatile int maximum = INT_MAX;\n"
        "    return maximum + count;\n"
        "}\n"
        "__attribute__((noinline)) int freed_value() {\n"
        "    volatile int* value = new int[8];\n"
        "    value[0] = 23;\n"
        "    delete[] value;\n"
        "    return value[0];\n"
        "}\n"
        "int main(int argc, char**) {\n"
        "    return argc == 2 ? freed_value() : overflow(argc);\n"
        "}\n"
    )
    binaries = {}
    sections = {}
    for level in ("-g2", "-g1"):
        binary = directory / level.removeprefix("-")
        subprocess.run(
            [
                "c++",
                "-std=c++17",
                "-O1",
                level,
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer",
                "-no-pie",
                str(source),
                "-o",
                str(binary),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        sections[level] = {}
        for section in (".text", ".rodata", ".data", ".eh_frame"):
            output = directory / (binary.name + section)
            subprocess.run(
                [
                    "objcopy",
                    "--only-section=" + section,
                    "--output-target=binary",
                    str(binary),
                    str(output),
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
            sections[level][section] = hashlib.sha256(output.read_bytes()).hexdigest()
        binaries[level] = binary
    assert sections["-g1"] == sections["-g2"]
    return binaries


@pytest.mark.parametrize(
    "arguments,diagnostic,function,line",
    [
        (["freed"], "heap-use-after-free", "freed_value", 10),
        ([], "signed integer overflow", "overflow", 4),
    ],
)
def test_minimal_metadata_keeps_instrumentation_and_source_backtraces(
    diagnostic_binaries, arguments, diagnostic, function, line
):
    environment = dict(
        os.environ,
        ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
        UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
    )
    for binary in diagnostic_binaries.values():
        result = subprocess.run(
            [str(binary), *arguments],
            capture_output=True,
            text=True,
            env=environment,
            timeout=10,
        )
        assert result.returncode != 0
        assert diagnostic in result.stderr
        assert function in result.stderr
        assert f"diagnostic.cpp:{line}" in result.stderr
        Path(str(binary) + "." + function + ".stderr").write_text(result.stderr)
