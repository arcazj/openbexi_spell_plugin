"""Compiled production gate + original source-derived CIF selection over real Context mTLS.

Scheduler/IPC substrate is controlled, not a complete native interpreter or
native-PID attestation test. Source methods and gate checks are not reimplemented.
"""

from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading
import uuid
import zipfile

import pytest
import test_prompt_agent as agent_tests
from openbexi_spell_server.contracts import Fault

ROOT = Path(__file__).resolve().parents[2]
source = agent_tests.source
setup = agent_tests.setup
family = agent_tests.family
prompts = agent_tests.prompts
provider = agent_tests.provider
relay = agent_tests.relay


@pytest.fixture(scope="session")
def compiled_prompt(tmp_path_factory):
    folder = tmp_path_factory.mktemp("compiled-prompt-boundary")
    original = folder / "source"
    original.mkdir()
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed"
    )
    with zipfile.ZipFile(archive) as z:
        z.extractall(original)
    # Compose the exact existing CPython/source-port recipes in a clean process.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from native_patches import apply_tree; "
            "from integrated_patches import apply_native_tree; "
            "import sys; p=Path(sys.argv[1]); apply_tree(p); "
            "apply_native_tree(p,Path(sys.argv[2]),Path(sys.argv[3]))",
            str(original),
            str(archive),
            str(folder / "composition"),
        ],
        check=True,
        env=dict(os.environ, PYTHONPATH=str(ROOT / "source_port")),
        capture_output=True,
        timeout=30,
    )
    spec = importlib.util.spec_from_file_location(
        "prompt_boundary_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.patch_native_tree(original)
    cif = (original / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    methods = []
    for name in (
        "void SPELLserverCif::startPrompt()",
        "bool SPELLserverCif::cancelPrompt()",
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply)",
        "void SPELLserverCif::waitPromptAnswer()",
    ):
        start = cif.index(name)
        methods.append(cif[start : cif.index("\n}", start) + 2])
    start = cif.index("void SPELLserverCif::processMessage(")
    tail = cif[start : cif.index("// Other messages...", start)]
    first = tail[tail.index("    const bool promptReply") : tail.index("    std::string msgId")]
    reply = tail[tail.index("    // Prompt answers") :]
    methods.append(
        "void SPELLserverCif::processPrompt(const SPELLipcMessage& msg) {\n"
        + first
        + "\n    const auto msgId=msg.getId();\n"
        + reply
        + "\n}"
    )
    harness = (ROOT / "server/tests/native_prompt_harness.cpp").read_text()
    unit = folder / "native.cpp"
    unit.write_text(
        harness
        + "\n\n".join(methods)
        + r"""
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    setenv("OPENBEXI_V08_PROMPTS", "owner-bound/1", 1);
    const std::string mode(argv[1]);
    SPELLserverCif cif;
    cif.m_promptMessage=SPELLipcMessage("MSG_PROMPT");
    cif.m_promptMessage.set("ProcId", "main#1");
    cif.m_promptMessage.set("Text", "Continue?");
    cif.m_promptMessage.set("TimeoutMicroseconds", "600000");
    try { cif.startPrompt(); }
    catch (const std::exception&) { std::cout << "{\"test\":\"OPEN_DENIED\"}" << std::endl; return 0; }
    std::thread waiter([&] { cif.waitPromptAnswer(); });
    // Readiness is test control, not a runtime prompt or a new authority.
    std::cout << "{\"test\":\"READY\"}" << std::endl;
    std::string action, prompt, reply;
    std::string input; std::getline(std::cin, input);
    std::istringstream fields(input); fields >> action >> prompt >> reply;
    SPELLipcMessage msg(action == "CANCEL" ? "MSG_CANCEL" : "MSG_ANSWER");
    msg.set("ProcId", mode == "wrong-instance" ? "other#1" : "main#1");
    msg.set("V08PromptId", prompt); msg.set("V08PromptRequest", reply);
    if (action == "ANSWER") msg.set("ReturnValue", mode == "wrong-answer" ? "forged" : "yes");
    if (mode == "extra-field") msg.set("Arguments", "unqualified");
    if (mode == "redirected") msg.set("ParentId", "main#1");
    if (mode == "cancel-with-answer") msg.set("ReturnValue", "yes");
    if (mode == "wrong-type") msg.setType(99);
    if (mode == "timeout") { /* no incoming reply */ }
    else if (mode == "internal-cancel") { cif.cancelPrompt(); }
    else {
        cif.processPrompt(msg);
        if (mode == "duplicate") cif.processPrompt(msg);
        if (mode == "answer-then-cancel") {
            msg.setId("MSG_CANCEL");msg.fields.erase("ReturnValue");cif.processPrompt(msg);
        }
        if (mode == "cancel-then-answer") {
            msg.setId("MSG_ANSWER");msg.set("ReturnValue", "yes");cif.processPrompt(msg);
        }
    }
    waiter.join();
    const auto& scheduler=SPELLexecutor::instance().getScheduler();
    const auto final=cif.m_promptAnswer.getId();
    std::cout << "{\"test\":\"DONE\",\"id\":\"" << final
              << "\",\"value\":\"" << cif.m_promptAnswer.get("ReturnValue")
              << "\",\"finished\":" << scheduler.finished.load()
              << ",\"cancelled\":" << scheduler.cancelled.load()
              << ",\"denials\":" << denials.load() << "}" << std::endl;
    if (cif.m_promptPending || cif.m_v08Prompt.active) return 3;
    return 0;
}
"""
    )
    binary = folder / "native-prompt"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-pthread",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(unit),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    return binary


def drive(binary, relay, family, pki, mode):
    errors, packets = [], []
    selected = None
    with subprocess.Popen(
        [str(binary), mode],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as native:
        watchdog = threading.Timer(12, native.kill)
        watchdog.daemon = True
        watchdog.start()
        try:
            # Real mTLS service calls are made from this controlled adapter;
            # production SO_PEERCRED/PID attestation is covered separately.
            while True:
                line = native.stdout.readline()
                if not line:
                    break
                body = json.loads(line)
                packets.append(body)
                if body.get("test") == "READY":
                    prompt_id, registration = next(iter(relay.registrations.items()))
                    action = (
                        "CANCEL"
                        if mode
                        in {
                            "cancel",
                            "cancel-with-answer",
                            "cancel-then-answer",
                            "cancel-ack-lost",
                            "cancel-deadline",
                        }
                        else "ANSWER"
                    )
                    native_prompt = dict(
                        prompt_id=prompt_id,
                        target_admission_id=registration[1],
                        definition_sha256=registration[3],
                    )
                    if mode in {"timeout", "internal-cancel"}:
                        native.stdin.write("WAIT unused unused\n")
                    else:
                        status, _ = agent_tests.protocol.enqueue(
                            family,
                            pki,
                            native_prompt,
                            action=action,
                            answer=None if action == "CANCEL" else "yes",
                        )
                        assert status == 200
                        assert relay.poll() == "reply"
                        selected = asdict(next(iter(relay.replies.values()))[1])
                        if mode == "stale-owner":
                            family["controller"](
                                "session.close", dict(connection_id=family["connection"])
                            )
                        target = str(uuid.uuid4()) if mode == "wrong-prompt" else prompt_id
                        reply = "not-a-uuid" if mode == "wrong-reply" else selected["reply_id"]
                        native.stdin.write(f"{action} {target} {reply}\n")
                    native.stdin.flush()
                    continue
                if body.get("test") in {"DONE", "OPEN_DENIED"}:
                    break
                ack = "ALLOW"
                try:
                    if body["schema"] == "openbexi.native-prompt-open/2":
                        if mode == "open-denied":
                            raise ValueError("controlled registration failure")
                        relay.register_definition(body)
                    elif body["schema"] == "openbexi.native-prompt-consume/1":
                        relay.consume(body)
                        if mode in {"consume-ack-lost", "cancel-ack-lost"}:
                            ack = "LOST"
                        elif mode in {"deadline-during-consume", "cancel-deadline"}:
                            time.sleep(0.8)
                    elif body["schema"] == "openbexi.native-prompt-close/1":
                        relay.close(body)
                    else:
                        raise AssertionError("Unknown native callback")
                except (Fault, ValueError) as error:
                    errors.append(type(error).__name__)
                    ack = "DENY"
                native.stdin.write(ack + "\n")
                native.stdin.flush()
            native.stdin.close()
            exit_code = native.wait(timeout=5)
            diagnostic = native.stderr.read()
            assert exit_code == 0, diagnostic
            assert "AddressSanitizer" not in diagnostic and "runtime error:" not in diagnostic
        finally:
            watchdog.cancel()
            if native.poll() is None:
                native.kill()
    return packets, errors, selected


@pytest.mark.parametrize(
    "mode,outcome",
    [
        ("answer", "ANSWER_SELECTED"),
        ("cancel", "CANCEL_SELECTED"),
        ("timeout", "TIMEOUT"),
        ("duplicate", "ANSWER_SELECTED"),
        ("answer-then-cancel", "ANSWER_SELECTED"),
        ("cancel-then-answer", "CANCEL_SELECTED"),
        ("cancel-ack-lost", "TIMEOUT"),
        ("cancel-deadline", "TIMEOUT"),
        ("internal-cancel", "UNKNOWN"),
        ("wrong-instance", "TIMEOUT"),
        ("wrong-prompt", "TIMEOUT"),
        ("wrong-reply", "TIMEOUT"),
        ("wrong-answer", "TIMEOUT"),
        ("wrong-type", "TIMEOUT"),
        ("extra-field", "TIMEOUT"),
        ("redirected", "TIMEOUT"),
        ("cancel-with-answer", "TIMEOUT"),
        ("stale-owner", "TIMEOUT"),
        ("consume-ack-lost", "TIMEOUT"),
        ("deadline-during-consume", "TIMEOUT"),
    ],
)
def test_original_native_selection_with_live_prompt_authority(
    compiled_prompt, relay, family, pki, mode, outcome
):
    packets, _, selected = drive(compiled_prompt, relay, family, pki, mode)
    closes = [b for b in packets if b.get("schema") == "openbexi.native-prompt-close/1"]
    assert len(closes) == 1 and closes[0]["outcome"] == outcome
    row = family["store"].db.execute("SELECT state,outcome FROM native_prompts").fetchone()
    assert tuple(row) == ("CLOSED", outcome)
    assert packets[-1]["test"] == "DONE"
    assert packets[-1]["cancelled"] == (outcome in {"CANCEL_SELECTED", "UNKNOWN"})
    assert packets[-1]["finished"] == (outcome not in {"CANCEL_SELECTED", "UNKNOWN"})
    assert packets[-1]["value"] == (
        "yes" if outcome == "ANSWER_SELECTED" else "default" if outcome == "TIMEOUT" else ""
    )
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    if selected and mode in {
        "consume-ack-lost",
        "deadline-during-consume",
        "cancel-ack-lost",
        "cancel-deadline",
    }:
        assert agent_tests.protocol.rows(family)[0]["state"] == "CONSUMED_UNPROVEN"


def test_native_registration_failure_publishes_no_prompt(compiled_prompt, relay, family, pki):
    packets, errors, _ = drive(compiled_prompt, relay, family, pki, "open-denied")
    assert errors == ["ValueError"]
    assert packets[-1] == {"test": "OPEN_DENIED"}
    assert not any(p.get("test") == "READY" for p in packets)
    assert family["store"].db.execute("SELECT COUNT(*) FROM native_prompts").fetchone()[0] == 0
