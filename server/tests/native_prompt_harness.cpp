// SPDX-License-Identifier: GPL-3.0-or-later
// Executes the exact patched, composed SPELL CIF methods. Dependency fixtures
// replace IPC/Python/scheduler; this is not a full native Executor acceptance.
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include "prompt_policy.H"
using namespace std::chrono_literals;
#define THROW_EXCEPTION(a,b,c) throw std::runtime_error(b)
#define LOG_WARN(a) do {} while (false)
const int MSG_TYPE_ONEWAY=1, MSG_TYPE_PROMPT=2;
namespace MessageId {
const std::string MSG_ID_CANCEL="MSG_CANCEL", MSG_ID_PROMPT_ANSWER="MSG_ANSWER";
const std::string MSG_ID_PROMPT_END="MSG_PROMPT_END", MSG_ID_PROMPT_START="MSG_PROMPT_START";
}
namespace MessageField { const std::string FIELD_RVALUE="ReturnValue"; }
namespace LanguageConstants { const int SCOPE_SYS=0; }
struct SPELLipcMessage {
    std::string id;
    int type=MSG_TYPE_ONEWAY;
    std::map<std::string,std::string> fields;
    SPELLipcMessage(std::string value=""):id(value){}
    std::string getId() const {return id;}
    int getType() const {return type;}
    void setId(const std::string& value) {id=value;}
    void setType(int value) {type=value;}
    std::string get(const std::string& key) const {
        auto found=fields.find(key);return found==fields.end()?"":found->second;
    }
    void set(const std::string& key,const std::string& value) {fields[key]=value;}
    bool isVoid() const {return id.empty();}
    const auto& v08Fields() const {return fields;}
};
const SPELLipcMessage VOID_MESSAGE;
struct SPELLtime {
    long ms=0;
    long getSeconds() const {return 0;}
    long getMilliseconds() const {return ms;}
    long getMicroseconds() const {return 0;}
};
struct Definition {SPELLtime timeout; bool defaultProvided=false;std::string defaultAnswer;};
namespace SPELLcifHelper {
std::string getRawAnswer(const std::string& value,const Definition&) {return value;}
}
struct SPELLsafeThreadOperations {explicit SPELLsafeThreadOperations(const char*){}};
struct Config {
    std::string getControlClient() const {return "test-owner";}
    bool isHeadless() const {return false;}
};
std::atomic<int> starts{0},aborts{0},finishes{0},declares{0},consumes{0},closes{0},denials{0},published{0};
std::function<void()> abort_hook,start_hook,consume_hook,publish_hook;
struct Scheduler {
    void startPrompt(const SPELLtime&,bool){++starts;if(start_hook)start_hook();}
    void finishPrompt(){++finishes;}
    void cancelPrompt(){++aborts;if(abort_hook)abort_hook();}
};
struct SPELLexecutor {
    Scheduler scheduler;
    static SPELLexecutor& instance(){static SPELLexecutor e;return e;}
    Scheduler& getScheduler(){return scheduler;}
};
struct SPELLserverCif {
    std::mutex m_promptAnswerLock;
    std::condition_variable m_promptAnswerReady;
    bool m_promptPending=false;
    SPELLipcMessage m_promptAnswer,m_promptMessage;
    Definition m_promptDef;
    std::string m_v08PromptId,m_v08PromptOutcome="UNKNOWN";
    bool m_v08PromptUncertain=false;
    std::string getProcId() const {return "main#1";}
    Config getExecutorConfig() const {return {};}
    void warning(const std::string&,int){}
    void sendGUIMessage(const SPELLipcMessage& msg) {
        if(msg.id=="MSG_PROMPT"){++published;if(publish_hook)publish_hook();}
    }
    void sendGUIMessage(const SPELLipcMessage* msg){sendGUIMessage(*msg);}
    void startPrompt();void waitPromptAnswer();
    bool cancelPrompt(const SPELLipcMessage* ownerReply=nullptr);
    void v08ProcessPrompt(const SPELLipcMessage&);
};
SPELLserverCif* cif=nullptr;
bool deny_authority=false,fail_declare=false,fail_close=false,fail_entropy=false,pipe_rpc=false;
std::string outcome,reply_id="bbbbbbbb-1111-4111-8111-222222222222";
std::string hex(const std::string& value) {
    const char* table="0123456789abcdef";std::string result;
    for(unsigned char ch:value){result+=table[ch>>4];result+=table[ch&15];}
    return result.empty()?"_":result;
}
void rpc(const std::string& frame) {
    std::cout << "CALL " << frame << std::endl;
    std::string response;
    if(!std::getline(std::cin,response)||response!="ALLOW")throw std::runtime_error("authority denied");
}
void assert_mailbox_unlocked() {
    assert(cif->m_promptAnswerLock.try_lock());cif->m_promptAnswerLock.unlock();
}
std::string v08_new_prompt_id(){
    if(fail_entropy)throw std::runtime_error("entropy unavailable");
    static int n=0;
    return "aaaaaaaa-1111-4111-8111-"+std::string(11,'0')+std::to_string(++n);
}
void v08_declare_prompt(const std::string& instance,const std::string& id,const SPELLipcMessage& msg){
    assert_mailbox_unlocked();++declares;
    if(pipe_rpc){std::string frame="declare "+id+" "+hex(instance);
        for(const auto& field:msg.fields) frame+=" "+hex(field.first)+"="+hex(field.second);
        rpc(frame);}
    if(fail_declare)throw std::runtime_error("registration lost");
}
void v08_consume_prompt(const std::string& instance,const SPELLipcMessage& msg){
    assert_mailbox_unlocked();++consumes;
    if(consume_hook)consume_hook();
    if(pipe_rpc)rpc("consume "+msg.get("V08PromptId")+" "+hex(instance)+" "+
        msg.get("V08PromptRequest")+" "+(msg.id=="MSG_ANSWER"?"ANSWER":"CANCEL")+" "+hex(msg.get("ReturnValue")));
    if(deny_authority)throw std::runtime_error("owner fenced");
}
void v08_close_prompt(const std::string& instance,const std::string& id,const std::string& result){
    assert_mailbox_unlocked();++closes;outcome=result;
    if(pipe_rpc)rpc("close "+id+" "+hex(instance)+" "+result);
    if(fail_close)throw std::runtime_error("close reply lost");
}
void v08_note_disabled_mutation(const std::string&,const std::string&){++denials;}
#include "composed_prompt_methods.inc"

void prepare(SPELLserverCif& c,long ms=0){
    c.m_promptDef.timeout.ms=ms;c.m_promptDef.defaultProvided=ms>0;
    c.m_promptDef.defaultAnswer="default";
    c.m_promptMessage=SPELLipcMessage("MSG_PROMPT");
    c.m_promptMessage.set("ProcId","main#1");c.m_promptMessage.set("Text","Continue?");
    c.m_promptMessage.set("DefaultProvided",ms>0?"True":"False");
    c.m_promptMessage.set("Default",ms>0?"default":"");
    c.m_promptMessage.set("TimeoutMicroseconds",std::to_string(ms*1000));
}
SPELLipcMessage reply(const SPELLserverCif& c,bool cancel=false){
    SPELLipcMessage m(cancel?"MSG_CANCEL":"MSG_ANSWER");m.set("ProcId",c.getProcId());
    m.set("V08PromptId",c.m_v08PromptId);m.set("V08PromptRequest",reply_id);
    if(!cancel) m.set("ReturnValue","yes");
    return m;
}
template<class F> void must_throw(F fn){bool threw=false;try{fn();}catch(const std::exception&){threw=true;}assert(threw);}
void run(const std::string& mode){
    SPELLserverCif c;cif=&c;
    if(mode=="early_answer"){
        prepare(c);publish_hook=[&]{c.v08ProcessPrompt(reply(c));};
        c.startPrompt();c.waitPromptAnswer();assert(c.m_promptAnswer.get("ReturnValue")=="yes");
        assert(outcome=="ANSWER_SELECTED"&&consumes==1&&finishes==1&&aborts==0);
    } else if(mode=="cancel_order"){
        prepare(c);c.startPrompt();auto m=reply(c,true);
        std::promise<void> entered,release;auto release_wait=release.get_future();
        abort_hook=[&]{entered.set_value();release_wait.wait();};
        auto waiter=std::async(std::launch::async,[&]{c.waitPromptAnswer();});
        auto cancelled=std::async(std::launch::async,[&]{c.v08ProcessPrompt(m);});
        entered.get_future().wait();
        // A spurious wakeup cannot let cancelled Python continue before abort.
        for(int n=0;n<5;++n)c.m_promptAnswerReady.notify_all();
        assert(waiter.wait_for(30ms)==std::future_status::timeout);
        release.set_value();cancelled.get();waiter.get();
        assert(outcome=="CANCEL_SELECTED"&&aborts==1&&finishes==0&&closes==1);
    } else if(mode=="wrong_scope"){
        prepare(c,20);c.startPrompt();
        auto wrong=reply(c);wrong.set("ProcId","other#1");c.v08ProcessPrompt(wrong);
        wrong=reply(c);wrong.set("ParentId","main#1");c.v08ProcessPrompt(wrong);
        wrong=reply(c);wrong.set("V08PromptId","aaaaaaaa-1111-4111-8111-999999999999");c.v08ProcessPrompt(wrong);
        wrong=reply(c);wrong.set("unexpected","x");c.v08ProcessPrompt(wrong);
        wrong=reply(c,true);wrong.set("ReturnValue","bad");c.v08ProcessPrompt(wrong);
        assert(consumes==0&&denials==5);c.waitPromptAnswer();assert(outcome=="TIMEOUT");
    } else if(mode=="duplicate_answer"){
        prepare(c);c.startPrompt();auto m=reply(c);c.v08ProcessPrompt(m);c.v08ProcessPrompt(m);
        c.waitPromptAnswer();assert(consumes==1&&denials==1&&outcome=="ANSWER_SELECTED");
    } else if(mode=="late_generation"){
        prepare(c);c.startPrompt();auto old=reply(c);c.v08ProcessPrompt(old);c.waitPromptAnswer();
        prepare(c,10);c.startPrompt();c.v08ProcessPrompt(old);c.waitPromptAnswer();
        assert(consumes==1&&denials==1&&closes==2&&outcome=="TIMEOUT");
    } else if(mode=="denied_answer"||mode=="denied_cancel"){
        prepare(c,20);c.startPrompt();deny_authority=true;
        c.v08ProcessPrompt(reply(c,mode=="denied_cancel"));
        assert(c.m_promptAnswer.isVoid()&&aborts==0);c.waitPromptAnswer();
        assert(outcome=="TIMEOUT"&&denials==1&&finishes==1);
    } else if(mode=="timeout_during_answer"||mode=="timeout_during_cancel"){
        prepare(c,20);c.startPrompt();auto m=reply(c,mode=="timeout_during_cancel");
        std::promise<void> entered,release;auto release_wait=release.get_future();
        consume_hook=[&]{entered.set_value();release_wait.wait();};
        auto answer=std::async(std::launch::async,[&]{c.v08ProcessPrompt(m);});
        entered.get_future().wait();c.waitPromptAnswer();release.set_value();answer.get();
        assert(c.m_promptAnswer.get("ReturnValue")=="default"&&aborts==0&&outcome=="TIMEOUT"&&denials==1);
    } else if(mode=="lost_entropy"){
        prepare(c);fail_entropy=true;must_throw([&]{c.startPrompt();});
        assert(!c.m_promptPending&&c.m_v08PromptUncertain&&c.m_v08PromptId.empty());
        fail_entropy=false;must_throw([&]{c.startPrompt();});
        assert(declares==0&&published==0&&starts==0);
    } else if(mode=="lost_registration"){
        prepare(c);fail_declare=true;must_throw([&]{c.startPrompt();});
        fail_declare=false;must_throw([&]{c.startPrompt();});
        assert(declares==1&&published==0&&starts==0&&!c.m_promptPending&&c.m_v08PromptUncertain);
    } else if(mode=="lost_close"){
        prepare(c);c.startPrompt();c.v08ProcessPrompt(reply(c));fail_close=true;
        must_throw([&]{c.waitPromptAnswer();});fail_close=false;
        prepare(c);must_throw([&]{c.startPrompt();});assert(closes==1&&declares==1&&c.m_v08PromptUncertain);
    } else if(mode=="empty_default"){
        prepare(c,10);c.m_promptDef.defaultAnswer="";c.startPrompt();c.waitPromptAnswer();
        assert(outcome=="TIMEOUT"&&consumes==0&&c.m_promptAnswer.get("ReturnValue").empty());
    } else if(mode=="internal_cancel"){
        prepare(c);c.startPrompt();assert(c.cancelPrompt());c.waitPromptAnswer();
        assert(outcome=="UNKNOWN"&&consumes==0&&aborts==1);
    } else if(mode=="pipe_answer"||mode=="pipe_cancel"||mode=="pipe_denied"){
        pipe_rpc=true;prepare(c,mode=="pipe_denied"?30:0);c.startPrompt();
        std::string line;if(!std::getline(std::cin,line))throw std::runtime_error("missing owner grant");
        reply_id=line;c.v08ProcessPrompt(reply(c,mode=="pipe_cancel"));c.waitPromptAnswer();
        assert(outcome==(mode=="pipe_answer"?"ANSWER_SELECTED":mode=="pipe_cancel"?"CANCEL_SELECTED":"TIMEOUT"));
    } else {throw std::runtime_error("unknown test case");}
    std::cout<<"RESULT {\"passed\":true,\"declares\":"<<declares<<",\"consumes\":"<<consumes
       <<",\"closes\":"<<closes<<",\"aborts\":"<<aborts<<",\"finishes\":"<<finishes
       <<",\"denials\":"<<denials<<",\"outcome\":\""<<outcome<<"\"}"<<std::endl;
}
int main(int argc,char** argv){try{if(argc!=2)return 2;run(argv[1]);return 0;}
catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
