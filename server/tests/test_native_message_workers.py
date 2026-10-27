"""Compile real incoming classes and completion guards with instrumented threads.

Transport and synchronization adapters are minimal test doubles; the production
cache, patched incoming header, constructors, run, finish, cancel, start and join
methods are compiled unchanged. Hosted tests own whole-runtime acceptance.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEADER = "include/SPELL_IPC/SPELLipcIncoming.H"
SOURCE = "lib/SPELL_IPC/src/SPELLipcIncoming.C"
TRASH_HEADER = "include/SPELL_IPC/SPELLipcTrash.H"
TRASH_SOURCE = "lib/SPELL_IPC/src/SPELLipcTrash.C"
EXTRA = ["include/SPELL_SYN/SPELLthread.H"] + [
    "lib/SPELL_IPC/src/" + name + ".C"
    for name in (
        "SPELLipcTrash",
        "SPELLipcServerInterfaceSingle",
        "SPELLipcServerInterface",
        "SPELLipcClientInterface",
    )
]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load(ROOT / "host_runtime/build_admission_context.py", "workers_builder")
PORT = load(ROOT / "source_port/native_patches.py", "workers_port")
PROMPT = load(ROOT / "source_port/prompt_control_patches.py", "workers_prompt")


def source(folder):
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for name in (HEADER, SOURCE, TRASH_HEADER, *EXTRA):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            original = archive.read(name)
            ported = PORT.apply(name, original)
            if name in PROMPT.PREIMAGES:
                ported = PROMPT.apply(name, original, ported)
            text = ported.decode()
            if name == SOURCE:
                text = BUILDER.transfer_native_incoming(text)
            path.write_text(text)


@pytest.fixture(scope="session")
def binaries(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-message-workers")
    adapters = (ROOT / "server/tests/native_message_workers_adapters.H").read_text()
    result = {}
    for name in ("before", "after"):
        folder = root / name
        source(folder)
        if name == "after":
            BUILDER.reuse_native_message_instances(folder)
            BUILDER.reuse_native_collector_nodes(folder)
        include = folder / "include"
        for dependency in (
            "SPELL_IPC/SPELLipcChannel.H",
            "SPELL_IPC/SPELLipcInterfaceListener.H",
            "SPELL_SYN/SPELLthread.H",
            "SPELL_SYN/SPELLevent.H",
            "SPELL_SYN/SPELLthreadWork.H",
            "SPELL_IPC/SPELLipcOutput.H",
            "SPELL_IPC/SPELLipcInput.H",
            "SPELL_IPC/SPELLipcError.H",
            "SPELL_IPC/SPELLipcMessage.H",
            "SPELL_UTIL/SPELLlog.H",
            "SPELL_SYN/SPELLmonitor.H",
        ):
            path = include / dependency
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#include "adapters.H"\n')
        (include / "adapters.H").write_text(adapters)
        (include / "SPELL_IPC/SPELLipcInput.H").write_text('#include "SPELL_IPC/SPELLipcTrash.H"\n')
        header = folder / HEADER
        if name == "after":
            text = header.read_text()
            anchor = "class SPELLipcIncomingBase: public SPELLthread\n{"
            assert text.count(anchor) == 1
            header.write_text(text.replace(anchor, anchor + "\n    friend size_t v08TestIdle();"))
        implementation = folder / SOURCE
        implementation.write_text(
            implementation.read_text().replace(
                "/candidate/message_instances.H",
                str(ROOT / "host_runtime/native/message_instances.H"),
            )
        )
        if name == "after":
            implementation.write_text(
                implementation.read_text() + "\n"
                "size_t v08TestIdle() { std::lock_guard<std::mutex> lock(v08_message_instances.mutex); "
                "for(size_t i=0;i<v08_message_instances.used;++i) { "
                "if(!v08_message_instances.idle[i]->getMessage().isVoid() || "
                "v08_message_instances.idle[i]->getKey()!=0) std::abort(); } "
                "return v08_message_instances.used; }\n"
            )
        trash_header = folder / TRASH_HEADER
        trash_header.write_text(
            trash_header.read_text().replace(
                "std::list<SPELLipcIncomingBase*>",
                "std::list<SPELLipcIncomingBase*, V08TestAllocator<SPELLipcIncomingBase*>>",
            )
        )
        binary = folder / "probe"
        compiled = subprocess.run(
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
                "-DV08_WORKERS=" + str(int(name == "after")),
                "-I" + str(include),
                str(folder / SOURCE),
                str(folder / TRASH_SOURCE),
                str(ROOT / "server/tests/native_message_workers.cpp"),
                "-o",
                str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert compiled.returncode == 0, compiled.stderr
        result[name] = binary
    return result


def run(binary, mode):
    p = subprocess.run(
        [str(binary), mode],
        capture_output=True,
        text=True,
        timeout=60,
        env=dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
        ),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads(p.stdout)


def test_reuses_processors_with_original_dedicated_threads(binaries, tmp_path):
    before = run(binaries["before"], "sequential")
    after = run(binaries["after"], "sequential")
    assert before["calls"] == after["calls"] == 10000
    assert before["os_threads_created"] == 10000
    assert after["os_threads_created"] == 10000
    assert before["processors_constructed"] == 10000
    assert after["processors_constructed"] == 1
    (tmp_path / "measurement.json").write_text(json.dumps(dict(before=before, after=after)))


@pytest.mark.parametrize(
    "mode", ["overflow", "concurrent", "cancel", "requests", "exceptions", "rebind"]
)
def test_preserves_completion_concurrency_and_request_path(binaries, mode):
    assert run(binaries["before"], mode) == run(binaries["after"], mode)


@pytest.mark.parametrize("path", [HEADER, SOURCE, *EXTRA])
def test_instance_patch_rejects_each_changed_input_without_partial_writes(tmp_path, path):
    source(tmp_path)
    changed = tmp_path / path
    changed.write_text(changed.read_text() + "\n")
    before = {name: (tmp_path / name).read_bytes() for name in (HEADER, SOURCE, *EXTRA)}
    with pytest.raises(ValueError, match="preimage differs"):
        BUILDER.reuse_native_message_instances(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())


@pytest.mark.parametrize("mode", ["bounded_cache", "oversized_identity"])
def test_cache_is_bounded_and_releases_payloads(binaries, mode):
    assert run(binaries["after"], mode)["passed"]


def test_instance_patch_rejects_reapplication(tmp_path):
    source(tmp_path)
    BUILDER.reuse_native_message_instances(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in (HEADER, SOURCE, *EXTRA)}
    with pytest.raises(ValueError, match="preimage differs"):
        BUILDER.reuse_native_message_instances(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())


@pytest.mark.parametrize("path", [TRASH_HEADER, TRASH_SOURCE])
def test_collector_node_patch_rejects_changed_source(tmp_path, path):
    source(tmp_path)
    BUILDER.reuse_native_message_instances(tmp_path)
    changed = tmp_path / path
    changed.write_text(changed.read_text() + "\n")
    before = {name: (tmp_path / name).read_bytes() for name in (TRASH_HEADER, TRASH_SOURCE)}
    with pytest.raises(ValueError, match="preimage differs"):
        BUILDER.reuse_native_collector_nodes(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())


def test_collector_nodes_are_reused_after_join_and_remain_bounded(binaries):
    before = run(binaries["before"], "collector")
    after = run(binaries["after"], "collector")
    assert before["calls"] == after["calls"] == 2500
    assert before["node_allocations"] == 2500
    assert after["node_allocations"] == 1
    assert run(binaries["before"], "collector_bound")["node_allocations"] == 128
    assert run(binaries["after"], "collector_bound")["node_allocations"] == 96


def test_collector_cancellation_still_joins_callbacks_before_recycling(binaries):
    assert run(binaries["before"], "collector_cancel") == run(binaries["after"], "collector_cancel")
