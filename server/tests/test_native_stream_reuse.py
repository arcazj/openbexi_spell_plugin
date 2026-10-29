"""Compile real IPC sources with independent frozen wire and allocation oracles."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest
from native_build_batch import NativeBuildBatch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "stream_builder", ROOT / "host_runtime/build_admission_context.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope="session")
def stream_binaries(tmp_path_factory, request):
    folder = tmp_path_factory.mktemp("native-stream-reuse")
    builds = NativeBuildBatch(folder, request)
    (folder / "SPELL_UTIL").mkdir()
    (folder / "SPELL_IPC").mkdir()
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
    std::string getError() const {return what();}
};
""")
    (folder / "SPELL_UTIL/SPELLlog.H").write_text("#pragma once\n")
    (folder / "SPELL_IPC/SPELLipcError.H").write_text('#include "SPELL_UTIL/SPELLbase.H"\n')
    (folder / "SPELL_UTIL/SPELLutils.H").write_text("""#pragma once
#include "SPELL_UTIL/SPELLbase.H"
struct SPELLutils {
static std::map<std::string,std::vector<BYTE>> tokenizeData(const std::string&);
static std::string itostr(long value){return std::to_string(value);}
static long strtoi(const std::string& s){return s.empty()?-1:std::atoi(s.c_str());}
};
#define ISTR(x) SPELLutils::itostr(x)
#define STRI(x) SPELLutils::strtoi(x)
""")
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        message = archive.read("lib/SPELL_IPC/src/SPELLipcMessage.C").decode()
        output = archive.read("lib/SPELL_IPC/src/SPELLipcOutput.C").decode()
        header = archive.read("include/SPELL_IPC/SPELLipcMessage.H").decode()
        (folder / "SPELL_IPC/SPELLipc.H").write_bytes(archive.read("include/SPELL_IPC/SPELLipc.H"))
        utils = archive.read("lib/SPELL_UTIL/src/SPELLutils.C").decode()
    start = utils.index("std::map<std::string, std::vector<BYTE> > SPELLutils::tokenizeData(")
    end = utils.index("\n}", start) + 2
    (folder / "utils.cpp").write_text('#include "SPELL_UTIL/SPELLutils.H"\n' + utils[start:end])
    result = {}
    for candidate in (False, True):
        name = "candidate" if candidate else "frozen"
        text = builder.replace_native_message_codec(message) if candidate else message
        declaration = builder.enable_native_message_moves(header) if candidate else header
        (folder / "SPELL_IPC/SPELLipcMessage.H").write_text(declaration)
        for include in ("message_codec.H", "allocation_trace.H"):
            text = text.replace(
                "/candidate/" + include, str(ROOT / "host_runtime/native" / include)
            )
        (folder / "message.cpp").write_text(text)
        out = builder.transfer_native_output(output) if candidate else output
        signatures = ["void SPELLipcOutput::send(", "void SPELLipcOutput::writeData("]
        if candidate:
            signatures.append("void SPELLipcOutput::v08WriteData(")
        methods = []
        for signature in signatures:
            first = out.index(signature)
            last = out.index("\n}", first) + 2
            methods.append(out[first:last])
        (folder / "output_methods.inc").write_text("\n".join(methods))
        binary = folder / name
        command = [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-DV08_STREAM_CANDIDATE=" + str(int(candidate)),
            "-I" + str(folder),
            "-I" + str(ROOT / "server/tests"),
            str(folder / "message.cpp"),
            str(folder / "utils.cpp"),
            str(ROOT / "server/tests/native_stream_harness.cpp"),
            "-lz",
            "-o",
            str(binary),
        ]
        builds.add(command, text=True, timeout=60)
        result[name] = binary
    builds.run()
    return result


def execute(binary, mode):
    process = subprocess.run(
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
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


@pytest.mark.parametrize("mode", ["wire", "large-and-failure"])
def test_native_stream_preserves_frames_and_error_behavior(stream_binaries, mode):
    assert execute(stream_binaries["frozen"], mode) == execute(stream_binaries["candidate"], mode)


@pytest.mark.parametrize("mode", ["decode-allocations", "output-allocations"])
def test_native_stream_removes_long_identity_allocation_churn(stream_binaries, mode):
    baseline = execute(stream_binaries["frozen"], mode)
    candidate = execute(stream_binaries["candidate"], mode)
    assert baseline["allocated_bytes"] > 1_000_000
    assert candidate["allocations"] == candidate["allocated_bytes"] == 0


def test_native_borrowed_input_is_owned_after_decode(stream_binaries):
    execute(stream_binaries["candidate"], "malformed")


def test_stream_patch_rejects_header_drift_and_reapplication():
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        header = archive.read("include/SPELL_IPC/SPELLipcOutput.H").decode()
    changed = builder.reuse_native_output_header(header)
    for invalid in (header + "\n", changed):
        with pytest.raises(ValueError, match="preimage"):
            builder.reuse_native_output_header(invalid)


def test_borrowed_callbacks_leave_requests_and_queue_ownership_unchanged(tmp_path):
    names = (
        "include/SPELL_CTX/SPELLexecutorListener.H",
        "include/SPELL_CTX/SPELLexecutor.H",
        "include/SPELL_CTX/SPELLclientNotifier.H",
        "lib/SPELL_CTX/src/SPELLexecutor.C",
        "lib/SPELL_CTX/src/SPELLclientNotifier.C",
    )
    originals = {}
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for name in names:
            originals[name] = archive.read(name).decode()
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(originals[name])
    builder.borrow_native_message_callbacks(tmp_path)
    for name in names:
        expected = originals[name].replace(
            "processMessageFromExecutor( SPELLipcMessage msg )",
            "processMessageFromExecutor( const SPELLipcMessage& msg )",
        )
        assert (tmp_path / name).read_text() == expected
    with pytest.raises(ValueError, match="boundary"):
        builder.borrow_native_message_callbacks(tmp_path)


def test_only_owned_line_notifications_use_the_no_copy_sender(tmp_path):
    names = (
        "include/SPELL_CIFS/SPELLserverCif.H",
        "lib/SPELL_CIFS/src/SPELLserverCif.C",
    )
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for name in names:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    builder.transfer_native_line_notification(tmp_path)
    source = (tmp_path / names[1]).read_text()
    assert source.count("sendGUIMessage(std::move(msg));") == 1
    assert "void SPELLserverCif::sendGUIMessage( const SPELLipcMessage& msg )" in source
    assert "void SPELLserverCif::sendGUIMessage( SPELLipcMessage&& msg )" in source
    with pytest.raises(ValueError, match="boundary"):
        builder.transfer_native_line_notification(tmp_path)


def test_notification_borrow_rejects_changed_body_and_reapplication(tmp_path):
    name = "lib/SPELL_CTX/src/SPELLexecutor.C"
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read(name).decode()
    for text in (
        original.replace("SPELLipcMessage msg(nmsg);", "SPELLipcMessage msg(nmsg); // drift"),
        original,
    ):
        path.write_text(text)
        if text == original:
            builder.borrow_native_executor_notification(tmp_path)
        before = path.read_bytes()
        with pytest.raises(ValueError, match="preimage"):
            builder.borrow_native_executor_notification(tmp_path)
        assert path.read_bytes() == before
