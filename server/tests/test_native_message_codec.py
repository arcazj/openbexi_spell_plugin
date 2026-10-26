"""Wire compatibility, malformed input and actual allocation regressions.

The frozen message class/implementation and its original tokenizeData helper
are compiled, with only unrelated Python/logging includes replaced by fixtures.
Hosted whole-native recovery remains a separate mandatory acceptance.
"""

import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "codec_builder", ROOT / "host_runtime/build_admission_context.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope="session")
def codec_binaries(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-message-codec")
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("lib/SPELL_IPC/src/SPELLipcMessage.C").decode()
        for name in ("SPELLipcMessage.H", "SPELLipc.H"):
            text = archive.read("include/SPELL_IPC/" + name).decode()
            if name == "SPELLipcMessage.H":
                text = text.replace(
                    "bool hasField( std::string field ) const;",
                    "bool hasField( std::string field ) const;\nconst Properties& v08Fields() const { return m_properties; }",
                )
            path = folder / "SPELL_IPC" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(text)
        message_header = archive.read("include/SPELL_IPC/SPELLipcMessage.H").decode()
        fields = set()
        for path in archive.namelist():
            if path.startswith("include/SPELL_IPC/") and path.endswith(".H"):
                fields.update(
                    re.findall(r'FIELD_\w+\s*\(\s*"([^"]+)"\s*\)', archive.read(path).decode())
                )
        fields.update({"DefaultProvided", "TimeoutMicroseconds"})
        utils = archive.read("lib/SPELL_UTIL/src/SPELLutils.C").decode()
    (folder / "SPELL_UTIL").mkdir()
    common = """#pragma once
#include <string>
#include <vector>
#include <map>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
using BYTE=unsigned char;
struct SPELLipcError:std::runtime_error { SPELLipcError(const std::string& s,int):std::runtime_error(s){} };
"""
    (folder / "SPELL_UTIL/SPELLbase.H").write_text(common)
    (folder / "SPELL_UTIL/SPELLlog.H").write_text("#pragma once\n")
    (folder / "SPELL_IPC/SPELLipcError.H").write_text('#include "SPELL_UTIL/SPELLbase.H"\n')
    (folder / "SPELL_UTIL/SPELLutils.H").write_text("""#pragma once
#include "SPELL_UTIL/SPELLbase.H"
struct SPELLutils {
static std::map<std::string,std::vector<BYTE>> tokenizeData(const std::string&);
static std::string itostr(long value){return std::to_string(value);}
static long strtoi(const std::string& value){return value.empty()?-1:std::atoi(value.c_str());}
};
#define ISTR(x) SPELLutils::itostr(x)
#define STRI(x) SPELLutils::strtoi(x)
""")
    start = utils.index("std::map<std::string, std::vector<BYTE> > SPELLutils::tokenizeData(")
    end = utils.index("\n}", start) + 2
    (folder / "utils.cpp").write_text('#include "SPELL_UTIL/SPELLutils.H"\n' + utils[start:end])
    binaries = {}
    for name, text in (
        ("before", original),
        ("after", builder.replace_native_message_codec(original)),
    ):
        header = (
            message_header
            if name == "before"
            else builder.enable_native_message_moves(message_header)
        )
        (folder / "SPELL_IPC/SPELLipcMessage.H").write_text(
            header.replace(
                "bool hasField( std::string field ) const;",
                "bool hasField( std::string field ) const;\nconst Properties& v08Fields() const { return m_properties; }",
            )
        )
        bridge_path = (
            "host_runtime/native_bridge.cpp"
            if name == "before"
            else "host_runtime/native/private_bridge.cpp"
        )
        bridge = (ROOT / bridge_path).read_text()
        start = bridge.index("Json encode(const SPELLipcMessage& message) {")
        end = bridge.index("\n}", start) + 2
        (folder / "bridge_encode.inc").write_text(
            "#include <nlohmann/json.hpp>\nusing Json=nlohmann::json;\n"
            + "static const char* fieldNames[]={"
            + ",".join(json.dumps(field) for field in sorted(fields))
            + "};\n"
            + bridge[start:end]
        )
        text = text.replace(
            "/candidate/message_codec.H", str(ROOT / "host_runtime/native/message_codec.H")
        ).replace(
            "/candidate/allocation_trace.H", str(ROOT / "host_runtime/native/allocation_trace.H")
        )
        path = folder / (name + ".cpp")
        path.write_text(text)
        binary = folder / name
        process = subprocess.run(
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
                str(path),
                str(folder / "utils.cpp"),
                str(ROOT / "server/tests/native_message_harness.cpp"),
                "-o",
                str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert process.returncode == 0, process.stderr
        binaries[name] = binary
    return binaries


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


@pytest.mark.parametrize("case", ["wire", "duplicates", "partial_metadata", "moves", "bridge"])
def test_native_codec_preserves_original_wire_and_decoding(codec_binaries, case):
    assert run(codec_binaries["before"], case) == run(codec_binaries["after"], case)


@pytest.mark.parametrize("case", ["malformed", "oversize_key"])
def test_native_codec_rejects_unrepresentable_and_truncated_fields(codec_binaries, case):
    run(codec_binaries["after"], case)


@pytest.mark.parametrize(
    "case,ratio", [("alloc_parse", 0.55), ("alloc_data", 0.35), ("alloc_bridge", 0.60)]
)
def test_native_codec_reduces_measured_allocation_churn(codec_binaries, case, ratio):
    before = run(codec_binaries["before"], case)
    after = run(codec_binaries["after"], case)
    assert before["allocated_bytes"] > 10_000_000
    assert after["allocated_bytes"] < before["allocated_bytes"] * ratio
    assert after["allocations"] < before["allocations"]


def test_native_message_patch_rejects_changed_or_repeated_source():
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("lib/SPELL_IPC/src/SPELLipcMessage.C").decode()
    for text in (original + "\n", builder.replace_native_message_codec(original)):
        with pytest.raises(ValueError, match="preimage"):
            builder.replace_native_message_codec(text)


def test_native_move_transfers_payload_without_allocating(codec_binaries):
    before = run(codec_binaries["before"], "alloc_move")
    after = run(codec_binaries["after"], "alloc_move")
    assert before["allocations"] > 0
    assert after["allocated_bytes"] == after["allocations"] == 0


def test_native_move_patches_reject_drift_and_reapplication():
    port_spec = importlib.util.spec_from_file_location(
        "move_native_port", ROOT / "source_port/native_patches.py"
    )
    port = importlib.util.module_from_spec(port_spec)
    port_spec.loader.exec_module(port)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for path, patcher in (
            ("include/SPELL_IPC/SPELLipcMessage.H", builder.enable_native_message_moves),
            ("lib/SPELL_IPC/src/SPELLipcIncoming.C", builder.transfer_native_incoming),
        ):
            original = port.apply(path, archive.read(path)).decode()
            for text in (original + "\n", patcher(original)):
                with pytest.raises(ValueError, match="preimage"):
                    patcher(text)
