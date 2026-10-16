"""Force early answers ahead of acknowledgements through exact native methods."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import prompt_startup_patches as patch

PRELUDE = r'''
#include <chrono>
#include <condition_variable>
#include <future>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
namespace MessageId {
const std::string MSG_ID_CANCEL="CANCEL", MSG_ID_PROMPT_START="START", MSG_ID_PROMPT_END="END";
}
namespace LanguageConstants {const int SCOPE_SYS=1;}
const int MSG_TYPE_ONEWAY=0;
struct SPELLipcMessage {
    std::string id;
    SPELLipcMessage()=default;
    SPELLipcMessage(const std::string& value):id(value){}
    bool isVoid() const {return id.empty();}
    std::string getId() const {return id;}
    void setId(const std::string& value){id=value;}
    void setType(int){}
};
const SPELLipcMessage VOID_MESSAGE;
struct SPELLsafeThreadOperations {explicit SPELLsafeThreadOperations(const char*){}};
struct Config {std::string getControlClient(){return "GUI";} bool isHeadless(){return false;}};
struct Scheduler {
    std::function<void()> acknowledge;
    void startPrompt(int,bool){acknowledge();}
    void cancelPrompt(){acknowledge();}
};
struct SPELLexecutor {
    Scheduler scheduler;
    static SPELLexecutor& instance(){static SPELLexecutor value; return value;}
    Scheduler& getScheduler(){return scheduler;}
};
static std::mutex spellPromptTransitionLock;
struct SPELLserverCif {
    std::mutex m_promptAnswerLock;
    std::condition_variable m_promptAnswerReady;
    SPELLipcMessage m_promptAnswer,m_promptMessage;
    bool m_promptPending=false;
    struct Definition {int timeout=0;} m_promptDef;
    Config getExecutorConfig(){return {};}
    void warning(const char*,int){}
    void sendGUIMessage(const SPELLipcMessage&){}
    void sendGUIMessage(const SPELLipcMessage*){}
    void startPrompt();
    bool cancelPrompt();
    void answer(const SPELLipcMessage& msg);
};
'''

MAIN = r'''
int main() {
    bool passed=true;
    std::cout << "{";
    for (int cancel=0;cancel<2;++cancel) {
        SPELLserverCif cif;
        cif.m_promptPending=true;
        std::promise<void> statusPublished, receiverFinished;
        auto status=statusPublished.get_future();
        auto ack=receiverFinished.get_future();
        bool ackDuringTransition=false;
        SPELLexecutor::instance().scheduler.acknowledge=[&] {
            statusPublished.set_value();
            ackDuringTransition=(ack.wait_for(std::chrono::seconds(2))==std::future_status::ready);
        };
        std::thread receiver([&] {
            status.wait();
            cif.answer(SPELLipcMessage("ANSWER"));
            // The next item on this same channel acknowledges status delivery.
            receiverFinished.set_value();
        });
        bool cancelled=false;
        if (cancel) cancelled=cif.cancelPrompt(); else cif.startPrompt();
        receiver.join();
        bool winner=cancel ? cancelled && cif.m_promptAnswer.getId()=="CANCEL" && !cif.m_promptPending
                           : cif.m_promptAnswer.getId()=="ANSWER" && cif.m_promptPending;
        passed=passed && ackDuringTransition && winner;
        if(cancel) std::cout << ",";
        std::cout << "\"" << (cancel?"cancel":"startup") << "\":{\"ack_during_transition\":"
            << (ackDuringTransition?"true":"false") << ",\"winner_preserved\":"
            << (winner?"true":"false") << "}";
    }
    std::cout << "}\n";
    return passed?0:1;
}
'''


def methods(source):
    text = source.decode()
    blocks = []
    for signature in ('void SPELLserverCif::startPrompt()', 'bool SPELLserverCif::cancelPrompt()'):
        start = text.index(signature)
        blocks.append(text[start:text.index('\n}', start) + 2])
    start = text.index('    if ( msgId == MessageId::MSG_ID_PROMPT_ANSWER )')
    end = text.index('    \treturn;', start)
    answer = text[text.index('\n', text.index('{', start)) + 1:end]
    blocks.append('void SPELLserverCif::answer(const SPELLipcMessage& msg) {\n' + answer + '\n}')
    return '\n'.join(blocks)


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    ported = (Path('/source') / patch.SOURCE).read_bytes()
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    patched = patch.apply(patch.SOURCE, original, ported)
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    result = dict(passed=False, preimage_sha256=digest(ported), patched_sha256=digest(patched), probes={})
    for label, raw in (('original', ported), ('patched', patched)):
        source = output / (label + '-probe.cpp')
        source.write_text(PRELUDE + methods(raw) + MAIN)
        binary = output / (label + '-probe')
        build = subprocess.run(['c++','-std=c++17','-pthread','-Wall','-Wextra','-Werror',
            str(source),'-o',str(binary)],capture_output=True)
        (output / (label + '-build.log')).write_bytes(build.stdout + build.stderr)
        assert build.returncode == 0, build.stderr.decode()
        run = subprocess.run([str(binary)],capture_output=True,timeout=12)
        (output / (label + '-run.log')).write_bytes(run.stdout + run.stderr)
        observed = json.loads(run.stdout)
        assert run.returncode == (1 if label == 'original' else 0)
        assert all(row['winner_preserved'] and row['ack_during_transition'] is (label == 'patched')
                   for row in observed.values())
        result['probes'][label] = dict(exit_code=run.returncode, observation=observed,
            source_sha256=digest(source.read_bytes()), binary_sha256=digest(binary.read_bytes()))
    result['passed'] = True
    result['scope'] = 'Exact prompt methods with controlled ordered answer/ack transport; native acceptance still required'
    (output / 'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
