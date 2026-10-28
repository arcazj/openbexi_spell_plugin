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
        output = archive.read("lib/SPELL_IPC/src/SPELLipcOutput.C").decode()
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
struct SPELLipcError:std::runtime_error {
    SPELLipcError(const std::string& s,int=0):std::runtime_error(s){}
    std::string getError() const {return what();}
};
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
        output_text = output if name == "before" else builder.transfer_native_output(output)
        methods = []
        signatures = ["void SPELLipcOutput::send(", "void SPELLipcOutput::writeData("]
        if name == "after":
            signatures.append("void SPELLipcOutput::v08WriteData(")
        for signature in signatures:
            begin = output_text.index(signature)
            end_method = output_text.index("\n}", begin) + 2
            methods.append(output_text[begin:end_method])
        (folder / "output_methods.inc").write_text("\n".join(methods))
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
        # Frozen encoder is an independent wire oracle for the cached encoder.
        bridge = (ROOT / "host_runtime/native_bridge.cpp").read_text()
        start = bridge.index("Json encode(const SPELLipcMessage& message) {")
        end = bridge.index("\n}", start) + 2
        wrappers = """
Json encodeEvent(const char* event, const SPELLipcMessage& message) {
    return {{"event",event},{"message",encode(message)}};
}
Json encodeReply(unsigned sequence, const SPELLipcMessage& reply) {
    return {{"seq",sequence},{"ok",reply.getType()!=MSG_TYPE_ERROR},{"message",encode(reply)}};
}
"""
        (folder / "bridge_encode.inc").write_text(
            "#include <nlohmann/json.hpp>\n#include <algorithm>\nusing Json=nlohmann::json;\n"
            + "static const char* fieldNames[]={"
            + ",".join(json.dumps(field) for field in sorted(fields))
            + "};\n"
            + bridge[start:end]
            + wrappers
            + '\n#include "'
            + str(ROOT / "host_runtime/native/bridge_frame.H")
            + '"\n'
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
                "-DV08_CODEC_REUSE=" + ("1" if name == "after" else "0"),
                "-g",
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer",
                "-no-pie",
                "-I" + str(folder),
                str(path),
                str(folder / "utils.cpp"),
                str(ROOT / "server/tests/native_message_harness.cpp"),
                "-lz",
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


@pytest.mark.parametrize(
    "case", ["wire", "duplicates", "partial_metadata", "moves", "output", "request_ids"]
)
def test_native_codec_preserves_original_wire_and_decoding(codec_binaries, case):
    assert run(codec_binaries["before"], case) == run(codec_binaries["after"], case)


@pytest.mark.parametrize("case", ["malformed", "oversize_key"])
def test_native_codec_rejects_unrepresentable_and_truncated_fields(codec_binaries, case):
    run(codec_binaries["after"], case)


@pytest.mark.parametrize(
    "case,ratio",
    [("alloc_parse", 0.55), ("alloc_data", 0.35), ("alloc_output", 0.25)],
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


def test_native_request_id_retains_one_owned_result_with_fewer_allocations(codec_binaries):
    before = run(codec_binaries["before"], "alloc_request_ids")
    after = run(codec_binaries["after"], "alloc_request_ids")
    assert before["allocations"] >= 40000
    assert after["allocations"] == 10000
    assert after["allocated_bytes"] < before["allocated_bytes"] / 2


def test_request_id_into_owned_processor_storage_avoids_the_measured_temporary(
    codec_binaries, tmp_path
):
    # The public owned-return path remains available and independently owned.
    returned = run(codec_binaries["after"], "alloc_request_ids")
    owned = run(codec_binaries["after"], "alloc_owned_request_ids")
    assert returned["allocations"] == 10000
    assert owned["allocations"] == owned["allocated_bytes"] == 0
    original = run(codec_binaries["before"], "alloc_owned_request_ids")
    assert original["digest"] == owned["digest"]
    (tmp_path / "request-id-measurement.json").write_text(
        json.dumps(
            {
                "public_owned_return": returned,
                "processor_owned_render": owned,
                "frozen_original": original,
            },
            indent=2,
        )
    )


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


def test_cached_bridge_frames_match_frozen_bytes_and_clear_stale_fields(codec_binaries):
    run(codec_binaries["after"], "cached_frames")


def test_cached_bridge_removes_measured_repeated_frame_allocations(codec_binaries):
    before = run(codec_binaries["before"], "alloc_frame")
    after = run(codec_binaries["after"], "alloc_cached_frame")
    assert after["allocated_bytes"] < before["allocated_bytes"] * 0.05
    assert after["allocations"] < before["allocations"] * 0.05


def test_native_output_transfer_rejects_changed_or_repeated_source():
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("lib/SPELL_IPC/src/SPELLipcOutput.C").decode()
    for text in (original + "\n", builder.transfer_native_output(original)):
        with pytest.raises(ValueError, match="preimage"):
            builder.transfer_native_output(text)


def test_reused_input_matches_fresh_messages_and_clears_metadata(codec_binaries):
    assert run(codec_binaries["before"], "input_reuse") == run(
        codec_binaries["after"], "input_reuse"
    )


def test_reused_input_retains_no_malformed_packet_or_oversized_field_state(codec_binaries):
    run(codec_binaries["after"], "input_malformed")


def test_reused_input_removes_repeated_decode_allocations(codec_binaries):
    before = run(codec_binaries["before"], "alloc_input")
    after = run(codec_binaries["after"], "alloc_input")
    assert after["allocated_bytes"] < before["allocated_bytes"] * 0.05
    assert after["allocations"] < before["allocations"] * 0.05


def test_alternating_input_layouts_reuse_owned_nodes(codec_binaries):
    before = run(codec_binaries["before"], "alloc_mixed_input")
    after = run(codec_binaries["after"], "alloc_mixed_input")
    assert before["allocations"] >= 200_000
    assert after["allocated_bytes"] == after["allocations"] == 0
