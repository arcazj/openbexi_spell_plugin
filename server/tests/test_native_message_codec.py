"""Wire compatibility, malformed input and actual allocation regressions.

The frozen message class/implementation and its original tokenizeData helper
are compiled, with only unrelated Python/logging includes replaced by fixtures.
Hosted whole-native recovery remains a separate mandatory acceptance.
"""

import importlib.util
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import zipfile

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "codec_builder", ROOT / "host_runtime/build_admission_context.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope="session")
def codec_binaries(tmp_path_factory, request):
    folder = tmp_path_factory.mktemp("native-message-codec")
    builds = NativeBuildBatch(folder, request)
    # Immutable pre-correction encoder: exact dev76 source, independent of the candidate.
    assert (
        hashlib.sha256(
            (ROOT / "server/tests/native_bridge_frame_before_dev76.H").read_bytes()
        ).hexdigest()
        == "8c4280f9e626059c26f8903f449e6ba63ba9619e0922d78131cd11de8a886e2a"
    )
    assert (
        hashlib.sha256((ROOT / "server/tests/native_bridge_frame_dev77.H").read_bytes()).hexdigest()
        == "d5f4a57d19e01d3884fd014ecd12ac50b1328641777b74da1dbfbf19d72d2660"
    )
    frozen_input = (ROOT / "server/tests/native_bridge_input_before_dev80.inc").read_bytes()
    assert hashlib.sha256(frozen_input).hexdigest() == (
        "79023bdf1f2d8eff324573c74975479723e5e7ae6346d27ba112f87db638c13b"
    )
    private_bridge = (ROOT / "host_runtime/native/private_bridge.cpp").read_text()
    input_start = private_bridge.index("                // The request owns these fields")
    input_end = private_bridge.index('                if (request.at("operation")', input_start)
    (folder / "bridge_input.inc").write_text(
        "static void bridgeInputBefore(SPELLipcMessage& message,const Json& request) {\n"
        + frozen_input.decode()
        + "}\nstatic void bridgeInputAfter(SPELLipcMessage& message,const Json& request) {\n"
        + private_bridge[input_start:input_end]
        + "}\n"
    )
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
        ("dev77", builder.replace_native_message_codec(original)),
        ("after", builder.replace_native_message_codec(original)),
    ):
        output_text = output if name == "before" else builder.transfer_native_output(output)
        methods = []
        signatures = ["void SPELLipcOutput::send(", "void SPELLipcOutput::writeData("]
        if name != "before":
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
        if name == "after":
            header = builder.borrow_native_bridge_headers(header)
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
            + str(
                ROOT
                / (
                    "server/tests/native_bridge_frame_before_dev76.H"
                    if name == "before"
                    else "server/tests/native_bridge_frame_dev77.H"
                    if name == "dev77"
                    else "host_runtime/native/bridge_frame.H"
                )
            )
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
        builds.add(
            [
                "c++",
                "-std=c++17",
                "-O1",
                "-DV08_CODEC_REUSE=" + ("0" if name == "before" else "1"),
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
            text=True,
            timeout=60,
        )
        binaries[name] = binary
    builds.run()
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


def test_mixed_bridge_schemas_reuse_owned_nodes_without_stale_fields(codec_binaries, tmp_path):
    before = run(codec_binaries["before"], "alloc_mixed_frames")
    after = run(codec_binaries["after"], "alloc_mixed_frames")
    assert before["digest"] == after["digest"]
    assert before["allocations"] >= 100000
    assert after["allocated_bytes"] == after["allocations"] == 0
    (tmp_path / "mixed-bridge-measurement.json").write_text(
        json.dumps({"before": before, "after": after}, indent=2) + "\n"
    )


def test_retired_bridge_nodes_preserve_large_and_excess_fields(codec_binaries):
    before = run(codec_binaries["before"], "bridge_retired_boundaries")
    after = run(codec_binaries["after"], "bridge_retired_boundaries")
    assert before["digest"] == after["digest"]


@pytest.mark.parametrize(
    "mode,allocations,byte_count",
    [
        ("alloc_native_id_frames", 10000, 170000),
        ("alloc_long_header_frames", 60000, 1980000),
    ],
)
def test_native_bridge_copies_long_headers_once_into_owned_encoder_storage(
    codec_binaries, tmp_path, mode, allocations, byte_count
):
    before = run(codec_binaries["dev77"], mode)
    after = run(codec_binaries["after"], mode)
    assert before["digest"] == after["digest"]
    assert before["allocations"] == allocations
    assert before["allocated_bytes"] == byte_count
    assert after["allocations"] == after["allocated_bytes"] == 0
    (tmp_path / (mode + ".json")).write_text(
        json.dumps({"dev77": before, "candidate": after}, indent=2) + "\n"
    )


def test_bridge_header_borrow_does_not_alias_mutated_or_destroyed_message(codec_binaries):
    assert run(codec_binaries["dev77"], "bridge_header_ownership") == run(
        codec_binaries["after"], "bridge_header_ownership"
    )


def test_bridge_header_adapter_rejects_drift_and_reapplication():
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("include/SPELL_IPC/SPELLipcMessage.H").decode()
    for text in (
        original.replace("return m_senderId;", "return m_receiverId;"),
        builder.borrow_native_bridge_headers(original),
    ):
        with pytest.raises(ValueError, match="boundary differs"):
            builder.borrow_native_bridge_headers(text)


def test_bridge_input_borrow_preserves_native_wire_errors_and_request_ownership(codec_binaries):
    result = run(codec_binaries["after"], "bridge_input_ownership")
    assert result["cases"] == 12
    assert result["input_unchanged"] is True
    assert result["owned_after_request_destruction"] is True


@pytest.mark.parametrize("case", ["short", "long", "absent"])
def test_bridge_input_borrow_removes_subtree_copy_allocations(codec_binaries, tmp_path, case):
    before = run(codec_binaries["after"], "alloc_bridge_input_" + case + "_copy")
    after = run(codec_binaries["after"], "alloc_bridge_input_" + case + "_borrow")
    assert before["digest"] == after["digest"]
    assert before["allocations"] - after["allocations"] >= 10000
    assert before["allocated_bytes"] - after["allocated_bytes"] >= 480000
    (tmp_path / (case + "-bridge-input-allocations.json")).write_text(
        json.dumps({"before": before, "after": after, "iterations": 10000}, indent=2) + "\n"
    )
