"""Compile real incoming classes and completion guards with instrumented threads.

Transport and synchronization adapters are minimal test doubles; the production
pool, patched incoming header, constructors, run, finish, cancel, start and join
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


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load(ROOT / "host_runtime/build_admission_context.py", "workers_builder")
PORT = load(ROOT / "source_port/native_patches.py", "workers_port")


def source(folder):
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for name in (HEADER, SOURCE):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            text = PORT.apply(name, archive.read(name)).decode()
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
            BUILDER.reuse_native_message_workers(folder)
        include = folder / "include"
        for dependency in (
            "SPELL_IPC/SPELLipcChannel.H",
            "SPELL_IPC/SPELLipcInterfaceListener.H",
            "SPELL_SYN/SPELLthread.H",
            "SPELL_SYN/SPELLevent.H",
            "SPELL_SYN/SPELLthreadWork.H",
            "SPELL_IPC/SPELLipcOutput.H",
            "SPELL_UTIL/SPELLlog.H",
            "SPELL_SYN/SPELLmonitor.H",
        ):
            path = include / dependency
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#include "adapters.H"\n')
        (include / "adapters.H").write_text(adapters)
        header = folder / HEADER
        header.write_text(
            header.read_text().replace(
                "/candidate/message_workers.H", str(ROOT / "host_runtime/native/message_workers.H")
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


def test_reuses_os_threads_across_completed_native_messages(binaries, tmp_path):
    before = run(binaries["before"], "sequential")
    after = run(binaries["after"], "sequential")
    assert before["calls"] == after["calls"] == 10000
    assert before["os_threads_created"] == 10000
    assert after["os_threads_created"] == 1
    (tmp_path / "measurement.json").write_text(json.dumps(dict(before=before, after=after)))


@pytest.mark.parametrize("mode", ["overflow", "concurrent", "cancel", "requests", "exceptions"])
def test_preserves_completion_concurrency_and_request_path(binaries, mode):
    assert run(binaries["before"], mode) == run(binaries["after"], mode)


def test_pool_shutdown_drains_and_rejects_late_work(binaries):
    assert run(binaries["after"], "shutdown")["shutdown_drained"]


@pytest.mark.parametrize("change", ["header", "implementation", "reapply"])
def test_rejects_source_drift_without_partial_writes(tmp_path, change):
    source(tmp_path)
    if change == "reapply":
        BUILDER.reuse_native_message_workers(tmp_path)
    else:
        path = tmp_path / (HEADER if change == "header" else SOURCE)
        path.write_text(path.read_text() + "\n")
    before = {name: (tmp_path / name).read_bytes() for name in (HEADER, SOURCE)}
    with pytest.raises(ValueError, match="preimage differs"):
        BUILDER.reuse_native_message_workers(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())
