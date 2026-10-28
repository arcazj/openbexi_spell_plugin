// SPDX-License-Identifier: GPL-3.0-or-later
// Actual CIF, integer-formatting, private-bridge callback and IPC message bodies.
// Controller, time source and transport are explicit component collaborators.
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <functional>
#include <mutex>
#include <set>
#include <strings.h>
#include <thread>
#include <vector>
#include "SPELL_IPC/SPELLipcMessage.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "line_stack.H"
#include "acknowledgement_ownership.H"
#define LOG_WARN(x) do {} while(false)
using SPELLmonitor=std::lock_guard<std::mutex>;
enum SPELLexecutorStatus {STATUS_UNINIT,STATUS_LOADED,STATUS_PAUSED,STATUS_FINISHED,STATUS_ERROR,STATUS_ABORTED};
struct SPELLstatusInfo {SPELLexecutorStatus status;std::string condition,actionLabel;bool actionEnabled=false;explicit SPELLstatusInfo(SPELLexecutorStatus s):status(s){}};
struct SPELLsafeThreadOperations {explicit SPELLsafeThreadOperations(const char*){}};
struct SPELLexecutorUtils {static std::string statusToString(SPELLexecutorStatus s){return s==STATUS_LOADED?"LOADED":s==STATUS_PAUSED?"PAUSED":"UNINIT";}};
struct SPELLcontrollerIF {SPELLexecutorStatus getStatus(){return STATUS_PAUSED;}std::string getCondition(){return "";}};
struct Action {std::string getLabel(){return "";}bool isEnabled(){return false;}};
struct SPELLexecutor {SPELLcontrollerIF controller;Action action;static SPELLexecutor& instance(){static SPELLexecutor e;return e;}bool hasController(){return true;}SPELLcontrollerIF& getController(){return controller;}Action& getUserAction(){return action;}};
struct Buffer {void flush(){}};
struct SPELLserverCif {
#include "status_members.inc"
    Buffer* m_buffer=nullptr;
    std::atomic_bool closing{false},m_ready{true};
    std::mutex m_reconnectMutex,m_ackLock;
    std::condition_variable m_reconnectWake;
    unsigned long m_reconnectGeneration=0,m_timeoutAcknowledgeSec=30;
#if V08_ACK_CANDIDATE
    V08AcknowledgementOwners m_ackOwners;
#else
    std::vector<std::string> m_ackSequences;
#endif
    std::function<void(const SPELLipcMessage&)> on_send;
    SPELLserverCif(){m_sequence=0;m_sequenceStack=0;m_stMessage.setId(MessageId::MSG_ID_NOTIFICATION);m_stMessage.setType(MSG_TYPE_NOTIFY);m_stMessage.set(MessageField::FIELD_DATA_TYPE,"STATUS");m_stMessage.set(MessageField::FIELD_PROC_ID,"procedure#0");}
    bool isClosing(){return closing.load();}bool isManual(){return false;}unsigned getNumExecutions(){return 0;}
    void v08AvailableStackInto(std::string& out){out="procedure#0:1";}std::string getCodeName(){return "procedure";}
    void completeMessage(SPELLipcMessage&);void prepareMessage(SPELLipcMessage&,const std::string,SPELLipcMessageType_);
    void specificNotifyStatus(const SPELLstatusInfo&);SPELLipcMessage getPingMessage();
    void sendAcknowledged(const SPELLipcMessage&);bool waitAcknowledge(const SPELLipcMessage&,unsigned long);
    void receiveAck(const SPELLipcMessage&);
    void sendGUIMessage(const SPELLipcMessage& message){assert(on_send);on_send(message);}
    std::size_t pending(){
#if V08_ACK_CANDIDATE
        return m_ackOwners.pending();
#else
        std::lock_guard<std::mutex> lock(m_ackLock);return m_ackSequences.size();
#endif
    }
};
#include "ack_methods.inc"
#include "native_utils.inc"

// Run the real bridge callback with explicit output/client collaborators.
static std::atomic<unsigned> emitted{0};
static void emitFrame(const SPELLipcMessage&,const char*){++emitted;}
struct SPELLipcClientInterface {std::function<void(const SPELLipcMessage&)> deliver;void sendMessage(const SPELLipcMessage& message){assert(emitted.load()>0);deliver(message);}};
struct Peer {SPELLipcClientInterface* client=nullptr;void processMessage(const SPELLipcMessage&);};
#include "ack_bridge.inc"
static SPELLipcMessage ackFor(const SPELLipcMessage& message){SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);ack.setType(MSG_TYPE_ONEWAY);ack.setSender("GUI");ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));ack.set(MessageField::FIELD_PROC_ID,message.get(MessageField::FIELD_PROC_ID));ack.set(MessageField::FIELD_MSG_SEQUENCE,message.get(MessageField::FIELD_MSG_SEQUENCE));return ack;}
static SPELLipcMessage notification(SPELLserverCif& cif,const std::string& type){SPELLipcMessage message(MessageId::MSG_ID_NOTIFICATION);message.set(MessageField::FIELD_PROC_ID,"procedure#0");cif.prepareMessage(message,type,type=="LINE"?MSG_TYPE_NOTIFY_ASYNC:MSG_TYPE_NOTIFY);return message;}
static void waitFor(const std::function<bool()>& predicate){const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);while(!predicate()){assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();}}
static void emit(const SPELLipcMessage& message){for(unsigned char c:message.data())std::printf("%02x",c);std::puts("");}

int main(int argc,char** argv){
    assert(argc==2);const std::string mode=argv[1];SPELLserverCif cif;
    if(mode=="wrong-domain"){
        auto ping=cif.getPingMessage();cif.receiveAck(ackFor(ping));
        auto call=notification(cif,"CALL");
#if V08_ACK_CANDIDATE
        std::atomic<bool> sent{false},done{false};
        cif.on_send=[&](const SPELLipcMessage&){sent=true;};
        std::thread waiter([&]{cif.sendAcknowledged(call);done=true;});
        waitFor([&]{return sent.load();});
        // Feed the old ping again while CALL is actively waiting.
        cif.receiveAck(ackFor(ping));
        assert(!cif.m_ackOwners.consume(call.get(MessageField::FIELD_MSG_SEQUENCE),0));
        assert(!done.load());cif.receiveAck(ackFor(call));waiter.join();
        assert(done&&cif.pending()==0);
        std::printf("{\"ping\":\"%s\",\"call\":\"%s\",\"wrong_ack_settled\":false}\n",ping.get(MessageField::FIELD_MSG_SEQUENCE).c_str(),call.get(MessageField::FIELD_MSG_SEQUENCE).c_str());return 0;
#else
        const bool wrong=cif.waitAcknowledge(call,0);
        std::printf("{\"ping\":\"%s\",\"call\":\"%s\",\"wrong_ack_settled\":%s}\n",ping.get(MessageField::FIELD_MSG_SEQUENCE).c_str(),call.get(MessageField::FIELD_MSG_SEQUENCE).c_str(),wrong?"true":"false");return wrong?7:0;
#endif
    }
    if(mode=="wire"){
        emit(cif.getPingMessage());emit(notification(cif,"CALL"));
        emit(cif.getPingMessage());emit(notification(cif,"LINE"));
        emit(notification(cif,"RETURN"));emit(cif.getPingMessage());return 0;
    }
#if V08_ACK_CANDIDATE
    if(mode=="synchronous-bridge"){
        SPELLipcClientInterface client;Peer peer;peer.client=&client;
        client.deliver=[&](const SPELLipcMessage& ack){assert(cif.pending()==1);cif.receiveAck(ack);};
        cif.on_send=[&](const SPELLipcMessage& message){peer.processMessage(message);};
        cif.specificNotifyStatus(SPELLstatusInfo(STATUS_LOADED));
        cif.sendAcknowledged(notification(cif,"CALL"));
        cif.sendAcknowledged(notification(cif,"RETURN"));
        assert(cif.pending()==0&&emitted==3);std::puts("registered-before-synchronous-publish-and-ack");return 0;
    }
    if(mode=="out-of-order"){
        auto first=notification(cif,"STATUS"),second=notification(cif,"CALL");
        std::atomic<unsigned> sent{0};std::atomic<bool> firstDone{false},secondDone{false};
        cif.on_send=[&](const SPELLipcMessage&){++sent;};
        std::thread a([&]{cif.sendAcknowledged(first);firstDone=true;});
        std::thread b([&]{cif.sendAcknowledged(second);secondDone=true;});
        waitFor([&]{return sent==2;});assert(cif.pending()==2);
        cif.receiveAck(ackFor(second));cif.receiveAck(ackFor(second));
        waitFor([&]{return secondDone.load();});assert(!firstDone&&cif.pending()==1);
        cif.receiveAck(ackFor(second));assert(!firstDone);
        cif.receiveAck(ackFor(first));a.join();b.join();
        for(unsigned n=0;n<100000;++n){cif.receiveAck(ackFor(first));cif.receiveAck(ackFor(second));}
        assert(cif.pending()==0);std::puts("two-independent-waits-out-of-order-duplicates-no-inactive-credits");return 0;
    }
    if(mode=="cancel-errors"){
        auto call=notification(cif,"CALL");
        cif.on_send=[&](const SPELLipcMessage&){assert(cif.pending()==1);throw std::runtime_error("transport failed");};
        bool failed=false;try{cif.sendAcknowledged(call);}catch(const std::runtime_error&){failed=true;}
        assert(failed&&cif.pending()==0);cif.receiveAck(ackFor(call));assert(cif.pending()==0);
        std::atomic<bool> sent{false};cif.on_send=[&](const SPELLipcMessage&){sent=true;};
        auto next=notification(cif,"STATUS");std::thread waiter([&]{cif.sendAcknowledged(next);});
        waitFor([&]{return sent.load();});cif.closing=true;cif.m_reconnectWake.notify_all();waiter.join();
        cif.receiveAck(ackFor(next));assert(cif.pending()==0);
        cif.sendAcknowledged(notification(cif,"RETURN"));assert(cif.pending()==0);
        cif.closing=false;cif.m_ready=false;sent=false;
        std::thread unready([&]{cif.sendAcknowledged(notification(cif,"RETURN"));});
        waitFor([&]{return cif.pending()==1;});cif.closing=true;cif.m_reconnectWake.notify_all();unready.join();
        assert(!sent&&cif.pending()==0);
        std::puts("transport-error-close-cancel-and-closed-entry-release-tickets");return 0;
    }
    if(mode=="retry-generation"){
        auto call=notification(cif,"CALL");const auto original=call.data();unsigned sends=0;
        cif.on_send=[&](const SPELLipcMessage& message){
            ++sends;assert(message.data()==original&&cif.pending()==1);
            if(sends==1){cif.receiveAck(ackFor(call));std::lock_guard<std::mutex> lock(cif.m_reconnectMutex);++cif.m_reconnectGeneration;}
            else{assert(sends==2);}
        };
        cif.sendAcknowledged(call);assert(sends==2&&cif.pending()==0);
        // A prior-send ACK is valid for this SAME logical notification while
        // retrying. A cancelled/completed notification never owns a later key.
        {V08AcknowledgementOwners::Ticket ticket(cif.m_ackOwners,"owned-logical-message");ticket.arm(7);assert(cif.m_ackOwners.receive("owned-logical-message"));assert(!cif.m_ackOwners.consume("owned-logical-message",8));ticket.arm(8);assert(cif.m_ackOwners.consume("owned-logical-message",8));assert(!cif.m_ackOwners.receive("owned-logical-message"));}
        assert(cif.pending()==0);std::puts("one-logical-owner-across-retries-generation-aware-consume");return 0;
    }
    if(mode=="retry-timeout"){
        auto call=notification(cif,"CALL");const auto original=call.data();unsigned sends=0;
        cif.on_send=[&](const SPELLipcMessage& message){++sends;assert(message.data()==original&&cif.pending()==1);if(sends==2)cif.receiveAck(ackFor(call));};
        const auto start=std::chrono::steady_clock::now();cif.sendAcknowledged(call);
        const auto elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        assert(sends==2&&elapsed>=31&&elapsed<35&&cif.pending()==0);
        std::printf("{\"elapsed_seconds\":%.6f,\"original_timeout_seconds\":30,\"sends\":%u}\n",elapsed,sends);return 0;
    }
    if(mode=="lifetime"){
        V08AcknowledgementOwners owners;std::atomic<bool> running{true};
        std::thread receive([&]{while(running){owners.receive("same-component-lifetime-key");}});
        for(unsigned i=0;i<20000;++i){V08AcknowledgementOwners::Ticket ticket(owners,"same-component-lifetime-key");ticket.arm(i);owners.consume("same-component-lifetime-key",i);}
        running=false;receive.join();assert(owners.pending()==0);
        // Production keys never repeat; this deliberately stresses removal vs
        // lookup of the same stack address, without asserting receipt identity.
        bool duplicate=false;{V08AcknowledgementOwners::Ticket a(owners,"unique");try{V08AcknowledgementOwners::Ticket b(owners,"unique");}catch(const std::logic_error&){duplicate=true;}assert(owners.pending()==1);}
        assert(duplicate&&owners.pending()==0);std::puts("receive-unlink-stack-lifetime-and-duplicate-owner-refusal");return 0;
    }
    if(mode=="sequence-limit"){
        const auto maximum=static_cast<unsigned long>(LONG_MAX);cif.m_sequence=maximum-1;
        auto first=cif.getPingMessage();auto last=notification(cif,"CALL");
        assert(first.get(MessageField::FIELD_MSG_SEQUENCE)==std::to_string(maximum-1));
        assert(last.get(MessageField::FIELD_MSG_SEQUENCE)==std::to_string(maximum));
        SPELLipcMessage decoded;decoded.v08ReadData(last.data());
        assert(decoded.data()==last.data()&&decoded.get(MessageField::FIELD_MSG_SEQUENCE)==std::to_string(maximum));
        SPELLipcClientInterface client;Peer peer;peer.client=&client;
        client.deliver=[&](const SPELLipcMessage& ack){SPELLipcMessage copy;copy.v08ReadData(ack.data());assert(copy.get(MessageField::FIELD_MSG_SEQUENCE)==std::to_string(maximum));cif.receiveAck(copy);};
        cif.on_send=[&](const SPELLipcMessage& message){peer.processMessage(message);};cif.sendAcknowledged(last);
        unsigned refusals=0;for(unsigned i=0;i<3;++i){try{cif.getPingMessage();}catch(const std::overflow_error&){++refusals;}}
        assert(refusals==3&&cif.m_sequence==maximum+1&&cif.pending()==0);
        std::printf("{\"last_sequence\":\"%s\",\"saturated_refusals\":%u}\n",last.get(MessageField::FIELD_MSG_SEQUENCE).c_str(),refusals);return 0;
    }
#endif
    return 2;
}
