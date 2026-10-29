"""Actual Context methods under a deterministic startup/binding interleaving.

The process spawn, identity RPC, IPC transport and registry dependencies are
explicit component seams. Hosted native startup stress remains mandatory.
"""

import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest
from native_build_batch import NativeBuildBatch
from test_native_status_ownership import (
    component_recording,  # noqa: F401
    component_run,
    method,
    status_sources,  # noqa: F401
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def startup_ack_binaries(status_sources, component_recording, request):  # noqa: F811
    folder, tree, _before, _contract, _builder = status_sources
    out = folder / "startup-ack"
    out.mkdir()
    files = {
        "client": "lib/SPELL_CTX/src/SPELLclient.C",
        "manager": "lib/SPELL_CTX/src/SPELLexecutorManager.C",
    }
    current = {key: (tree / relative).read_text() for key, relative in files.items()}
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        original_client = archive.read(files["client"]).decode()
    original = method(original_client, "void SPELLclient::processMessageFromClient(")
    assert hashlib.sha256(original.encode()).hexdigest() == (
        "e839685f88176e758c756b89b13de8620800ff5c58611f775daf417a36aa4a1b"
    )
    template = (Path(__file__).with_name("native_startup_ack_fixture.cpp")).read_text()
    batch = NativeBuildBatch(out, request)
    binaries = {}
    signatures = (
        "void SPELLexecutorManager::startExecutor(",
        "void SPELLexecutorManager::recoverExecutor(",
        "SPELLexecutor* SPELLexecutorManager::getExecutor(",
    )
    common = [method(current["manager"], signature) for signature in signatures]
    for profile in ("before", "candidate"):
        methods = list(common)
        if profile == "before":
            methods.append(original)
        else:
            methods.extend(
                [
                    method(current["client"], "void SPELLclient::processMessageFromClient("),
                    method(current["manager"], "void SPELLexecutorManager::acknowledgeExecutor("),
                ]
            )
        source, binary = out / f"{profile}.cpp", out / profile
        source.write_text(template.replace("// VERBATIM_METHODS", "\n\n".join(methods)))
        (out / f"{profile}.methods.json").write_text(
            json.dumps(
                {
                    value.split("\n", 1)[0]: hashlib.sha256(value.encode()).hexdigest()
                    for value in methods
                },
                indent=2,
            )
            + "\n"
        )
        command = [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-fno-pie",
            "-no-pie",
        ]
        if profile == "candidate":
            command.append("-DCANDIDATE")
        command.extend([str(source), "-o", str(binary)])
        batch.add(command, timeout=45)
        binaries[profile] = binary
    batch.run()
    return binaries


def run_case(binary, case):
    result = component_run(
        [str(binary), case],
        label=f"startup-ack-{binary.name}-{case}",
        binary=binary,
        timeout=5,
        env=os.environ
        | {"ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"},
    )
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("case", ["start", "recover"])
def test_original_ack_lookup_reproduces_loss_before_registry_publication(
    startup_ack_binaries, case
):
    result, record = run_case(startup_ack_binaries["before"], case)
    assert result.returncode == 41
    assert record["before_publication_return"] == 1
    assert record["delivered"] == 0 and record["expected"] == 1
    assert result.stderr == b"ACK routing component assertion failed\n"


@pytest.mark.parametrize(
    "case",
    [
        "start",
        "recover",
        "start-observer",
        "recover-observer",
        "start-failed",
        "recover-failed",
        "published",
        "unknown",
        "nonack",
        "command",
    ],
)
def test_ack_waits_for_publication_preserving_owner_and_failure_checks(startup_ack_binaries, case):
    result, record = run_case(startup_ack_binaries["candidate"], case)
    assert result.returncode == 0, result.stderr.decode()
    assert record["delivered"] == record["expected"]
    assert not record["before_publication_return"]
    assert result.stderr == b""
