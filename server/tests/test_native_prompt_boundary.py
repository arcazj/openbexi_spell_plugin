"""Compile exact patched native methods to exercise selection/timeout lock races.

The surrounding class/transport fixtures are controlled; the separate Docker
cohort must execute the full source-derived native runtime.
"""

import importlib.util
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-prompt-source")
    source = root / "source"
    source.mkdir()
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            target = source / item.filename
            assert target.resolve().is_relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
    sys.path.insert(0, str(ROOT / "source_port"))
    try:
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, ROOT / "docs/reference/SPELL2.6.10-src.zip", root / "receipt")
    finally:
        sys.path.remove(str(ROOT / "source_port"))
    spec = importlib.util.spec_from_file_location(
        "prompt_candidate_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.patch_native_tree(source)
    return source


PRELUDE = r"""
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <functional>
#include <future>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
namespace nlohmann { struct json {
    template<class T> json(const T&) {}
    json(std::initializer_list<json>) {}
}; }
namespace MessageId {
const std::string MSG_ID_CANCEL="MSG_CANCEL", MSG_ID_PROMPT_START="START",
MSG_ID_PROMPT_END="END", MSG_ID_PROMPT_ANSWER="MSG_ANSWER";
}
namespace MessageField { const std::string FIELD_RVALUE="ReturnValue"; }
namespace LanguageConstants { const int SCOPE_SYS=1; }
const int MSG_TYPE_ONEWAY=0;
#define THROW_EXCEPTION(a,b,c) throw std::runtime_error(b)
struct SPELLipcMessage {
    std::string id;
    std::map<std::string,std::string> fields;
    SPELLipcMessage()=default;
    SPELLipcMessage(const std::string& value):id(value){}
    bool isVoid() const {return id.empty();}
    std::string getId() const {return id;}
    std::string get(const std::string& key) const {
        auto x=fields.find(key);return x==fields.end()?"":x->second;
    }
    void setId(const std::string& value){id=value;}
    void setType(int){}
    void set(const std::string& key,const std::string& value){fields[key]=value;}
    const std::map<std::string,std::string>& v08Fields() const {return fields;}
};
const SPELLipcMessage VOID_MESSAGE;
struct SPELLsafeThreadOperations { explicit SPELLsafeThreadOperations(const char*){} };
struct SPELLtime {
    int milliseconds=0;
    int getSeconds() const{return 0;}
    int getMilliseconds() const{return milliseconds;}
    int getMicroseconds() const{return 0;}
};
struct Definition {SPELLtime timeout;bool defaultProvided=false;std::string defaultAnswer="DEFAULT";};
struct Config {std::string getControlClient(){return "GUI";}bool isHeadless(){return false;}};
struct Scheduler {
    std::function<void()> start=[]{};
    std::function<void()> cancel=[]{};
    void startPrompt(const SPELLtime&,bool){start();}
    void cancelPrompt(){cancel();}
    void finishPrompt(){}
};
struct SPELLexecutor {
    Scheduler scheduler;
    static SPELLexecutor& instance(){static SPELLexecutor x;return x;}
    Scheduler& getScheduler(){return scheduler;}
};
struct SPELLcifHelper {static std::string getRawAnswer(const std::string& x,const Definition&){return x;}};
static std::mutex spellPromptTransitionLock;
struct SPELLserverCif {
    std::mutex m_promptAnswerLock;
    std::condition_variable m_promptAnswerReady;
    SPELLipcMessage m_promptAnswer,m_promptMessage;
    bool m_promptPending=false;
    std::string m_v08PromptId,m_v08PromptOutcome="UNKNOWN";
    Definition m_promptDef;
    Config getExecutorConfig(){return {};}
    std::string getProcId(){return "root#1";}
    void warning(const char*,int){}
    void sendGUIMessage(const SPELLipcMessage&){}
    void sendGUIMessage(const SPELLipcMessage*){}
    void startPrompt();
    bool cancelPrompt();
    bool cancelPromptForId(const std::string&);
    bool v08HandlePromptReply(const SPELLipcMessage&);
    void waitPromptAnswer();
};
static SPELLserverCif* observed=nullptr;
static int identity=0, consumed=0;
static std::vector<std::string> closes;
static std::function<void()> authorization=[]{ };
static std::function<void()> registration=[]{ };
static bool v08_prompt_enabled(){return true;}
static std::string v08_prompt_identity(){return "prompt-"+std::to_string(++identity);}
static void v08_open_prompt(const std::string&,const std::string&,const nlohmann::json&) {
    assert(observed->m_promptAnswerLock.try_lock()); observed->m_promptAnswerLock.unlock();
    registration();
}
static void v08_consume_prompt(const std::string&,const std::string&,const SPELLipcMessage&) {
    assert(observed->m_promptAnswerLock.try_lock()); observed->m_promptAnswerLock.unlock();
    ++consumed; authorization();
}
static void v08_close_prompt(const std::string&,const std::string&,const std::string& outcome) {
    assert(observed->m_promptAnswerLock.try_lock()); observed->m_promptAnswerLock.unlock();
    closes.push_back(outcome);
}
"""

MAIN = r"""
static SPELLipcMessage answer(SPELLserverCif& cif,const std::string& id="MSG_ANSWER") {
    SPELLipcMessage msg(id);msg.set("V08PromptId",cif.m_v08PromptId);msg.set("ReturnValue","value");return msg;
}
int main(int argc,char** argv) {
    assert(argc==2);
    const std::string test=argv[1];
    SPELLserverCif cif; observed=&cif;
    if(test=="registration-failure") {
        registration=[] {throw std::runtime_error("unavailable");};
        try {cif.startPrompt();assert(false);}catch(const std::runtime_error&){}
        assert(!cif.m_promptPending && closes.empty());return 0;
    }
    cif.startPrompt();
    if(test=="answer" || test=="denied" || test=="foreign" || test=="duplicate") {
        auto msg=answer(cif);
        if(test=="foreign") {
            auto bad=msg;bad.set("V08PromptId","foreign");assert(!cif.v08HandlePromptReply(bad));assert(consumed==0);
        }
        if(test=="denied") {
            authorization=[]{throw std::runtime_error("fenced");};
            try {cif.v08HandlePromptReply(msg);assert(false);}catch(const std::runtime_error&){}
            assert(cif.m_promptPending && cif.m_promptAnswer.isVoid());
            authorization=[]{ };
        }
        assert(cif.v08HandlePromptReply(msg));
        if(test=="duplicate") assert(!cif.v08HandlePromptReply(msg) && consumed==1);
        cif.waitPromptAnswer();assert(closes==std::vector<std::string>{"ANSWER_SELECTED"});
        assert(cif.m_promptAnswer.get("ReturnValue")=="value" && cif.m_v08PromptId.empty());
    } else if(test=="default-during-rpc" || test=="old-cancel-new-generation") {
        cif.m_promptDef.defaultProvided=true;cif.m_promptDef.timeout.milliseconds=20;
        auto msg=answer(cif,test=="old-cancel-new-generation"?"MSG_CANCEL":"MSG_ANSWER");
        std::promise<void> entering,release;auto ready=entering.get_future();auto held=release.get_future();
        authorization=[&]{entering.set_value();held.wait();};
        auto receiving=std::async(std::launch::async,[&]{return cif.v08HandlePromptReply(msg);});
        assert(ready.wait_for(std::chrono::seconds(2))==std::future_status::ready);
        cif.waitPromptAnswer();assert(closes==std::vector<std::string>{"DEFAULT_SELECTED"});
        if(test=="old-cancel-new-generation") cif.startPrompt();
        release.set_value();assert(!receiving.get());
        if(test=="old-cancel-new-generation") {
            assert(cif.m_promptPending && cif.m_promptAnswer.isVoid());
            authorization=[]{ };assert(cif.v08HandlePromptReply(answer(cif)));cif.waitPromptAnswer();
            assert(closes.size()==2 && closes[1]=="ANSWER_SELECTED");
        } else assert(cif.m_promptAnswer.get("ReturnValue")=="DEFAULT");
    } else if(test=="cancel-completion-before-wakeup") {
        std::promise<void> aborting,finish;auto started=aborting.get_future();auto block=finish.get_future();
        SPELLexecutor::instance().scheduler.cancel=[&]{aborting.set_value();block.wait();};
        auto msg=answer(cif,"MSG_CANCEL");
        auto cancelling=std::async(std::launch::async,[&]{return cif.v08HandlePromptReply(msg);});
        assert(started.wait_for(std::chrono::seconds(2))==std::future_status::ready);
        auto waiting=std::async(std::launch::async,[&]{cif.waitPromptAnswer();});
        assert(waiting.wait_for(std::chrono::milliseconds(30))==std::future_status::timeout);
        finish.set_value();assert(cancelling.get());waiting.get();
        assert(closes==std::vector<std::string>{"CANCEL_SELECTED"});
    } else if(test=="early-answer-before-start-ack") {
        // A second prompt starts while its scheduler publication awaits ACK.
        assert(cif.cancelPrompt());cif.waitPromptAnswer();closes.clear();
        std::promise<void> published,ack;auto status=published.get_future();auto seen=ack.get_future();
        SPELLexecutor::instance().scheduler.start=[&]{
            published.set_value();assert(seen.wait_for(std::chrono::seconds(2))==std::future_status::ready);
        };
        auto receiver=std::async(std::launch::async,[&]{status.wait();assert(cif.v08HandlePromptReply(answer(cif)));ack.set_value();});
        cif.startPrompt();receiver.get();cif.waitPromptAnswer();
        assert(closes==std::vector<std::string>{"ANSWER_SELECTED"});
    } else {assert(false);}
    return 0;
}
"""


@pytest.fixture(scope="module")
def prompt_binary(native_source, tmp_path_factory):
    text = (native_source / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    signatures = (
        "void SPELLserverCif::startPrompt()",
        "bool SPELLserverCif::cancelPrompt()",
        "bool SPELLserverCif::cancelPromptForId(const std::string& expectedPrompt)",
        "bool SPELLserverCif::v08HandlePromptReply(const SPELLipcMessage& msg)",
        "void SPELLserverCif::waitPromptAnswer()",
    )
    blocks = []
    for signature in signatures:
        assert text.count(signature) == 1
        start = text.index(signature)
        blocks.append(text[start : text.index("\n}", start) + 2])
    folder = tmp_path_factory.mktemp("native-prompt-compiled")
    unit = folder / "probe.cpp"
    unit.write_text(PRELUDE + "\n".join(blocks) + MAIN)
    binary = folder / "probe"
    build = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-g",
            str(unit),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert build.returncode == 0, build.stderr
    return binary


@pytest.mark.parametrize(
    "case",
    [
        "answer",
        "denied",
        "foreign",
        "duplicate",
        "default-during-rpc",
        "old-cancel-new-generation",
        "cancel-completion-before-wakeup",
        "early-answer-before-start-ack",
        "registration-failure",
    ],
)
def test_original_native_prompt_selection_and_races(prompt_binary, case):
    run = subprocess.run([str(prompt_binary), case], capture_output=True, text=True, timeout=8)
    assert run.returncode == 0, run.stdout + run.stderr


def test_prompt_patcher_refuses_unknown_or_already_patched_source(native_source):
    spec = importlib.util.spec_from_file_location(
        "native_prompt_patch_test", ROOT / "host_runtime/native/prompt_patch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="preimage differs"):
        module.apply_prompt_boundary(native_source)


def test_native_opt_in_precedes_default_deny_and_checks_exact_target(native_source):
    source = (native_source / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    handler = source.split("void SPELLserverCif::processMessage(", 1)[1]
    assert handler.index("v08_prompt_enabled()") < handler.index("v08_message_disabled(")
    header = (ROOT / "host_runtime/native/prompt_gate.H").read_text()
    assert "msg.get(MessageField::FIELD_PROC_ID) != instance" in header
    assert 'msg.get("ParentId").empty()' in header
    assert 'msg.get("V08PromptId") != prompt' in header
    assert "msg.get(MessageField::FIELD_RVALUE).size() > 4096" in header
