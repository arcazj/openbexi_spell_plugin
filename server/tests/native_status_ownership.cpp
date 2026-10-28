// SPDX-License-Identifier: GPL-3.0-or-later
// Actual native CIF bodies and IPC message class. Controller, stack, time and
// transport collaborators are explicit component adapters, not native acceptance.
#include <atomic>
#include <cassert>
#include <cstdio>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>
#include "SPELL_IPC/SPELLipcMessage.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "line_stack.H"
#include "acknowledgement_ownership.H"
enum SPELLexecutorStatus {STATUS_UNINIT,STATUS_LOADED,STATUS_PAUSED,STATUS_FINISHED,STATUS_ERROR,STATUS_ABORTED};
struct SPELLstatusInfo {
    SPELLexecutorStatus status;std::string condition,actionLabel;bool actionEnabled=false;
    explicit SPELLstatusInfo(SPELLexecutorStatus value):status(value){}
};
// The real safe-thread scope releases the GIL; it is not a C++ metadata lock.
struct SPELLsafeThreadOperations {explicit SPELLsafeThreadOperations(const char*){}};
struct SPELLexecutorUtils {static std::string statusToString(SPELLexecutorStatus value){return value==STATUS_LOADED?"LOADED":value==STATUS_PAUSED?"PAUSED":"UNINIT";}};
struct SPELLcontrollerIF {SPELLexecutorStatus state=STATUS_PAUSED;std::string condition;SPELLexecutorStatus getStatus(){return state;}std::string getCondition(){return condition;}};
struct Action {std::string label;bool enabled=false;std::string getLabel(){return label;}bool isEnabled(){return enabled;}};
struct SPELLexecutor {
    SPELLcontrollerIF controller;Action action;bool present=true;
    static SPELLexecutor& instance(){static SPELLexecutor value;return value;}
    bool hasController(){return present;}SPELLcontrollerIF& getController(){return controller;}Action& getUserAction(){return action;}
};
struct Buffer {void flush(){}};
struct SPELLserverCif {
    // These declarations are copied from the actual before/after native header.
#include "status_members.inc"
    Buffer* m_buffer=nullptr;
    std::mutex output_mutex;std::vector<SPELLipcMessage> outputs;
    std::function<void()> on_stack,on_send;
    SPELLserverCif(){m_sequence=0;m_sequenceStack=0;m_stMessage.setId(MessageId::MSG_ID_NOTIFICATION);m_stMessage.setType(MSG_TYPE_NOTIFY);m_stMessage.set(MessageField::FIELD_DATA_TYPE,"STATUS");m_stMessage.set(MessageField::FIELD_PROC_ID,"procedure#0");}
    bool isManual(){return false;}unsigned getNumExecutions(){return 0;}
    std::string getAvailableStack(){return "procedure#0:1";}
    std::string getCodeName(){return "procedure";}
    void v08AvailableStackInto(std::string& out){if(on_stack)on_stack();out=getAvailableStack();}
    void completeMessage(SPELLipcMessage&);void prepareMessage(SPELLipcMessage&,const std::string,SPELLipcMessageType_);
    void specificNotifyStatus(const SPELLstatusInfo&);SPELLipcMessage getPingMessage();
    void sendAcknowledged(const SPELLipcMessage& message){if(on_send)on_send();std::lock_guard<std::mutex> lock(output_mutex);outputs.push_back(message);}
};
#include "status_methods.inc"
static void emit(const SPELLipcMessage& message){for(unsigned char c:message.data())std::printf("%02x",c);std::puts("");}
int main(int argc,char**argv){
    assert(argc==2);const std::string mode=argv[1];SPELLserverCif cif;
    if(mode=="sequence" || mode=="stack-sequence"){
        // An earlier non-stack notification consumes the SAME wire domain.
        if(mode=="stack-sequence"){SPELLipcMessage earlier;cif.completeMessage(earlier);}
        SPELLipcMessage a,b;reserve_barrier=true;
        auto prepare=[&](SPELLipcMessage& msg){if(mode=="sequence")cif.completeMessage(msg);else cif.prepareMessage(msg,"LINE",MSG_TYPE_NOTIFY_ASYNC);};
        std::thread left([&]{prepare(a);});std::thread right([&]{prepare(b);});left.join();right.join();reserve_barrier=false;
        const auto x=a.get(MessageField::FIELD_MSG_SEQUENCE),y=b.get(MessageField::FIELD_MSG_SEQUENCE);
        std::printf("{\"left\":\"%s\",\"right\":\"%s\",\"counter\":%lu,\"stack_counter\":%lu,\"duplicate\":%s}\n",x.c_str(),y.c_str(),static_cast<unsigned long>(cif.m_sequence),static_cast<unsigned long>(cif.m_sequenceStack),x==y?"true":"false");return x==y?5:0;
    }
    if(mode=="template"){
        std::atomic<unsigned> ready{0};
        std::thread ping([&]{ready.fetch_add(1);while(ready.load()<2)std::this_thread::yield();for(unsigned i=0;i<20000;++i){auto message=cif.getPingMessage();assert(!message.isVoid());}});
        std::thread status([&]{ready.fetch_add(1);while(ready.load()<2)std::this_thread::yield();for(unsigned i=0;i<20000;++i)cif.specificNotifyStatus(SPELLstatusInfo(STATUS_LOADED));});ping.join();status.join();std::printf("{\"notifications\":%zu}\n",cif.outputs.size());return 0;
    }
    if(mode=="template-proof"){
        // Warm existing fields, then pause through the explicit stack adapter
        // before ping's return-copy acquires the metadata-cache mutex. Without
        // this boundary, that unrelated cache can incidentally order one pair.
        cif.getPingMessage();std::atomic<unsigned> phase{0};
        static thread_local bool pingThread=false;
        cif.on_stack=[&]{if(pingThread){phase.store(1,std::memory_order_relaxed);while(phase.load(std::memory_order_relaxed)!=2)std::this_thread::yield();}else{phase.store(2,std::memory_order_relaxed);}};
        std::thread ping([&]{pingThread=true;cif.getPingMessage();});
        std::thread status([&]{while(phase.load(std::memory_order_relaxed)!=1)std::this_thread::yield();cif.specificNotifyStatus(SPELLstatusInfo(STATUS_LOADED));});
        ping.join();status.join();std::printf("{\"notifications\":%zu}\n",cif.outputs.size());return 0;
    }
    if(mode=="stack"){
        SPELLipcMessage message;cif.completeMessage(message);
        std::printf("{\"field_present\":%s,\"stack\":\"%s\"}\n",message.hasField(MessageField::FIELD_CSP)?"true":"false",message.get(MessageField::FIELD_CSP).c_str());return 0;
    }
    if(mode=="wire"){
        auto& executor=SPELLexecutor::instance();executor.controller.condition="condition-one";executor.action.label="action-one";executor.action.enabled=true;
        auto first=cif.getPingMessage();const auto unchanged=first.data();emit(first);
        cif.specificNotifyStatus(SPELLstatusInfo(STATUS_LOADED));emit(cif.outputs.back());
        executor.controller.condition="";executor.action.label="";executor.action.enabled=false;
        emit(cif.getPingMessage());
        SPELLstatusInfo direct(STATUS_LOADED);direct.condition="direct-condition";direct.actionLabel="direct-action";direct.actionEnabled=false;cif.specificNotifyStatus(direct);emit(cif.outputs.back());
        emit(cif.getPingMessage());assert(first.data()==unchanged);
        executor.present=false;assert(cif.getPingMessage().isVoid());return 0;
    }
#if V08_STATUS_CANDIDATE
    if(mode=="callbacks"){
        cif.on_stack=[&]{auto copy=cif.v08StatusSnapshot();assert(copy.get(MessageField::FIELD_PROC_ID)=="procedure#0");};
        cif.on_send=[&]{auto copy=cif.v08StatusSnapshot();assert(copy.get(MessageField::FIELD_PROC_ID)=="procedure#0");};
        cif.specificNotifyStatus(SPELLstatusInfo(STATUS_LOADED));auto ping=cif.getPingMessage();assert(ping.hasField(MessageField::FIELD_CSP));std::puts("callbacks-outside-status-lock");return 0;
    }
#endif
    return 2;
}
