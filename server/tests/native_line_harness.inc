// SPDX-License-Identifier: GPL-3.0-or-later
// Actual frozen/Candidate CIF methods; scheduler, clock and socket are fixtures.
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include <functional>
#include <cstdint>
static uint64_t line_digest=1469598103934665603ULL;
static unsigned pauses=0,sleeps=0,line_deliveries=0,native_sequence=0;
static void line_record(const std::string& text) {
    for(unsigned char byte:text) {line_digest^=byte;line_digest*=1099511628211ULL;}
}
struct SPELLsafeThreadOperations { explicit SPELLsafeThreadOperations(const char*){} };
struct SPELLexecutor {
    static SPELLexecutor& instance(){static SPELLexecutor e;return e;}
    void pause(){++pauses;}
};
struct LinePeer {
    bool fail=false;
    std::function<void()> reenter;
    void sendMessage(SPELLipcMessage& m) {
        if(fail){fail=false;throw SPELLipcError("fixture connection failure");}
        m.setKey(7);m.setSequence(native_sequence++);
        if(reenter) {
            const auto fields=m.v08Fields(); // Independent snapshot across reentry.
            auto call=std::move(reenter);reenter=nullptr;call();
            require(fields==m.v08Fields());
        }
        line_record(m.getId());line_record(m.getSender());line_record(m.getReceiver());
        line_record(std::to_string(m.getSequence()));line_record(std::to_string(m.getKey()));
        line_record(std::to_string(m.getType()));line_record(std::to_string(m.getCompressed()));
        for(const auto& field:m.v08Fields()){line_record(field.first);line_record(field.second);}
        ++line_deliveries;
    }
};
class SPELLserverCif {
public:
    SPELLipcMessage m_lnMessage{MessageId::MSG_ID_NOTIFICATION};
    int m_sequence=0,m_sequenceStack=0,executions=1;
    bool m_ready=true,manual=false;
    std::string stage="stage:first",code="long-procedure-entry.py",stack="long-procedure#0:14";
    LinePeer peer;LinePeer* m_ifc=&peer;
    SPELLserverCif(){m_lnMessage.set(MessageField::FIELD_PROC_ID,"long-procedure-origin#0");}
    std::string getProcId(){return "long-procedure-origin#0";}
    std::string getStage(){return stage;}
    std::string getCodeName(){return code;}
    std::string getAvailableStack(){return stack;}
    int getNumExecutions(){return executions;}
    bool isManual(){return manual;}
    void specificNotifyLine();
    void prepareMessage(SPELLipcMessage&,const std::string,SPELLipcMessageType_);
    void completeMessage(SPELLipcMessage&);
    void sendGUIMessage(const SPELLipcMessage&);
#if V08_STORAGE
    void sendGUIMessage(SPELLipcMessage&&);
#endif
};
#if V08_STORAGE
#include "line_message.H"
#endif
#define LOG_ERROR(x) do {} while(false)
#define usleep(x) (++sleeps)
#include "line_methods.inc"
#undef usleep
#undef LOG_ERROR
static void line_case(const std::string& mode) {
    SPELLserverCif cif;
    if(mode=="line_bench") {
        cif.specificNotifyLine();cif.specificNotifyLine();
        measure=true;
        for(int i=0;i<10000;++i)cif.specificNotifyLine();
        measure=false;
    } else {
        for(int i=0;i<256;++i) {
            cif.stage=i%3==0 ? "" : i%3==1 ? "stage:" : std::string("stage:")+char(i)+u8"é中🙂";
            cif.code="code-"+std::to_string(i);cif.stack="stack-"+std::to_string(i);
            cif.executions=i;cif.manual=i%2;
            cif.specificNotifyLine();
        }
        cif.stage=std::string(128*1024,'x');cif.specificNotifyLine();
        cif.stage="after-huge:fresh";cif.specificNotifyLine();
        cif.m_lnMessage.set("prototype-extra","preserve this field");cif.specificNotifyLine();
        cif.m_lnMessage=SPELLipcMessage(MessageId::MSG_ID_NOTIFICATION);
        cif.m_lnMessage.set(MessageField::FIELD_PROC_ID,"other-procedure#1");cif.specificNotifyLine();
        cif.peer.fail=true;cif.specificNotifyLine();cif.specificNotifyLine();
        cif.m_ready=false;cif.specificNotifyLine();cif.m_ready=true;cif.specificNotifyLine();
        cif.peer.reenter=[&cif]{cif.stage="nested:fresh";cif.specificNotifyLine();};
        cif.specificNotifyLine();
        require(pauses==1 && sleeps==1);
    }
}
