"""Original composed CIF guards and the actual cross-unit terminal ticket registry.

These compiled checks supplement, not replace, the full native hosted cohort.
"""

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

import test_native_prompt_boundary as source_boundary

native_sources = source_boundary.native_sources
method = source_boundary.method

ROOT = Path(__file__).resolve().parents[2]


def patcher():
    spec = importlib.util.spec_from_file_location(
        "native_terminal_patch", ROOT / "host_runtime/native_terminal_patch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terminal_cif_consumption_precedes_original_first_effects(native_sources, tmp_path):
    _, _, prompt_source, _ = native_sources
    source = tmp_path / "terminal"
    shutil.copytree(prompt_source, source)
    patcher().patch_terminal_tree(source)
    text = (source / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    dispatch = method(text, "void SPELLserverCif::processMessageCommand(")
    consume = dispatch.index("v08_admit_terminal_cif(")
    for first_effect in (
        "cancelPrompt(nullptr, &v08TerminalPrompt)",
        "setClosing()",
        "SPELLexecutor::instance().command(",
    ):
        assert consume < dispatch.index(first_effect)
    message = method(text, "void SPELLserverCif::processMessage(")
    assert message.index("v08_terminal_command(") < message.index(
        "m_ipcInterruptionNotified = false"
    )
    assert message.index("processMessageCommand(msg)") < message.index(
        "m_ipcInterruptionNotified = false"
    )
    assert dispatch.index("v08_queue_terminal(") < dispatch.index(
        "SPELLexecutor::instance().command("
    )
    cancelled = method(text, "bool SPELLserverCif::cancelPrompt(")
    assert "m_v08PromptId != *terminalPrompt" in cancelled
    assert cancelled.index("m_v08PromptId != *terminalPrompt") < cancelled.index("m_promptAnswer =")
    hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in patcher().PREIMAGES
    }
    with pytest.raises(ValueError, match="preimage"):
        patcher().patch_terminal_tree(source)
    assert hashes == {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in hashes
    }


def test_terminal_profile_is_explicit_and_does_not_weaken_original_default(tmp_path):
    code = r"""
#include "mutation_policy.H"
#include <cassert>
int main() {
    assert(v08_request_supported("REQ_EXEC_STATUS"));
    assert(!v08_command_supported("CMD_ABORT"));
    assert(!v08_command_supported("CMD_CLOSE"));
    assert(v08_message_disabled("MSG_ANSWER", false));
    assert(v08_external_command_disabled("CMD_ABORT", true));
    assert(!v08_external_command_disabled("CMD_STOP", false));
}
"""
    run_cpp(tmp_path, code)
    enabled = (
        code.replace(
            'assert(!v08_command_supported("CMD_ABORT"));',
            'assert(v08_command_supported("CMD_ABORT"));',
        )
        .replace(
            'assert(!v08_command_supported("CMD_CLOSE"));',
            'assert(v08_command_supported("CMD_CLOSE"));',
        )
        .replace(
            'assert(v08_external_command_disabled("CMD_ABORT", true));',
            'assert(!v08_external_command_disabled("CMD_ABORT", true));',
        )
    )
    run_cpp(tmp_path, enabled, flags=["-DOPENBEXI_V08_TERMINAL_COMMANDS=1"])


def run_cpp(path, code, *, flags=(), extra=()):
    source, binary = path / "test.cpp", path / "test-native-terminal"
    source.write_text(code)
    result = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "host_runtime/native"),
            *flags,
            str(source),
            *map(str, extra),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr


def test_actual_native_ticket_is_one_use_across_translation_units_and_threads(tmp_path):
    other = tmp_path / "other.cpp"
    other.write_text(r"""
#include "terminal_ticket.H"
void queue_elsewhere() {
    v08_terminal::advance("root#1","CMD_ABORT","r1",
        v08_terminal::Phase::ADMITTED, v08_terminal::Phase::QUEUED);
}
""")
    run_cpp(
        tmp_path,
        r"""
#include "terminal_ticket.H"
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
void queue_elsewhere();
int main() {
    using namespace v08_terminal;
    auto denied = [](auto action) {
        try { action(); } catch(const std::exception&) { return true; }
        return false;
    };
    assert(denied([]{advance("root#1","CMD_ABORT","r1",Phase::ADMITTED,Phase::QUEUED);}));
    begin("root#1","CMD_ABORT","r1");
    assert(denied([]{begin("root#1","CMD_ABORT","r1");}));
    assert(denied([]{advance("other#1","CMD_ABORT","r1",Phase::ATTEMPTED,Phase::ADMITTED);}));
    assert(denied([]{advance("root#1","CMD_CLOSE","r1",Phase::ATTEMPTED,Phase::ADMITTED);}));
    advance("root#1","CMD_ABORT","r1",Phase::ATTEMPTED,Phase::ADMITTED);
    queue_elsewhere();
    std::atomic<int> winners{0}; std::vector<std::thread> threads;
    for (int i=0; i<16; ++i) threads.emplace_back([&]{
        try {advance("root#1","CMD_ABORT","r1",Phase::QUEUED,Phase::CLAIMED);++winners;}
        catch(const std::exception&) {}
    });
    for(auto& thread:threads) thread.join();
    assert(winners==1);
    assert(denied([]{advance("root#1","CMD_ABORT","r1",Phase::QUEUED,Phase::CLAIMED);}));
    assert(denied([]{begin("root#1","CMD_STOP","r2");}));
    for(int i=1;i<512;++i) begin("root#1","CMD_CLOSE","bounded-"+std::to_string(i));
    assert(denied([]{begin("root#1","CMD_CLOSE","overflow");}));
}
""",
        extra=[other],
    )


def test_exact_native_terminal_message_scope_validator(tmp_path):
    gate = (ROOT / "host_runtime/native/terminal_gate.H").read_text()
    start = gate.index("inline bool v08_terminal_command(")
    end = gate.index("inline void v08_admit_terminal_cif(", start)
    code = '#include "prompt_policy.H"\n#include <map>\n#include <cassert>\n' + gate[start:end]
    code += r"""
int main() {
    std::map<std::string,std::string> f{{"ProcId","root#1"},
        {"V08ControlRequest","00000000-0000-4000-8000-000000000001"}};
    for(const auto cmd:{"CMD_ABORT","CMD_CLOSE"}) {
        assert(v08_terminal_message_valid(cmd,true,f,"root#1"));
        assert(!v08_terminal_message_valid(cmd,false,f,"root#1"));
        assert(!v08_terminal_message_valid(cmd,true,f,"other#1"));
        auto redirect=f;redirect["ParentId"]="child#1";
        assert(!v08_terminal_message_valid(cmd,true,redirect,"root#1"));
        auto broken=f;broken["V08ControlRequest"]="bad";
        assert(!v08_terminal_message_valid(cmd,true,broken,"root#1"));
        auto user=f;user["User"]="descriptive-not-authority";
        assert(v08_terminal_message_valid(cmd,true,user,"root#1"));
    }
    assert(!v08_terminal_message_valid("CMD_RUN",true,f,"root#1"));
    assert(!v08_terminal_message_valid("CMD_STOP",true,f,"root#1"));
}
"""
    run_cpp(tmp_path, code)
