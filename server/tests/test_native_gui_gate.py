"""Measure exact GUI JSON construction with real native messages and transport."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "8350123cec0e7b0af4c5727d64398c5478422503"
BASELINE_SHA256 = "2147c18a4997889d7fa3d319380e1ae0b309248cbebea2aa2c42163df5eb8764"


@pytest.fixture(scope="session")
def gui_binaries(tmp_path_factory, request):
    serialization_only = getattr(request, "param", "transport") == "serialization"
    folder = tmp_path_factory.mktemp("native-gui-gate")
    builds = NativeBuildBatch(folder, request)
    baseline = (ROOT / "server/tests/native_gui_gate_before_dev82.H").read_bytes()
    assert hashlib.sha256(baseline).hexdigest() == BASELINE_SHA256
    include = Path("/usr/include")
    if not (include / "nlohmann/json.hpp").is_file():
        import nlohmann_json

        include = Path(nlohmann_json.get_include())
    spec = importlib.util.spec_from_file_location(
        "gui_message_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("lib/SPELL_IPC/src/SPELLipcMessage.C").decode()
        header = archive.read("include/SPELL_IPC/SPELLipcMessage.H").decode()
        ipc = archive.read("include/SPELL_IPC/SPELLipc.H").decode()
        utils = archive.read("lib/SPELL_UTIL/src/SPELLutils.C").decode()
    (folder / "SPELL_IPC").mkdir()
    (folder / "SPELL_UTIL").mkdir()
    (folder / "SPELL_IPC/SPELLipc.H").write_text(ipc)
    (folder / "SPELL_UTIL/SPELLbase.H").write_text("""#pragma once
#include <string>
#include <vector>
#include <map>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
using BYTE=unsigned char;
struct SPELLipcError:std::runtime_error {
    SPELLipcError(const std::string& s,int=0):std::runtime_error(s){}
};
""")
    (folder / "SPELL_UTIL/SPELLlog.H").write_text("#pragma once\n")
    (folder / "SPELL_IPC/SPELLipcError.H").write_text('#include "SPELL_UTIL/SPELLbase.H"\n')
    (folder / "SPELL_UTIL/SPELLutils.H").write_text("""#pragma once
#include "SPELL_UTIL/SPELLbase.H"
struct SPELLutils {
static std::map<std::string,std::vector<BYTE>> tokenizeData(const std::string&);
static std::string itostr(long n){return std::to_string(n);}
static long strtoi(const std::string& s){return s.empty()?-1:std::atoi(s.c_str());}
};
#define ISTR(x) SPELLutils::itostr(x)
#define STRI(x) SPELLutils::strtoi(x)
""")
    start = utils.index("std::map<std::string, std::vector<BYTE> > SPELLutils::tokenizeData(")
    end = utils.index("\n}", start) + 2
    (folder / "utils.cpp").write_text('#include "SPELL_UTIL/SPELLutils.H"\n' + utils[start:end])
    header = builder.enable_native_message_moves(header).replace(
        "bool hasField( std::string field ) const;",
        "bool hasField( std::string field ) const;\n"
        "const Properties& v08Fields() const { return m_properties; }",
    )
    (folder / "SPELL_IPC/SPELLipcMessage.H").write_text(header)
    message = builder.replace_native_message_codec(original)
    for file in ("message_codec.H", "allocation_trace.H"):
        message = message.replace("/candidate/" + file, str(ROOT / "host_runtime/native" / file))
    (folder / "message.cpp").write_text(message)
    binaries = {}
    for name in ("before", "after"):
        headers = folder / name
        headers.mkdir()
        (headers / "gui_gate.H").write_bytes(
            baseline if name == "before" else (ROOT / "host_runtime/native/gui_gate.H").read_bytes()
        )
        (headers / "admission_ipc.H").write_bytes(
            (ROOT / "host_runtime/native/admission_ipc.H").read_bytes()
        )
        if serialization_only:
            (headers / "admission_channel.H").write_text(
                "#define v08_admission_exchange v08_original_admission_exchange\n"
                '#include "' + str(ROOT / "host_runtime/native/admission_channel.H") + '"\n'
                "#undef v08_admission_exchange\n"
                "static inline void v08_admission_exchange(const char*, const std::string&, const std::string&);\n"
            )
        binary = folder / (name + "-gui-gate")
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
                "-DV08_OWNED_BODY",
                *(["-DV08_GUI_EXCHANGE_COMPONENT"] if serialization_only else []),
                "-I" + str(headers),
                "-I" + str(folder),
                "-I" + str(ROOT / "host_runtime/native"),
                "-I" + str(ROOT / "server/tests"),
                "-I" + str(include),
                str(folder / "message.cpp"),
                str(folder / "utils.cpp"),
                str(ROOT / "server/tests/native_gui_gate.cpp"),
                "-o",
                str(binary),
            ],
            timeout=90,
        )
        binaries[name] = binary
    builds.run()
    names = [
        "host_runtime/native/gui_gate.H",
        "host_runtime/native/admission_ipc.H",
        "host_runtime/native/admission_channel.H",
        "server/tests/native_gui_gate.cpp",
        "server/tests/native_gui_gate_before_dev82.H",
        "server/tests/test_native_gui_gate.py",
        "host_runtime/build_admission_context.py",
        "docs/reference/SPELL2.6.10-src.zip",
    ]
    linked = subprocess.check_output(["ldd", str(binaries["after"])], text=True)
    sanitizer_libraries = {
        name: {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        for name, path in re.findall(
            r"^\s*(libasan\.so\.\d+|libubsan\.so\.\d+) => (/\S+) ", linked, re.M
        )
    }
    assert len(sanitizer_libraries) == 2
    (folder / "inputs.json").write_text(
        json.dumps(
            {
                "component_only": True,
                "baseline": BASELINE,
                "actual_message_codec_and_gui_function_compiled": True,
                "physical_unix_transport_requested": not serialization_only,
                "explicit_exchange_test_sink": serialization_only,
                "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[
                    0
                ],
                "sanitizer_libraries": sanitizer_libraries,
                "utility_dependency_stubs_same_as_existing_message_storage_component": True,
                "source_sha256": {
                    n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names
                },
                "json_header_sha256": hashlib.sha256(
                    (include / "nlohmann/json.hpp").read_bytes()
                ).hexdigest(),
                "json_include_sha256": {
                    p.relative_to(include).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((include / "nlohmann").rglob("*.hpp"))
                },
                "binary_sha256": {
                    n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in binaries.items()
                },
            },
            indent=2,
        )
        + "\n"
    )
    return binaries


def invoke(binary, mode, output):
    with tempfile.TemporaryDirectory(prefix="gui-gate-") as short:
        result = subprocess.run(
            [str(binary), mode, str(output / "epoch"), str(Path(short) / "agent.sock")],
            capture_output=True,
            timeout=60,
            env=dict(
                os.environ,
                ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
                UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
            ),
        )
    (output / (binary.name + "-" + mode + ".stdout")).write_bytes(result.stdout)
    (output / (binary.name + "-" + mode + ".stderr")).write_bytes(result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode == "failures":
        lines = result.stderr.splitlines()
        assert len(lines) == 2 and all(line.startswith(b"V08_ADMISSION ") for line in lines)
    else:
        assert not result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("shape", [0, 1, 2, 3])
def test_gui_constructor_reduces_measured_allocations_without_changing_wire(
    gui_binaries, tmp_path, shape
):
    results = {n: invoke(p, str(shape), tmp_path) for n, p in gui_binaries.items()}
    before, after = results["before"], results["after"]
    for key in (
        "requests",
        "shape",
        "wire_fnv1a64",
        "wire_bytes",
        "independent_wire_oracle",
        "caller_message_unchanged",
        "fresh_epoch_rotation",
    ):
        assert before[key] == after[key]
    assert before["requests"] == 10000
    assert 0 < after["caller_allocations"] < before["caller_allocations"]
    assert 0 < after["caller_allocated_bytes"] < before["caller_allocated_bytes"]
    (tmp_path / "measurements.json").write_text(json.dumps(results, indent=2) + "\n")


@pytest.mark.parametrize("mode", ["failures", "concurrency"])
def test_gui_const_message_and_failure_authority_preserved(gui_binaries, tmp_path, mode):
    before = invoke(gui_binaries["before"], mode, tmp_path)
    after = invoke(gui_binaries["after"], mode, tmp_path)
    assert before == after


@pytest.mark.parametrize("gui_binaries", ["serialization"], indirect=True)
@pytest.mark.parametrize("shape", [0, 1, 2, 3])
def test_gui_serialization_component_exact_bytes_and_measured_copy_cost(
    gui_binaries, tmp_path, shape
):
    results = {n: invoke(p, "component-" + str(shape), tmp_path) for n, p in gui_binaries.items()}
    before, after = results["before"], results["after"]
    for key in (
        "requests",
        "shape",
        "wire_fnv1a64",
        "wire_bytes",
        "independent_wire_oracle",
        "caller_message_unchanged",
        "fresh_epoch_rotation",
        "physical_unix_transport_executed",
    ):
        assert before[key] == after[key]
    assert before["requests"] == 10000
    assert before["physical_unix_transport_executed"] is False
    assert 0 < after["caller_allocations"] < before["caller_allocations"]
    assert 0 < after["caller_allocated_bytes"] < before["caller_allocated_bytes"]
    (tmp_path / "measurements.json").write_text(json.dumps(results, indent=2) + "\n")


@pytest.mark.parametrize("gui_binaries", ["serialization"], indirect=True)
def test_gui_serialization_component_failure_ownership(gui_binaries, tmp_path):
    before = invoke(gui_binaries["before"], "component-failures", tmp_path)
    after = invoke(gui_binaries["after"], "component-failures", tmp_path)
    assert before == after
