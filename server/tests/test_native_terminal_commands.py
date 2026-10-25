"""Compile native terminal guard and actual composed CIF command handler."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native_composition(tmp_path_factory):
    directory = tmp_path_factory.mktemp("terminal-native")
    source = directory / "source"
    source.mkdir()
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(source)
    sys.path.insert(0, str(ROOT / "source_port"))
    try:
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, archive, directory / "evidence")
    finally:
        sys.path.remove(str(ROOT / "source_port"))
    spec = importlib.util.spec_from_file_location(
        "terminal_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.patch_native_tree(source)
    return source


def compile_and_run(tmp_path, code):
    source, binary = tmp_path / "terminal.cpp", tmp_path / "terminal"
    source.write_text(code)
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)


def test_compiled_terminal_permits_and_copied_mailbox_races(tmp_path):
    compile_and_run(
        tmp_path,
        r"""
#include "terminal_gate.H"
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
struct Command {
    std::string id, v08Request;
    bool v08External = true, v08TerminalAdmitted = false;
};
int main() {
    int rpc = 0;
    for (const std::string id: {"CMD_ABORT", "CMD_CLOSE"}) {
        Command cmd{id, id + "-id"};
        v08_admit_terminal_command(cmd, id == "CMD_CLOSE", [&]() { ++rpc; });
        assert(cmd.v08TerminalAdmitted);
        bool rejected = false;
        try { v08_admit_terminal_command(cmd, id == "CMD_CLOSE", [&]() { ++rpc; }); }
        catch (const std::exception&) { rejected = true; }
        assert(rejected);
        V08TerminalContinuations guard;
        std::atomic<int> winners{0};
        std::vector<std::thread> threads;
        for (int i=0;i<64;++i) threads.emplace_back([&, cmd]() {
            try { guard.consume(cmd); ++winners; } catch (const std::exception&) {}
        });
        for (auto& thread:threads) thread.join();
        assert(winners == 1);
    }
    assert(rpc == 2);
    for (auto cmd: {Command{"CMD_RUN", "x"}, Command{"CMD_ABORT", ""},
                   Command{"CMD_ABORT", "x", false, false}}) {
        bool rejected = false;
        try { v08_admit_terminal_command(cmd, false, [&]() { ++rpc; }); }
        catch (const std::exception&) { rejected = true; }
        assert(rejected && !cmd.v08TerminalAdmitted);
    }
    Command early_close{"CMD_CLOSE", "close-running"};
    try { v08_admit_terminal_command(early_close, false, [&]() { ++rpc; }); assert(false); }
    catch (const std::exception&) {}
    Command lost{"CMD_ABORT", "lost-ack"};
    try { v08_admit_terminal_command(lost, false, []() { throw std::runtime_error("lost"); }); assert(false); }
    catch (const std::exception&) {}
    assert(!lost.v08TerminalAdmitted && rpc == 2);
    V08TerminalContinuations guard;
    try { guard.consume(lost); assert(false); } catch (const std::exception&) {}
}
""",
    )


def test_compiled_composed_cif_fences_before_prompt_cancel_and_closing(
    native_composition, tmp_path
):
    text = (native_composition / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    start = text.index("void SPELLserverCif::processMessageCommand(")
    end = text.index("\n}", start) + 2
    actual_handler = text[start:end]
    assert actual_handler.index("v08_admit_terminal_command") < actual_handler.index(
        "cancelPrompt()"
    )
    assert actual_handler.index("v08_admit_terminal_command") < actual_handler.index("setClosing()")
    compile_and_run(
        tmp_path,
        r"""
#include "mutation_policy.H"
#include "terminal_gate.H"
#include <cassert>
#include <map>
#include <utility>
#define LOG_INFO(x) do {} while(false)
const int STATUS_RUNNING=1, STATUS_PAUSED=2, STATUS_FINISHED=3, STATUS_ABORTED=4, STATUS_ERROR=5;
namespace ExecutorMessages {
const std::string MSG_CMD_ABORT="CMD_ABORT", MSG_CMD_CLOSE="CMD_CLOSE", MSG_CMD_BLOCK="CMD_BLOCK",
MSG_CMD_GOTO="CMD_GOTO", MSG_CMD_SCRIPT="CMD_SCRIPT";
}
namespace MessageField {
const std::string FIELD_GOTO_LINE="GotoLine", FIELD_GOTO_LABEL="GotoLabel", FIELD_SCRIPT="Script";
}
struct ExecutorCommand {
 std::string id,arg,earg,v08Request;
 bool v08External=false,v08TerminalAdmitted=false;
};
struct SPELLipcMessage {
 std::string id;
 std::map<std::string,std::string> fields;
 std::string getId() const { return id; }
 bool hasField(const std::string& key) const { return fields.count(key); }
 std::string get(const std::string& key) const { return fields.at(key); }
};
int requests=0, denials=0, dispositions=0;
bool allowed=true;
std::set<std::string> consumed;
void v08_native_request(std::initializer_list<std::pair<std::string,std::string>> values) {
 ++requests;
 std::map<std::string,std::string> body;
 for (const auto& value:values) body.insert(value);
 if (!allowed || body.at("instance_id")!="root#1" ||
     !consumed.insert(body.at("request_id")).second) throw std::runtime_error("denied");
}
void v08_note_disabled_mutation(const std::string&,const std::string&) { ++denials; }
void v08_report_native_disposition(const std::string&,const ExecutorCommand& cmd,const char*) {
 assert(cmd.v08TerminalAdmitted); ++dispositions;
}
struct SPELLexecutor {
 int status=STATUS_RUNNING,queued=0; ExecutorCommand last;
 static SPELLexecutor& instance() { static SPELLexecutor value; return value; }
 int getStatus() { return status; }
 void command(const ExecutorCommand& value,bool high) { assert(high); last=value; ++queued; }
};
struct Lock { void lock() {} };
struct SPELLmonitor { SPELLmonitor(Lock&) {} };
struct SPELLserverCif {
 Lock m_ipcLock;
 int cancellations=0, closing=0; bool prompt=false;
 std::string getProcId() { return "root#1"; }
 bool cancelPrompt() { ++cancellations; return prompt; }
 void setClosing() { ++closing; }
 void processMessageCommand(const SPELLipcMessage& msg);
};
"""
        + actual_handler
        + r"""
int main() {
 assert(!v08_message_disabled("CMD_ABORT",false));
 assert(v08_message_disabled("CMD_ABORT",true));
 assert(v08_external_command_disabled("CMD_SCRIPT",true));
 assert(v08_request_supported("REQ_EXEC_STATUS"));
 auto& executor=SPELLexecutor::instance();
 SPELLserverCif cif;
 cif.prompt=true;
 cif.processMessageCommand({"CMD_ABORT",{}});
 assert(requests==0 && cif.cancellations==0 && cif.closing==0 && executor.queued==0);
 allowed=false;
 cif.processMessageCommand({"CMD_ABORT",{{"V08ControlRequest","denied"}}});
 assert(requests==1 && cif.cancellations==0 && executor.queued==0);
 allowed=true;
 cif.processMessageCommand({"CMD_ABORT",{{"V08ControlRequest","accepted"}}});
 assert(requests==2 && cif.cancellations==1 && executor.queued==0 && dispositions==1);
 cif.processMessageCommand({"CMD_ABORT",{{"V08ControlRequest","accepted"}}});
 assert(cif.cancellations==1 && dispositions==1);
 cif.prompt=false;
 cif.processMessageCommand({"CMD_ABORT",{{"V08ControlRequest","no-prompt"}}});
 assert(cif.cancellations==2 && executor.queued==1 && executor.last.v08TerminalAdmitted);
 cif.processMessageCommand({"CMD_CLOSE",{{"V08ControlRequest","too-early"}}});
 assert(cif.closing==0 && executor.queued==1);
 executor.status=STATUS_ABORTED;
 cif.processMessageCommand({"CMD_CLOSE",{{"V08ControlRequest","close-terminal"}}});
 assert(cif.closing==1 && executor.queued==2 && executor.last.v08TerminalAdmitted);
 cif.processMessageCommand({"CMD_CLOSE",{{"V08ControlRequest","close-terminal"}}});
 assert(cif.closing==1 && executor.queued==2);
 assert(denials==5);
}
""",
    )
