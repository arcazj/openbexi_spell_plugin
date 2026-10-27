// SPDX-License-Identifier: GPL-3.0-or-later
#include <atomic>
#include <cassert>
#include <cstdio>
#include <string>
#include <thread>
#include <vector>
static std::atomic<bool> measuring{false};
static std::atomic<unsigned long> allocations{0};
static void allocated(const volatile void*,size_t) {
    if(measuring.load(std::memory_order_relaxed))++allocations;
}
static void released(const volatile void*) {}
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*,size_t), void (*)(const volatile void*));
namespace MessageId {
const std::string MSG_ID_NOTIFICATION="MSG_NOTIFICATION", MSG_ID_SET_UACTION="MSG_SET_UACTION",
MSG_ID_DISMISS_UACTION="MSG_DISMISS_UACTION", MSG_ID_ENABLE_UACTION="MSG_ENABLE_UACTION",
MSG_ID_DISABLE_UACTION="MSG_DISABLE_UACTION";
}
namespace ExecutorMessages { const std::string MSG_NOTIF_EXEC_CLOSE="MSG_NOTIF_EXEC_CLOSE"; }
namespace MessageField { const std::string FIELD_ACTION_LABEL="label",FIELD_ACTION_SEVERITY="severity",FIELD_ERROR="error",FIELD_REASON="reason"; }
namespace MessageValue { const std::string DATA_SEVERITY_WARN="WARN",DATA_SEVERITY_ERROR="ERROR"; }
namespace LanguageConstants { enum {INFORMATION,WARNING,ERROR}; }
enum {MSG_TYPE_ERROR=3, STATUS_ERROR=7};
#define DEBUG(x) do {} while(false)
#define LOG_INFO(x) do {} while(false)
struct SPELLipcMessage {
    std::string id,severity;
    int type=0;
    std::string getId()const{return id;}
    bool v08HasId(const std::string& value)const{return id==value;}
    int getType()const{return type;}
    std::string get(const std::string& field)const{
        return field==MessageField::FIELD_ACTION_SEVERITY?severity:field;
    }
};
struct Action {
    bool enabled=false;unsigned int severity=0;std::string label;
    void setLabel(const std::string& value){label=value;}
    void setSeverity(unsigned int value){severity=value;}
    void enable(bool value){enabled=value;}
    void reset(){enabled=false;label.clear();severity=0;}
};
struct Model {
    Action action;unsigned errors=0;
    Action& getUserAction(){return action;}
    void setError(const std::string&,const std::string&){++errors;}
};
struct Event {bool set_value=false;void set(){set_value=true;}};
struct SPELLexecutor {
    Model m_model;Event m_executorLoggedOutEvent;
    unsigned notifications=0,forwarded=0,status=0;
    Model& getModel(){return m_model;}
    void executorNotification(const SPELLipcMessage&){++notifications;}
    void forwardMessageToClient(const SPELLipcMessage&){++forwarded;}
    void executorStatusChanged(int,const std::string&,const std::string&){++status;}
    void processMessageFromExecutor(const SPELLipcMessage&);
};
#include "callback.inc"
static void semantics() {
    SPELLexecutor e;
    e.processMessageFromExecutor({ExecutorMessages::MSG_NOTIF_EXEC_CLOSE,"",0});
    assert(e.m_executorLoggedOutEvent.set_value && e.forwarded==0);
    e.processMessageFromExecutor({MessageId::MSG_ID_NOTIFICATION,"",0});
    assert(e.notifications==1 && e.forwarded==1);
    for(const auto& severity:{"INFO","WARN","ERROR"}) {
        e.processMessageFromExecutor({MessageId::MSG_ID_SET_UACTION,severity,0});
        assert(e.m_model.action.enabled && e.m_model.action.label=="label");
    }
    assert(e.m_model.action.severity==LanguageConstants::ERROR);
    e.processMessageFromExecutor({MessageId::MSG_ID_DISABLE_UACTION,"",0});
    assert(!e.m_model.action.enabled);
    e.processMessageFromExecutor({MessageId::MSG_ID_ENABLE_UACTION,"",0});
    assert(e.m_model.action.enabled);
    e.processMessageFromExecutor({MessageId::MSG_ID_DISMISS_UACTION,"",0});
    assert(!e.m_model.action.enabled && e.m_model.action.label.empty());
    e.processMessageFromExecutor({"unknown","",MSG_TYPE_ERROR});
    assert(e.m_model.errors==1 && e.status==1 && e.forwarded==8);
}
int main() {
    assert(__sanitizer_install_malloc_and_free_hooks(allocated,released)>0);
    semantics();
    std::vector<std::thread> threads;
    for(int i=0;i<16;++i)threads.emplace_back(semantics);
    for(auto& thread:threads)thread.join();
    SPELLexecutor e;SPELLipcMessage msg{MessageId::MSG_ID_NOTIFICATION,"",0};
    allocations=0;measuring=true;
    for(int i=0;i<10000;++i)e.processMessageFromExecutor(msg);
    measuring=false;
    assert(e.notifications==10000 && e.forwarded==10000);
    std::printf("{\"semantics\":true,\"allocations\":%lu}\n",allocations.load());
}
