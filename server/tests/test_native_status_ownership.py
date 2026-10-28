"""Real native STATUS/CSP ownership and sequence regression components."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIGNATURES = (
    "void SPELLserverCif::completeMessage(",
    "void SPELLserverCif::prepareMessage(",
    "void SPELLserverCif::specificNotifyStatus(",
    "SPELLipcMessage SPELLserverCif::getPingMessage()",
)


def method(text, signature):
    start = text.index("\n" + signature) + 1
    return text[start : text.index("\n}", start) + 2]


@pytest.fixture(scope="module")
def status_sources(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-status-source")
    tree = folder / "native"
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as original:
        original.extractall(tree)
    saved = sys.path[:]
    sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
    try:
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(tree)
        apply_native_tree(tree, archive, folder / "composition")
        contract = method((tree / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text(), SIGNATURES[0])
        spec = importlib.util.spec_from_file_location(
            "status_builder", ROOT / "host_runtime/build_admission_context.py"
        )
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        original_patch = builder.own_native_status_snapshots
        before = folder / "before"

        def capture(source):
            for name in (
                "lib/SPELL_CIFS/src/SPELLserverCif.C",
                "include/SPELL_CIFS/SPELLserverCif.H",
            ):
                path = before / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((source / name).read_bytes())
            original_patch(source)

        builder.own_native_status_snapshots = capture
        builder.patch_native_tree(tree, prompts=True, terminal=True)
        builder.own_native_status_snapshots = original_patch
    finally:
        sys.path[:] = saved
    original_cif = before / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    assert (
        hashlib.sha256(original_cif.read_bytes()).hexdigest()
        == "81c949f5bcf729e52879437aad3ec2d77dd1d9a8595235fa09c16416180034ed"
    )
    return folder, tree, before, contract, builder


@pytest.fixture(scope="module")
def status_binaries(status_sources):
    folder, tree, before, contract, _ = status_sources
    binaries = {}
    for profile in ("before", "candidate", "contract"):
        out = folder / (profile + "-build")
        for name in ("SPELL_IPC", "SPELL_UTIL"):
            (out / name).mkdir(parents=True)
        for name in (
            "SPELLipc.H",
            "SPELLipc_Executor.H",
            "SPELLipc_Context.H",
            "SPELLipcMessage.H",
        ):
            shutil.copyfile(tree / "include/SPELL_IPC" / name, out / "SPELL_IPC" / name)
        (out / "SPELL_UTIL/SPELLbase.H").write_text("""#pragma once
#include <string>
#include <vector>
#include <map>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
using BYTE=unsigned char;
struct SPELLipcError:std::runtime_error {SPELLipcError(const std::string& s,int=0):std::runtime_error(s){};std::string getError()const{return what();}};
""")
        (out / "SPELL_UTIL/SPELLlog.H").write_text("#pragma once\n")
        (out / "SPELL_IPC/SPELLipcError.H").write_text('#include "SPELL_UTIL/SPELLbase.H"\n')
        (out / "SPELL_UTIL/SPELLutils.H").write_text("""#pragma once
#include "SPELL_UTIL/SPELLbase.H"
#include <atomic>
#include <thread>
inline std::atomic<bool> reserve_barrier{false};
inline std::atomic<unsigned> reservations{0};
struct SPELLutils {
static long strtoi(const std::string& s){return s.empty()?-1:std::atoi(s.c_str());}
static std::string itostr(long value){
 if(reserve_barrier.load()){const unsigned n=reservations.fetch_add(1);while(reservations.load()<(n/2+1)*2)std::this_thread::yield();}
 return std::to_string(value);
}
static void timestamp(std::string& out){out="2026-10-28T00:00:00";}
static std::string timestamp(){return "2026-10-28T00:00:00";}
};
#define ISTR(x) SPELLutils::itostr(x)
#define STRI(x) SPELLutils::strtoi(x)
""")
        selected = tree if profile == "candidate" else before
        text = (selected / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
        methods = [method(text, signature) for signature in SIGNATURES]
        if profile == "contract":
            methods[0] = contract
        if profile == "candidate":
            methods += [
                method(text, signature)
                for signature in (
                    "SPELLipcMessage SPELLserverCif::v08StatusSnapshot()",
                    "void SPELLserverCif::v08PublishStatusSnapshot(",
                )
            ]
        (out / "status_methods.inc").write_text("\n".join(methods) + "\n")
        header = (selected / "include/SPELL_CIFS/SPELLserverCif.H").read_text()
        first = header.index("SPELLipcMessage m_stMessage;")
        last = header.index("/** Processes incoming", first)
        declarations = header[first:last]
        for name in ("m_sequence", "m_sequenceStack"):
            found = re.findall(
                r"(?:std::atomic<unsigned long>|unsigned long) " + name + ";", header
            )
            assert len(found) == 1
            declarations += found[0] + "\n"
        (out / "status_members.inc").write_text(declarations)
        message = (
            (tree / "lib/SPELL_IPC/src/SPELLipcMessage.C")
            .read_text()
            .replace("/candidate/", str(ROOT / "host_runtime/native") + "/")
        )
        (out / "message.cpp").write_text(message)
        sanitizers = ("asan", "tsan") if profile != "contract" else ("asan",)
        for sanitizer in sanitizers:
            binary = out / sanitizer
            command = [
                "c++",
                "-std=c++17",
                "-O1",
                "-g",
                "-pthread",
                "-fno-omit-frame-pointer",
                "-fno-sanitize-recover=all",
                "-fsanitize=" + ("address,undefined" if sanitizer == "asan" else "thread"),
                "-no-pie",
                "-I" + str(out),
                "-I" + str(ROOT / "host_runtime/native"),
                "-DV08_STATUS_CANDIDATE=" + str(int(profile == "candidate")),
                str(out / "message.cpp"),
                str(ROOT / "server/tests/native_status_ownership.cpp"),
                "-lz",
                "-o",
                str(binary),
            ]
            built = subprocess.run(command, capture_output=True, timeout=60)
            (out / (sanitizer + "-build.stderr")).write_bytes(built.stderr)
            assert built.returncode == 0, built.stderr.decode()
            binaries[profile, sanitizer] = binary
    return binaries


def execute(binaries, profile, sanitizer, mode):
    binary = binaries[profile, sanitizer]
    result = subprocess.run([str(binary), mode], capture_output=True, timeout=30)
    (binary.parent / (sanitizer + "-" + mode + ".stdout")).write_bytes(result.stdout)
    (binary.parent / (sanitizer + "-" + mode + ".stderr")).write_bytes(result.stderr)
    return result


@pytest.mark.parametrize("mode", ["sequence", "stack-sequence"])
def test_actual_methods_reserve_distinct_sequences_under_forced_interleaving(status_binaries, mode):
    before = execute(status_binaries, "before", "asan", mode)
    after = execute(status_binaries, "candidate", "asan", mode)
    assert before.returncode == 5 and json.loads(before.stdout)["duplicate"]
    assert after.returncode == 0 and not after.stderr
    observed = json.loads(after.stdout)
    assert {observed["left"], observed["right"]} == {"0", "1"}
    assert observed["counter"] == 2


def test_actual_getref_semantics_require_an_owned_stack_field(status_binaries):
    before = execute(status_binaries, "before", "asan", "stack")
    after = execute(status_binaries, "candidate", "asan", "stack")
    assert before.returncode == after.returncode == 0
    assert json.loads(before.stdout) == {"field_present": False, "stack": ""}
    assert json.loads(after.stdout) == {"field_present": True, "stack": "procedure#0:1/0"}


def test_sequential_ping_and_acknowledged_status_match_original_native_wire_contract(
    status_binaries,
):
    expected = execute(status_binaries, "contract", "asan", "wire")
    after = execute(status_binaries, "candidate", "asan", "wire")
    assert expected.returncode == after.returncode == 0
    assert not expected.stderr and not after.stderr
    assert expected.stdout == after.stdout and len(after.stdout.splitlines()) == 5


def test_status_snapshot_mutex_is_released_before_stack_and_send_callbacks(status_binaries):
    result = execute(status_binaries, "candidate", "asan", "callbacks")
    assert result.returncode == 0 and not result.stderr


def test_actual_source_thread_sanitizer_reproduces_and_eliminates_status_races(status_binaries):
    before = execute(status_binaries, "before", "tsan", "template")
    assert before.returncode == 66 and b"ThreadSanitizer: data race" in before.stderr
    assert (
        b"SPELLserverCif::getPingMessage" in before.stderr
        and b"SPELLserverCif::specificNotifyStatus" in before.stderr
    )
    after = execute(status_binaries, "candidate", "tsan", "template")
    assert after.returncode == 0 and not after.stderr
    assert json.loads(after.stdout)["notifications"] == 20000


@pytest.mark.parametrize("bad", ["method", "header", "reapplied"])
def test_ownership_patch_refuses_drift_before_any_write(status_sources, tmp_path, bad):
    _, _, before, _, builder = status_sources
    source = tmp_path / "source"
    shutil.copytree(before, source)
    paths = [
        source / "lib/SPELL_CIFS/src/SPELLserverCif.C",
        source / "include/SPELL_CIFS/SPELLserverCif.H",
    ]
    if bad == "method":
        paths[0].write_text(paths[0].read_text().replace("m_sequence++;", "m_sequence += 1;"))
    elif bad == "header":
        paths[1].write_text(
            paths[1]
            .read_text()
            .replace("unsigned long m_sequence;", "unsigned long changed_sequence;")
        )
    else:
        builder.own_native_status_snapshots(source)
    originals = [path.read_bytes() for path in paths]
    with pytest.raises(ValueError, match="Native status ownership"):
        builder.own_native_status_snapshots(source)
    assert originals == [path.read_bytes() for path in paths]
