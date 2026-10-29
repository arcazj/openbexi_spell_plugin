"""Compiled composed CIF prompt methods, including real Context/mTLS callbacks.

The actual port recipes and candidate source patch generate the compiled methods.
IPC message/Python-GIL/scheduler dependencies are fixtures, NOT full Executor
binaries. Hosted native/driver/cleanup acceptance remains mandatory.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import select
import shutil
import subprocess
import sys
import zipfile

import pytest

from openbexi_spell_server.contracts import Fault, digest
import test_prompt_agent as agents
import test_prompt_authority as protocol
import test_child_gate as gates

ROOT = Path(__file__).resolve().parents[2]
source = agents.source
setup = agents.setup
family = agents.family
prompts = agents.prompts
provider = agents.provider
relay = agents.relay


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def native_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("composed-prompt")
    original = root / "source"
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as z:
        z.extractall(original)
    before_path = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT / "source_port"))
        sys.path.insert(0, str(ROOT / "host_runtime"))
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(original)
        apply_native_tree(
            original, ROOT / "docs/reference/SPELL2.6.10-src.zip", root / "composition"
        )
        builder = load(ROOT / "host_runtime/build_admission_context.py", "prompt_builder")
        enabled = root / "enabled"
        # Branch before private overlays, exactly as the hosted builder does.
        # Stream reuse changes CIF source after prompt/terminal composition;
        # adding prompts to an already-finished default tree is invalid.
        shutil.copytree(original, enabled)
        builder.patch_native_tree(original)
        builder.patch_native_tree(enabled, prompts=True)
        patcher = load(ROOT / "host_runtime/native_prompt_patch.py", "prompt_hooks")
    finally:
        sys.path[:] = before_path
    return root, original, enabled, patcher


def method(text, signature):
    start = text.index(signature)
    return text[start : text.index("\n}", start) + 2]


@pytest.fixture(scope="session")
def native_prompt_binary(native_sources):
    root, _, enabled, _ = native_sources
    text = (enabled / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    signatures = (
        "void SPELLserverCif::v08ProcessPrompt(",
        "void SPELLserverCif::startPrompt()",
        "bool SPELLserverCif::cancelPrompt(",
        "void SPELLserverCif::waitPromptAnswer()",
    )
    generated = "static std::mutex spellPromptTransitionLock;\n" + "\n\n".join(
        method(text, signature) for signature in signatures
    )
    (root / "composed_prompt_methods.inc").write_text(generated)
    binary = root / "native_prompt_test"
    compiler = subprocess.run(
        [
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
            str(ROOT / "server/tests/native_prompt_harness.cpp"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (root / "compile.log").write_text(compiler.stdout + compiler.stderr)
    assert compiler.returncode == 0, compiler.stdout + compiler.stderr
    return binary


@pytest.mark.parametrize(
    "case",
    [
        "early_answer",
        "cancel_order",
        "wrong_scope",
        "duplicate_answer",
        "late_generation",
        "denied_answer",
        "denied_cancel",
        "timeout_during_answer",
        "timeout_during_cancel",
        "lost_entropy",
        "lost_registration",
        "lost_close",
        "empty_default",
        "internal_cancel",
    ],
)
def test_exact_composed_native_prompt_methods(native_prompt_binary, case):
    result = subprocess.run(
        [str(native_prompt_binary), case], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip().removeprefix("RESULT "))["passed"] is True


def test_prompt_patch_is_opt_in_and_refuses_wrong_or_duplicate_compositions(
    native_sources, tmp_path
):
    _, default, enabled, patcher = native_sources
    path = "lib/SPELL_CIFS/src/SPELLserverCif.C"
    original = (default / path).read_text()
    assert "v08ProcessPrompt(" not in original
    assert "v08_message_disabled(msg.getId()" in original
    changed = (enabled / path).read_text()
    assert "v08ProcessPrompt(msg)" in changed
    # Generic command deny policy still closes ABORT/CLOSE/STOP and arbitrary setters.
    assert "if (!v08_command_supported(msg.getId()))" in changed
    assert "Owner-admitted request protocol unavailable" in changed
    sums = {
        name: hashlib.sha256((enabled / name).read_bytes()).hexdigest()
        for name in (path, "include/SPELL_CIFS/SPELLserverCif.H")
    }
    with pytest.raises(ValueError, match="preimage"):
        patcher.patch_prompt_tree(enabled)
    assert sums == {
        name: hashlib.sha256((enabled / name).read_bytes()).hexdigest() for name in sums
    }
    raw = tmp_path / "raw"
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as z:
        z.extractall(raw)
    with pytest.raises(ValueError, match="preimage"):
        patcher.patch_prompt_tree(raw)


def test_cancel_retains_asynchronous_dispatch_and_original_ordered_answer(native_sources):
    _, _, enabled, _ = native_sources
    for name in ("Client", "Server"):
        text = (enabled / f"lib/SPELL_IPC/src/SPELLipc{name}Interface.C").read_text()
        start = text.index("// Prompt answers only forward")
        block = text[start : text.index("return;", start)]
        assert "MSG_ID_PROMPT_ANSWER" in block
        assert "MSG_ID_CANCEL" not in block
    builder = (ROOT / "host_runtime/build_admission_context.py").read_text()
    assert "prompts=False" in builder and '"--native-prompts"' in builder
    assert "prompts=args.native_prompts" in builder


def native_line(process):
    ready, _, _ = select.select([process.stdout], [], [], 7)
    assert ready, "Native prompt fixture failed to produce a bounded callback"
    line = process.stdout.readline().strip()
    assert line, "Native prompt fixture exited before completing callback"
    return line


def unhex(value):
    return "" if value == "_" else bytes.fromhex(value).decode("utf-8")


def callback(line):
    parts = line.split()
    assert parts[0] == "CALL"
    if parts[1] == "declare":
        return dict(
            schema="openbexi.native-prompt-declare/1",
            prompt_id=parts[2],
            instance_id=unhex(parts[3]),
            definition={unhex(k): unhex(v) for k, v in (p.split("=") for p in parts[4:])},
        )
    if parts[1] == "consume":
        return dict(
            schema="openbexi.native-prompt-consume/1",
            prompt_id=parts[2],
            instance_id=unhex(parts[3]),
            reply_id=parts[4],
            action=parts[5],
            answer=unhex(parts[6]) if parts[5] == "ANSWER" else None,
        )
    assert parts[1] == "close"
    return dict(
        schema="openbexi.native-prompt-close/1",
        prompt_id=parts[2],
        instance_id=unhex(parts[3]),
        outcome=parts[4],
    )


@pytest.mark.parametrize(
    "mode,action,answer",
    [
        ("pipe_answer", "ANSWER", "yes"),
        ("pipe_cancel", "CANCEL", None),
        ("pipe_denied", "ANSWER", "yes"),
    ],
)
def test_compiled_native_selection_through_real_context_mtls(
    native_prompt_binary, relay, family, pki, mode, action, answer
):
    server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
    server.prompts = relay
    server.report = lambda *a, **k: None
    process = subprocess.Popen(
        [str(native_prompt_binary), mode],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        declared = callback(native_line(process))
        server.dispatch("executor", "main#1", declared)
        process.stdin.write("ALLOW\n")
        process.stdin.flush()
        definition = dict(
            declared, definition_sha256=digest(declared["definition"]), target_admission_id=None
        )
        assert protocol.enqueue(family, pki, definition, action=action, answer=answer)[0] == 200
        seen = []

        def deliver(command, fields, **options):
            assert options == dict(send=True, procedure="main#1")
            assert command == ("MSG_ANSWER" if action == "ANSWER" else "MSG_CANCEL")
            if mode == "pipe_denied":
                family["controller"]("session.close", dict(connection_id=family["connection"]))
            process.stdin.write(fields["V08PromptRequest"] + "\n")
            process.stdin.flush()
            consumption = callback(native_line(process))
            seen.append(consumption["schema"])
            try:
                server.dispatch("executor", "main#1", consumption)
            except Fault as error:
                assert mode == "pipe_denied" and error.status == 403
                process.stdin.write("DENY\n")
            else:
                assert mode != "pipe_denied"
                process.stdin.write("ALLOW\n")
            process.stdin.flush()
            closing = callback(native_line(process))
            seen.append(closing["schema"])
            server.dispatch("executor", "main#1", closing)
            process.stdin.write("ALLOW\n")
            process.stdin.flush()

        relay.journal.original = deliver
        assert relay.poll() == "reply"
        result = json.loads(native_line(process).removeprefix("RESULT "))
        assert process.wait(timeout=5) == 0
        assert result["passed"] is True and result["closes"] == 1
        assert result["aborts"] == (1 if action == "CANCEL" else 0)
        assert seen == ["openbexi.native-prompt-consume/1", "openbexi.native-prompt-close/1"]
        row = family["store"].db.execute("SELECT state,outcome FROM native_prompts").fetchone()
        assert row["state"] == "CLOSED"
        assert row["outcome"] == (
            "TIMEOUT"
            if mode == "pipe_denied"
            else "ANSWER_SELECTED"
            if action == "ANSWER"
            else "CANCEL_SELECTED"
        )
        assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"ProcId": "other#1"},
        {"V08PromptId": "user-controlled"},
        {"Text": False},
        {"Text": "nul\x00"},
        {"Text": "x" * 17000},
        {"": "missing-key"},
    ],
)
def test_native_definition_cannot_substitute_member_or_digest(relay, changes):
    import uuid

    body = dict(
        schema="openbexi.native-prompt-declare/1",
        instance_id="main#1",
        prompt_id=str(uuid.uuid4()),
        definition={"ProcId": "main#1", "Text": "Continue?", **changes},
    )
    with pytest.raises((ValueError, Fault)):
        relay.declare(body)
    assert not relay.open_attempted


def test_opt_in_prompt_module_is_shipped_and_source_bound_in_native_build():
    builder = (ROOT / "scripts/qualify_v08_native_launch.py").read_text()
    workflow = (ROOT / ".github/workflows/v08-server-foundation.yml").read_text()
    assert builder.count('ROOT / "host_runtime/native_prompt_patch.py"') == 2
    assert 'native_build / "native_prompt_patch.py"' in builder
    assert (
        "COPY *.H private_bridge.cpp build.py native_prompt_patch.py native_terminal_patch.py native_startup_ack_patch.py epoch_connection.py /candidate/"
        in builder
    )
    assert workflow.count("'host_runtime/native_prompt_patch.py'") == 2
    assert builder.count('ROOT / "host_runtime/native_startup_ack_patch.py"') == 2
    assert 'native_build / "native_startup_ack_patch.py"' in builder
    assert workflow.count("'host_runtime/native_startup_ack_patch.py'") == 2
    # Existing hosted cohorts must not silently activate unqualified prompts.
    assert '" --native-prompts" if profile.native_prompts else ""' in builder
    assert 'parser.add_argument("--native-prompts", action="store_true")' in builder
    assert "native-prompts" in workflow and "flags: '--native-prompts'" in workflow


def test_real_native_yes_no_timeout_uses_accepted_default_key():
    """The original helper accepts Y/YES, not Python bool True, as a default."""
    import importlib.util

    path = ROOT / "scripts/v08_prompt_cohort.py"
    spec = importlib.util.spec_from_file_location("prompt_timeout_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = module.prompt_fixture(timeout=True)
    assert "Default:'Y'" in fixture and "Timeout:1" in fixture
    assert "Default:True" not in fixture
    # Cross-check the actual composed native conversion, not just the fixture.
    import zipfile

    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        helper = archive.read("lib/SPELL_CIF/src/SPELLcifHelper.C").decode()
    assert 'deflt == "Y" || deflt == ISTR(LanguageConstants::PROMPT_YES)' in helper
