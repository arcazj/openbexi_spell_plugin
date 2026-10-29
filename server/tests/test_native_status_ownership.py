"""Real native STATUS/CSP ownership and sequence regression components."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIGNATURES = (
    "void SPELLserverCif::completeMessage(",
    "void SPELLserverCif::prepareMessage(",
    "void SPELLserverCif::specificNotifyStatus(",
    "SPELLipcMessage SPELLserverCif::getPingMessage()",
)
_COMPONENT_OUTPUT = None
_COMPONENT_TERMINAL = None
_COMPONENT_INDEX = 0


@pytest.fixture(scope="session", autouse=True)
def component_recording(request):
    """Retain each bounded component result before pytest's deferred summary."""
    global _COMPONENT_OUTPUT, _COMPONENT_TERMINAL
    xmlpath = request.config.getoption("xmlpath", default=None)
    if xmlpath:
        _COMPONENT_OUTPUT = Path(xmlpath).with_suffix(".native-components")
        _COMPONENT_OUTPUT.mkdir(parents=True, exist_ok=True)
    _COMPONENT_TERMINAL = request.config.pluginmanager.get_plugin("terminalreporter")


def component_run(command, *, label, binary, timeout, env=None, echo_output=True):
    global _COMPONENT_INDEX
    started = time.monotonic()
    error = None
    result = None
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, env=env)
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        error = exc
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
    except OSError as exc:
        error = exc
        stdout, stderr = b"", str(exc).encode()
    record = {
        "label": label,
        "command": [str(part) for part in command],
        "returncode": result.returncode if result else None,
        "elapsed_seconds": time.monotonic() - started,
        "timeout_seconds": timeout,
        "timed_out": isinstance(error, subprocess.TimeoutExpired),
        "error": str(error) if error else None,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
    if binary.exists():
        stat = binary.stat()
        record["binary"] = {
            "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "size": stat.st_size,
            "mode": oct(stat.st_mode),
            "inode": stat.st_ino,
            "mtime_ns": stat.st_mtime_ns,
        }
    _COMPONENT_INDEX += 1
    if _COMPONENT_OUTPUT:
        prefix = _COMPONENT_OUTPUT / f"{_COMPONENT_INDEX:03d}-{label}"
        prefix.with_suffix(".stdout").write_bytes(stdout)
        prefix.with_suffix(".stderr").write_bytes(stderr)
        prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    if _COMPONENT_TERMINAL:
        # Inputs and outputs are fixed component fixtures; no runtime secrets,
        # credentials, arguments or environment from a deployed process enter.
        displayed = record
        if echo_output:
            displayed = record | {
                "stdout": stdout.decode("utf-8", "backslashreplace"),
                "stderr": stderr.decode("utf-8", "backslashreplace"),
            }
        _COMPONENT_TERMINAL.write_line(
            "native_component_result " + json.dumps(displayed, sort_keys=True)
        )
    if error:
        raise error
    return result


@pytest.fixture(scope="module")
def message_object_cache(tmp_path_factory, component_recording):
    # Every object is built during this module's timed pytest invocation.
    return tmp_path_factory.mktemp("native-message-objects"), {}


def common_message_object(out, group, sanitizer, macro, value, cache, deadline):
    """Reuse only an identical translation unit, flags and dependency bytes."""
    folder, entries = cache
    compiler = Path(shutil.which("c++")).resolve()
    compiler_identity = str(compiler), hashlib.sha256(compiler.read_bytes()).hexdigest()
    inputs = {
        path.relative_to(out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [out / "message.cpp", *sorted(out.glob("SPELL_*/*.H"))]
    }
    canonical = folder / f"{group}-{sanitizer}"
    binary = canonical / "message.o"
    flags = [
        "-std=c++17",
        "-O1",
        "-g",
        "-pthread",
        "-fno-omit-frame-pointer",
        "-fno-sanitize-recover=all",
        "-fsanitize=" + ("address,undefined" if sanitizer == "asan" else "thread"),
        "-no-pie",
        "-I" + str(canonical),
        "-I" + str(ROOT / "host_runtime/native"),
    ]
    identity = dict(compiler=compiler_identity, flags=flags, input_sha256=inputs)
    key = group, sanitizer
    entry = entries.get(key)
    if entry is not None:
        if identity != entry["identity"]:
            raise ValueError("Message object input or compiler flag drift")
        for name, digest in entry["dependencies"].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise ValueError("Message object dependency drift")
        if hashlib.sha256(binary.read_bytes()).hexdigest() != entry["object_sha256"]:
            raise ValueError("Message object byte drift")
    else:
        canonical.mkdir()
        for name in inputs:
            target = canonical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out / name, target)

    # -P removes location directives, but preserves expanded __FILE__ values.
    # Therefore source paths that affect executable tokens also refuse reuse.
    original_flags = ["-I" + str(out) if part == "-I" + str(canonical) else part for part in flags]
    observed = component_run(
        [
            str(compiler),
            *original_flags,
            "-D" + macro + "=" + str(value),
            "-E",
            "-P",
            str(out / "message.cpp"),
        ],
        label=f"message-{group}-{sanitizer}-{out.name}-preprocess",
        binary=binary,
        timeout=max(0, deadline - time.monotonic()),
        echo_output=False,
    )
    assert observed.returncode == 0, observed.stderr.decode()
    preprocessed = hashlib.sha256(observed.stdout).hexdigest()
    if entry is None:
        common = component_run(
            [str(compiler), *flags, "-E", "-P", str(canonical / "message.cpp")],
            label=f"message-{group}-{sanitizer}-common-preprocess",
            binary=binary,
            timeout=max(0, deadline - time.monotonic()),
            echo_output=False,
        )
        assert common.returncode == 0, common.stderr.decode()
        expected = hashlib.sha256(common.stdout).hexdigest()
    else:
        expected = entry["preprocessed_sha256"]
    if preprocessed != expected:
        raise ValueError("Message object preprocessed translation unit drift")

    if entry is None:
        dependencies = canonical / "message.d"
        command = [
            str(compiler),
            *flags,
            "-MD",
            "-MF",
            str(dependencies),
            "-c",
            str(canonical / "message.cpp"),
            "-o",
            str(binary),
        ]
        result = component_run(
            command,
            label=f"message-{group}-{sanitizer}-compile",
            binary=binary,
            timeout=max(0, deadline - time.monotonic()),
        )
        assert result.returncode == 0, result.stderr.decode()
        names = shlex.split(dependencies.read_text().replace("\\\n", "").split(":", 1)[1])
        entry = {
            "identity": identity,
            "compiler_invocation": command,
            "preprocessed_sha256": expected,
            "dependencies": {
                name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in names
            },
            "object_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "uses": [],
        }
        entries[key] = entry
    entry["uses"].append(
        dict(profile=out.name, macro=macro, value=value, preprocessed_sha256=preprocessed)
    )
    receipt = json.dumps(entry, indent=2) + "\n"
    (canonical / "input-identity.json").write_text(receipt)
    if _COMPONENT_OUTPUT:
        (_COMPONENT_OUTPUT / f"message-object-{group}-{sanitizer}.json").write_text(receipt)
    return binary


def method(text, signature):
    start = text.index("\n" + signature) + 1
    return text[start : text.index("\n}", start) + 2]


@pytest.fixture(scope="session")
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
def status_binaries(status_sources, component_recording, message_object_cache):
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
            deadline = time.monotonic() + 60
            message_object = common_message_object(
                out,
                "status",
                sanitizer,
                "V08_STATUS_CANDIDATE",
                int(profile == "candidate"),
                message_object_cache,
                deadline,
            )
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
                str(message_object),
                str(ROOT / "server/tests/native_status_ownership.cpp"),
                "-lz",
                "-o",
                str(binary),
            ]
            built = component_run(
                command,
                label=f"status-{profile}-{sanitizer}-build",
                binary=binary,
                timeout=max(0, deadline - time.monotonic()),
            )
            (out / (sanitizer + "-build.stderr")).write_bytes(built.stderr)
            assert built.returncode == 0, built.stderr.decode()
            binaries[profile, sanitizer] = binary
    return binaries


def execute(binaries, profile, sanitizer, mode, *, halt_first_race=False):
    binary = binaries[profile, sanitizer]
    env = os.environ.copy()
    if halt_first_race:
        # Stop at the demonstrated defect instead of requiring the unsafe
        # baseline to survive thousands of further conflicting mutations.
        env["TSAN_OPTIONS"] = env.get("TSAN_OPTIONS", "") + ":halt_on_error=1:exitcode=66"
    result = component_run(
        [str(binary), mode],
        label=f"status-{profile}-{sanitizer}-{mode}",
        binary=binary,
        timeout=30,
        env=env,
    )
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
    assert {observed["left"], observed["right"]} == (
        {"0", "1"} if mode == "sequence" else {"1", "2"}
    )
    assert observed["counter"] == (2 if mode == "sequence" else 3)
    assert observed["stack_counter"] == (0 if mode == "sequence" else 2)


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
    before = execute(status_binaries, "before", "tsan", "template-proof", halt_first_race=True)
    assert before.returncode == 66 and b"ThreadSanitizer: data race" in before.stderr
    assert (
        b"SPELLserverCif::getPingMessage" in before.stderr
        and b"SPELLserverCif::specificNotifyStatus" in before.stderr
    )
    single = execute(status_binaries, "candidate", "tsan", "template-proof")
    assert single.returncode == 0 and not single.stderr
    assert json.loads(single.stdout)["notifications"] == 1
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


@pytest.fixture(scope="module")
def ack_binaries(status_sources, status_binaries, message_object_cache):
    folder, tree, before_status, _, builder = status_sources
    before = folder / "before-ack"
    shutil.copytree(before_status, before)
    builder.own_native_status_snapshots(before)
    text = (before / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "dcfa7b849d6a3ed5c805e8b5df31981c3c99febec5e652c9c6ff4d5305365d36"
    )
    binaries = {}
    for profile, selected in (("before", before), ("candidate", tree)):
        out = folder / (profile + "-ack-build")
        out.mkdir()
        support = status_binaries["candidate", "asan"].parent
        for name in ("SPELL_IPC", "SPELL_UTIL"):
            shutil.copytree(support / name, out / name)
        shutil.copyfile(support / "message.cpp", out / "message.cpp")
        shutil.copyfile(support / "status_members.inc", out / "status_members.inc")
        (out / "SPELL_UTIL/SPELLutils.H").write_text("""#pragma once
#include "SPELL_UTIL/SPELLbase.H"
struct SPELLutils {
static long strtoi(const std::string&);
static std::string itostr(long);
static void timestamp(std::string& out){out="2026-10-28T00:00:00";}
static std::string timestamp(){return "2026-10-28T00:00:00";}
};
#define ISTR(x) SPELLutils::itostr(x)
#define STRI(x) SPELLutils::strtoi(x)
""")
        utils = (tree / "lib/SPELL_UTIL/src/SPELLutils.C").read_text()
        (out / "native_utils.inc").write_text(
            method(utils, "std::string SPELLutils::itostr(")
            + "\n"
            + method(utils, "long SPELLutils::strtoi(")
            + "\n"
        )
        cif = (selected / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
        signatures = (
            "void SPELLserverCif::completeMessage(",
            "void SPELLserverCif::prepareMessage(",
            "void SPELLserverCif::specificNotifyStatus(",
            "SPELLipcMessage SPELLserverCif::getPingMessage()",
            "SPELLipcMessage SPELLserverCif::v08StatusSnapshot()",
            "void SPELLserverCif::v08PublishStatusSnapshot(",
            "void SPELLserverCif::sendAcknowledged(",
            "bool SPELLserverCif::waitAcknowledge(",
        )
        methods = [method(cif, signature) for signature in signatures]
        start = cif.index("    if (m_ready && msgId == ExecutorMessages::ACKNOWLEDGE)")
        received = cif[start : cif.index("\n    // Reset the IPC", start)]
        methods.append(
            "void SPELLserverCif::receiveAck(const SPELLipcMessage& msg) {\n"
            "    const auto msgId=msg.getId();\n" + received + "\n}\n"
        )
        (out / "ack_methods.inc").write_text("\n".join(methods))
        bridge = (ROOT / "host_runtime/native/private_bridge.cpp").read_text()
        start = bridge.index("    void processMessage(const SPELLipcMessage& message) override {")
        callback = bridge[start : bridge.index("\n    SPELLipcMessage processRequest", start)]
        callback = callback.replace(
            "    void processMessage(const SPELLipcMessage& message) override {",
            "void Peer::processMessage(const SPELLipcMessage& message) {",
        )
        (out / "ack_bridge.inc").write_text(callback)
        (out / "source-bindings.json").write_text(
            json.dumps(
                {
                    "cif_sha256": hashlib.sha256(cif.encode()).hexdigest(),
                    "methods": {
                        signature: hashlib.sha256(body.encode()).hexdigest()
                        for signature, body in zip(signatures, methods)
                    },
                    "ack_branch_sha256": hashlib.sha256(received.encode()).hexdigest(),
                    "private_bridge_sha256": hashlib.sha256(bridge.encode()).hexdigest(),
                    "actual_native_integer_methods": True,
                    "native_acceptance": False,
                },
                indent=2,
            )
        )
        for sanitizer in ("asan", "tsan") if profile == "candidate" else ("asan",):
            binary = out / sanitizer
            deadline = time.monotonic() + 60
            message_object = common_message_object(
                out,
                "ack",
                sanitizer,
                "V08_ACK_CANDIDATE",
                int(profile == "candidate"),
                message_object_cache,
                deadline,
            )
            command = [
                "c++",
                "-std=c++17",
                "-O1",
                "-g",
                "-pthread",
                "-no-pie",
                "-fno-omit-frame-pointer",
                "-fno-sanitize-recover=all",
                "-fsanitize=" + ("address,undefined" if sanitizer == "asan" else "thread"),
                "-I" + str(out),
                "-I" + str(ROOT / "host_runtime/native"),
                "-DV08_ACK_CANDIDATE=" + str(int(profile == "candidate")),
                str(message_object),
                str(ROOT / "server/tests/native_ack_ownership.cpp"),
                "-lz",
                "-o",
                str(binary),
            ]
            result = component_run(
                command,
                label=f"ack-{profile}-{sanitizer}-build",
                binary=binary,
                timeout=max(0, deadline - time.monotonic()),
            )
            (out / (sanitizer + "-build.stderr")).write_bytes(result.stderr)
            assert result.returncode == 0, result.stderr.decode()
            binaries[profile, sanitizer] = binary
    return binaries


def execute_ack(binaries, profile, sanitizer, mode):
    binary = binaries[profile, sanitizer]
    result = component_run(
        [str(binary), mode],
        label=f"ack-{profile}-{sanitizer}-{mode}",
        binary=binary,
        timeout=40,
    )
    (binary.parent / (sanitizer + "-" + mode + ".stdout")).write_bytes(result.stdout)
    (binary.parent / (sanitizer + "-" + mode + ".stderr")).write_bytes(result.stderr)
    return result


def test_actual_native_ping_ack_cannot_settle_a_different_call(ack_binaries):
    before = execute_ack(ack_binaries, "before", "asan", "wrong-domain")
    assert before.returncode == 7 and not before.stderr
    assert json.loads(before.stdout) == {"ping": "0", "call": "0", "wrong_ack_settled": True}
    after = execute_ack(ack_binaries, "candidate", "asan", "wrong-domain")
    assert after.returncode == 0 and not after.stderr
    assert json.loads(after.stdout) == {"ping": "0", "call": "1", "wrong_ack_settled": False}


@pytest.mark.parametrize(
    "mode",
    [
        "synchronous-bridge",
        "out-of-order",
        "cancel-errors",
        "retry-generation",
        "retry-timeout",
        "lifetime",
        "sequence-limit",
    ],
)
def test_live_logical_ack_owners_with_actual_native_methods(ack_binaries, mode):
    result = execute_ack(ack_binaries, "candidate", "asan", mode)
    assert result.returncode == 0 and not result.stderr


@pytest.mark.parametrize("mode", ["out-of-order", "lifetime", "cancel-errors"])
def test_receive_and_unlink_are_thread_sanitizer_clean(ack_binaries, mode):
    result = execute_ack(ack_binaries, "candidate", "tsan", mode)
    assert result.returncode == 0 and not result.stderr


def test_intentional_shared_wire_sequence_change_preserves_other_encoded_bytes(ack_binaries):
    before = execute_ack(ack_binaries, "before", "asan", "wire")
    after = execute_ack(ack_binaries, "candidate", "asan", "wire")
    assert before.returncode == after.returncode == 0 and not before.stderr and not after.stderr
    left = [bytes.fromhex(line.decode()) for line in before.stdout.splitlines()]
    right = [bytes.fromhex(line.decode()) for line in after.stdout.splitlines()]
    assert len(left) == len(right) == 6
    # Sequence values are the only intentional wire change. All exercised
    # values are one decimal byte, so the framing length also stays identical.
    pattern = rb"(\x00\x08Sequence\x00\x00\x00\x01)([0-9])"
    old_values = [re.search(pattern, message).group(2) for message in left]
    new_values = [re.search(pattern, message).group(2) for message in right]
    assert old_values == [b"0", b"0", b"2", b"1", b"2", b"5"]
    assert new_values == [b"0", b"1", b"2", b"3", b"4", b"5"]
    assert [re.sub(pattern, rb"\1TOKEN", message) for message in left] == [
        re.sub(pattern, rb"\1TOKEN", message) for message in right
    ]


@pytest.mark.parametrize("bad", ["method", "header", "ack-branch", "reapplied"])
def test_ack_patch_refuses_source_drift_without_partial_writes(status_sources, tmp_path, bad):
    _, _, before, _, builder = status_sources
    tree = tmp_path / "native"
    shutil.copytree(before, tree)
    builder.own_native_status_snapshots(tree)
    cif = tree / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    header = tree / "include/SPELL_CIFS/SPELLserverCif.H"
    if bad == "method":
        cif.write_text(cif.read_text().replace("m_sequence = 0;", "m_sequence = 1;"))
    elif bad == "header":
        header.write_text(header.read_text().replace("m_ackSequences;", "changed_ackSequences;"))
    elif bad == "ack-branch":
        cif.write_text(
            cif.read_text().replace("m_ackSequences.push_back", "changed_ackSequences.push_back")
        )
    else:
        builder.own_native_acknowledgements(tree)
    saved = cif.read_bytes(), header.read_bytes()
    with pytest.raises(ValueError, match="Native ACK"):
        builder.own_native_acknowledgements(tree)
    assert saved == (cif.read_bytes(), header.read_bytes())


def test_wait_deadline_polling_and_constructor_only_reset_remain_explicit(status_sources):
    _, tree, _, _, _ = status_sources
    cif = (tree / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    assert cif.count("m_sequence = 0;") == 1
    constructor = method(cif, "SPELLserverCif::SPELLserverCif()")
    assert "m_sequence = 0;" in constructor
    wait = method(cif, "bool SPELLserverCif::waitAcknowledge(")
    assert (
        "std::chrono::seconds(static_cast<unsigned long long>(m_timeoutAcknowledgeSec)+1)" in wait
    )
    assert "std::this_thread::sleep_for(std::chrono::milliseconds(20));" in wait
    assert "generation!=m_reconnectGeneration" in wait


def test_message_object_reuse_refuses_input_dependency_flag_and_token_drift(
    status_binaries, message_object_cache, tmp_path
):
    source = status_binaries["before", "asan"].parent

    def reuse(out=source, cache=message_object_cache):
        return common_message_object(
            out,
            "status",
            "asan",
            "V08_STATUS_CANDIDATE",
            0,
            cache,
            time.monotonic() + 60,
        )

    changed = tmp_path / "changed"
    shutil.copytree(source, changed)
    header = changed / "SPELL_UTIL/SPELLutils.H"
    header.write_text(header.read_text() + "\n// changed input identity\n")
    with pytest.raises(ValueError, match="input or compiler flag drift"):
        reuse(changed)

    folder, entries = message_object_cache
    entry = entries["status", "asan"]
    flags = entry["identity"]["flags"]
    entry["identity"]["flags"] = flags + ["-O2"]
    try:
        with pytest.raises(ValueError, match="input or compiler flag drift"):
            reuse()
    finally:
        entry["identity"]["flags"] = flags
    dependency = folder / "status-asan/SPELL_UTIL/SPELLutils.H"
    original = dependency.read_bytes()
    dependency.write_bytes(original + b"\n// changed dependency identity\n")
    try:
        with pytest.raises(ValueError, match="dependency drift"):
            reuse()
    finally:
        dependency.write_bytes(original)

    # Actual preprocessing must reject a test macro that affects this unit.
    header.write_text(
        header.read_text()
        + "\n#ifdef V08_STATUS_CANDIDATE\n"
        + "inline constexpr int component_token=V08_STATUS_CANDIDATE;\n#endif\n"
    )
    fresh = tmp_path / "fresh-cache"
    fresh.mkdir()
    with pytest.raises(ValueError, match="preprocessed translation unit drift"):
        reuse(changed, (fresh, {}))
    assert not list(fresh.rglob("*.o"))
