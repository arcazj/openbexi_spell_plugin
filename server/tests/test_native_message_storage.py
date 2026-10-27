"""Compile the real message class: bounded reuse, independent copies and churn."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def storage_binaries(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-message-storage")
    spec = importlib.util.spec_from_file_location(
        "storage_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original = archive.read("lib/SPELL_IPC/src/SPELLipcMessage.C").decode()
        header = archive.read("include/SPELL_IPC/SPELLipcMessage.H").decode()
        ipc = archive.read("include/SPELL_IPC/SPELLipc.H").decode()
        utils = archive.read("lib/SPELL_UTIL/src/SPELLutils.C").decode()
        executor = archive.read("lib/SPELL_CTX/src/SPELLexecutor.C").decode()
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
    binaries = {}
    for name in ("before", "after"):
        native = folder / "lib/SPELL_CTX/src/SPELLexecutor.C"
        native.parent.mkdir(parents=True, exist_ok=True)
        native.write_text(executor)
        if name == "after":
            builder.borrow_native_executor_notification(folder)
        notification = native.read_text()
        start = notification.index("void SPELLexecutor::executorNotification(")
        end = notification.index("\n}", start) + 2
        (folder / "notification_method.inc").write_text(notification[start:end])
        text = original if name == "before" else builder.replace_native_message_codec(original)
        candidate = header if name == "before" else builder.enable_native_message_moves(header)
        candidate = candidate.replace(
            "bool hasField( std::string field ) const;",
            "bool hasField( std::string field ) const;\n"
            "const Properties& v08Fields() const { return m_properties; }",
        )
        (folder / "SPELL_IPC/SPELLipcMessage.H").write_text(candidate)
        for file in ("message_codec.H", "allocation_trace.H"):
            text = text.replace("/candidate/" + file, str(ROOT / "host_runtime/native" / file))
        if name == "after":
            text += """
extern "C" size_t storage_size(){return v08_property_storage.used;}
extern "C" size_t storage_capacity(){
    size_t n=0;for(const auto& m:v08_property_storage.maps)
    for(const auto& f:m)n+=f.first.capacity()+f.second.capacity();return n;
}
extern "C" size_t storage_fields(){
    size_t n=0;for(const auto& m:v08_property_storage.maps)n+=m.size();return n;
}
"""
        source = folder / (name + ".cpp")
        source.write_text(text)
        binary = folder / name
        process = subprocess.run(
            [
                "c++",
                "-std=c++17",
                "-O1",
                "-g",
                "-pthread",
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer",
                "-no-pie",
                "-DV08_STORAGE=" + str(int(name == "after")),
                "-I" + str(folder),
                "-I" + str(ROOT / "server/tests"),
                str(source),
                str(folder / "utils.cpp"),
                str(ROOT / "server/tests/native_storage_harness.cpp"),
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
    environment = dict(os.environ)
    environment["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    result = subprocess.run(
        [str(binary), mode], capture_output=True, text=True, env=environment, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("mode", ["copy", "shapes", "fresh", "threads", "bounds", "notification"])
def test_native_storage_preserves_independence_and_bounds(storage_binaries, mode):
    assert run(storage_binaries["before"], mode) == run(storage_binaries["after"], mode)


def test_native_storage_reduces_real_message_copy_allocations(storage_binaries):
    before = run(storage_binaries["before"], "bench")
    after = run(storage_binaries["after"], "bench")
    assert before["message_size"] == after["message_size"]
    assert before["allocated_bytes"] > 20_000_000
    assert after["allocated_bytes"] < before["allocated_bytes"] * 0.25
    assert after["allocations"] < before["allocations"] * 0.25


@pytest.mark.parametrize("mode", ["mixed_bench", "saturated_bench"])
def test_interleaved_message_shapes_reuse_matching_owned_storage(storage_binaries, mode):
    before = run(storage_binaries["before"], mode)
    after = run(storage_binaries["after"], mode)
    assert before["allocations"] >= 200_000
    assert after["allocations"] == 0
    assert after["allocated_bytes"] == 0


def test_fresh_native_notifications_reuse_exclusive_nodes(storage_binaries):
    before = run(storage_binaries["before"], "fresh_bench")
    after = run(storage_binaries["after"], "fresh_bench")
    assert before["message_size"] == after["message_size"]
    assert before["allocations"] >= 80_000
    assert after["allocations"] == 0
    assert after["allocated_bytes"] == 0


def test_synchronous_notification_avoids_the_redundant_copy(storage_binaries):
    before = run(storage_binaries["before"], "notification_bench")
    after = run(storage_binaries["after"], "notification_bench")
    assert before["allocations"] >= 80_000
    assert after["allocations"] == 0
    assert after["allocated_bytes"] == 0
