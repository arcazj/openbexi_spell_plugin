"""Exact composed CIF/controller methods + production JSON/Unix IPC + real Context mTLS.

CIF/scheduler dependencies are fixtures, not whole interpreter/cleanup acceptance.
Read-only image provisioning is fixture-owned; actual process PID/executable
and pidfd checks, native request transport and Context cryptography execute.
"""

from pathlib import Path
import hashlib
import json
import os
import select
import socket
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import zipfile

import pytest

import test_native_prompt_boundary as prompts
import test_terminal_commands as terminal
import test_control as controls
import test_child_gate as gates
import test_owner_commands as owner
from openbexi_spell_server.commands import NativeOwnerCommands
from openbexi_spell_server.control import NativeControlJournal

ROOT = Path(__file__).resolve().parents[2]
source = terminal.source
setup = terminal.setup
family = terminal.family
provider = terminal.provider


@pytest.fixture(scope="session")
def terminal_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-terminals")
    source = root / "source"
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        archive.extractall(source)
    old_path = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, ROOT / "docs/reference/SPELL2.6.10-src.zip", root / "composition")
        builder = prompts.load(ROOT / "host_runtime/build_admission_context.py", "terminal_builder")
        builder.patch_native_tree(source, prompts=True, terminals=True)
    finally:
        sys.path[:] = old_path
    return root, source


@pytest.fixture(scope="session")
def terminal_binary(terminal_sources):
    root, source = terminal_sources
    cif = (source / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    controller = (source / "lib/SPELL_EXC/src/SPELLcontroller.C").read_text()
    generated = (
        prompts.method(cif, "void SPELLserverCif::v08ProcessTerminal(")
        + "\n"
        + prompts.method(controller, "void SPELLcontroller::executeCommand(")
    )
    (root / "composed_terminal_methods.inc").write_text(generated)
    binary = root / "terminal"
    args = [
        "c++",
        "-std=c++17",
        "-pthread",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O1",
        "-I",
        str(ROOT / "host_runtime/native"),
        "-I",
        str(root),
    ]
    if os.getenv("V08_TERMINAL_SANITIZERS") == "1":
        args += [
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
        ]
    if os.getenv("V08_JSON_INCLUDE"):
        args += ["-I", os.environ["V08_JSON_INCLUDE"]]
    args += [str(ROOT / "server/tests/native_terminal_harness.cpp"), "-o", str(binary)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    (root / "compile.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    if os.getenv("OPENBEXI_SERVER_EVIDENCE_DIR"):
        evidence = Path(os.environ["OPENBEXI_SERVER_EVIDENCE_DIR"])
        evidence.mkdir(parents=True, exist_ok=True)
        record = {
            "scope": "composed original methods; production Unix IPC and Context mTLS",
            "full_native_lifecycle_qualified": False,
            "sanitizers": os.getenv("V08_TERMINAL_SANITIZERS") == "1",
            "composed_methods_sha256": hashlib.sha256(generated.encode()).hexdigest(),
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "headers": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "host_runtime/native").glob("*.H"))
            },
        }
        (evidence / "native-terminal-compiled-methods.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
    return binary


def test_terminal_dispatch_precedes_original_side_effects(terminal_sources):
    _, source = terminal_sources
    text = (source / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    incoming = prompts.method(text, "void SPELLserverCif::processMessage(")
    assert incoming.index("v08_terminal_command(") < incoming.index(
        "m_ipcInterruptionNotified = false"
    )
    command = prompts.method(text, "void SPELLserverCif::processMessageCommand(")
    assert command.index("v08ProcessTerminal(") < command.index("cancelPrompt()")
    assert command.index("v08ProcessTerminal(") < command.index("setClosing()")
    terminal = prompts.method(text, "void SPELLserverCif::v08ProcessTerminal(")
    check = terminal.index("v08_terminal_authorize(")
    assert (
        check
        < terminal.index("cancelPrompt()")
        < terminal.index("SPELLexecutor::instance().command(")
    )
    assert check < terminal.index("setClosing()")


def test_terminal_patch_rejects_wrong_or_repeated_composition(terminal_sources):
    _, source = terminal_sources
    patcher = prompts.load(ROOT / "host_runtime/native_terminal_patch.py", "terminal_repatch")
    paths = [
        source / "include/SPELL_CIFS/SPELLserverCif.H",
        source / "lib/SPELL_CIFS/src/SPELLserverCif.C",
    ]
    before = [p.read_bytes() for p in paths]
    with pytest.raises(ValueError, match="preimage"):
        patcher.patch_terminal_tree(source, prompts=True)
    assert before == [p.read_bytes() for p in paths]


@pytest.mark.parametrize(
    "operation,scenario",
    [
        ("CMD_ABORT", "allowed"),
        ("CMD_CLOSE", "allowed"),
        ("CMD_ABORT", "prompt"),
        ("CMD_ABORT", "duplicate"),
        ("CMD_CLOSE", "duplicate"),
        ("CMD_ABORT", "token"),
        ("CMD_CLOSE", "token"),
        ("CMD_ABORT", "disconnect"),
        ("CMD_CLOSE", "disconnect"),
        ("CMD_ABORT", "expiry"),
        ("CMD_CLOSE", "expiry"),
        ("CMD_ABORT", "target"),
        ("CMD_CLOSE", "redirect"),
        ("CMD_CLOSE", "extra"),
        ("CMD_CLOSE", "type"),
        ("CMD_ABORT", "direct"),
        ("CMD_CLOSE", "direct"),
        ("CMD_ABORT", "lost_ack"),
        ("CMD_CLOSE", "lost_ack"),
        ("CMD_ABORT", "between"),
        ("CMD_CLOSE", "between"),
    ],
)
def test_composed_native_boundary_production_socket_and_real_crypto(
    terminal_binary, family, pki, provider, operation, scenario
):
    NativeControlJournal(family["app"].authority)
    NativeOwnerCommands(family["app"].authority, terminal_commands=True)
    journal = controls.module.NativeRunJournal(
        SimpleNamespace(instance="main#1", request=lambda *a, **k: {}),
        provider.request,
        provider.route,
        provider,
        terminal_commands=True,
    )
    # Provision a short UNIX path. The production server authentication checks
    # actual SO_PEERCRED, executable path, parent PID, starttime and pidfds.
    with tempfile.TemporaryDirectory(prefix="v08-terminal-") as temporary:
        path = str(Path(temporary) / "auth.sock")
        env = dict(
            os.environ, OPENBEXI_V08_ADMISSION_SOCKET=path, OPENBEXI_V08_AGENT_PID=str(os.getpid())
        )
        process = subprocess.Popen(
            [str(terminal_binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
        server.path = path
        server.gate, server.controls, server.prompts = provider, journal, None
        server.executor = terminal_binary.resolve()
        server.executor_sha256 = hashlib.sha256(server.executor.read_bytes()).hexdigest()
        server.context_pid = os.getpid()
        server.pidfd = os.pidfd_open(os.getpid(), 0)
        server.listener = lambda: SimpleNamespace(pid=os.getppid(), poll=lambda: None)
        server.members, server.member_pids, server.disabled_mutations = {}, {}, set()
        server.control_denials, server.consume_denials = threading.Event(), threading.Event()
        server.gui = SimpleNamespace(close=lambda: None)
        server.report = lambda *a, **k: None
        server.stop = threading.Event()
        server.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.socket.bind(path)
        server.socket.listen(4)
        server.socket.settimeout(0.1)
        server.thread = threading.Thread(target=server.serve, daemon=True)
        server.thread.start()
        try:
            assert select.select([process.stdout], [], [], 5)[0]
            assert process.stdout.readline().strip() == "READY"
            server.register(
                dict(schema="openbexi.native-member/1", instance_id="main#1", pid=process.pid)
            )
            grant = terminal.delivered(family, pki, operation)
            journal.dispatch_owner(grant)
            journal.forward(
                dict(
                    schema="openbexi.native-control/1",
                    instance_id="main#1",
                    request_id=grant["command_id"],
                    command=operation,
                )
            )
            if scenario == "token":
                from dataclasses import replace

                target, admitted = journal.owner_operations[grant["command_id"]]
                journal.owner_operations[grant["command_id"]] = (
                    target,
                    replace(admitted, token="0" * 64),
                )
            if scenario == "disconnect":
                family["controller"]("session.close", dict(connection_id=family["connection"]))
            if scenario == "expiry":
                family["app"].authority.clock = lambda: grant["expires_at"] + 1
            original_dispatch = server.dispatch

            def dispatch(role, instance, body):
                original_dispatch(role, instance, body)
                if (
                    body.get("schema") == "openbexi.native-terminal/1"
                    and body.get("stage") == "preprocess"
                ):
                    if scenario == "lost_ack":
                        raise TimeoutError("after durable commit")
                    if scenario == "between":
                        family["controller"](
                            "session.close", dict(connection_id=family["connection"])
                        )

            server.dispatch = dispatch
            fields = {
                "ProcId": "other#1" if scenario == "target" else "main#1",
                "V08ControlRequest": grant["command_id"],
            }
            if scenario == "redirect":
                fields["ParentId"] = "main#1"
            if scenario == "extra":
                fields["cryptographically_verified"] = "true"
            request = dict(
                command=operation,
                fields=fields,
                prompt=scenario == "prompt",
                duplicate=scenario == "duplicate",
                direct=scenario == "direct",
                type=2 if scenario == "type" else 1,
            )
            out, error = process.communicate(json.dumps(request) + "\n", timeout=15)
            assert process.returncode == 0, error
            effect = json.loads(out)
            if scenario in ("allowed", "duplicate"):
                assert effect["abort"] == (operation == "CMD_ABORT")
                assert effect["close"] == (operation == "CMD_CLOSE")
                assert effect["start_processing"] == 1 and effect["dispatch"] == 1
                assert owner.rows(family)[0]["state"] == "EXECUTION_UNPROVEN"
            elif scenario == "prompt":
                assert effect["prompt_cancelled"] == 1 and effect["dispatch"] == 0
                assert owner.rows(family)[0]["state"] == "TERMINAL_PREPROCESSED_UNPROVEN"
            elif scenario == "between":
                assert effect["start_processing"] == effect["abort"] == effect["close"] == 0
                assert effect["closing"] == (operation == "CMD_CLOSE")
                assert effect["cancel_calls"] == (operation == "CMD_ABORT")
                assert owner.rows(family)[0]["state"] == "TERMINAL_PREPROCESSED_UNPROVEN"
            else:
                assert all(
                    effect[k] == 0
                    for k in (
                        "cancel_calls",
                        "prompt_cancelled",
                        "closing",
                        "abort",
                        "close",
                        "start_processing",
                        "dispatch",
                    )
                ), effect
            assert (
                family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            server.close()
