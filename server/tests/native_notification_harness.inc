// SPDX-License-Identifier: GPL-3.0-or-later
// Compile the exact upstream/candidate callback against the real message class.
// Only the model, context and status collaborators are fixtures.
namespace MessageField {
static const std::string FIELD_DATA_TYPE("DataType"), FIELD_EXEC_STATUS("ExecutorStatus"),
    FIELD_STAGE_ID("StageId"), FIELD_STAGE_TL("StageTitle"), FIELD_CSP("Csp"), FIELD_CODE_NAME("CodeName");
}
namespace MessageValue {
static const std::string DATA_TYPE_STATUS("STATUS"), DATA_TYPE_LINE("LINE"),
    DATA_TYPE_CALL("CALL"), DATA_TYPE_RETURN("RETURN");
}
enum SPELLexecutorStatus { STATUS_ERROR, STATUS_RUNNING };
struct SPELLdataHelper {
    static SPELLexecutorStatus stringToExecutorStatus(const std::string& value) {
        return value=="ERROR" ? STATUS_ERROR : STATUS_RUNNING;
    }
};
// Preserve the upstream calls at the error boundary; their trim implementation
// is independent of the ownership-only change being exercised.
struct NotificationUtils {
    static void trim(std::string& value) {
        const auto first=value.find_first_not_of(' ');
        if(first==std::string::npos) {value.clear();return;}
        value=value.substr(first,value.find_last_not_of(' ')-first+1);
    }
};
struct SPELLexecutorOperation {
    enum { EXEC_OP_SUMMARY } type;
    std::string instanceId, originId, groupId, stageId, stageTitle;
};
struct SPELLcontext {
    unsigned summaries=0;
    SPELLexecutorOperation last;
    static SPELLcontext& instance() {static SPELLcontext context;return context;}
    void notifyExecutorOperation(const SPELLexecutorOperation& op) {++summaries;last=op;}
};
struct NotificationModel {
    std::string stack, code, stageId, stageTitle;
    void setStack(const std::string& s,const std::string& c) {stack=s;code=c;}
    void setStage(const std::string& id,const std::string& title) {stageId=id;stageTitle=title;}
    const std::string& getStageId() const {return stageId;}
    const std::string& getStageTitle() const {return stageTitle;}
    std::string getInstanceId() const {return "exec";}
    std::string getOriginId() const {return "origin";}
    std::string getGroupId() const {return "group";}
};
struct SPELLexecutor {
    NotificationModel m_model;
    unsigned statuses=0;
    SPELLexecutorStatus status=STATUS_RUNNING;
    std::string error,reason;
    NotificationModel& getModel() {return m_model;}
    void executorStatusChanged(SPELLexecutorStatus s,const std::string& e="",const std::string& r="") {
        ++statuses;status=s;error=e;reason=r;
    }
    void executorNotification(const SPELLipcMessage& nmsg);
};
static unsigned notification_errors=0;
#define SPELLutils NotificationUtils
#define DEBUG(x)
#define LOG_INFO(x) do {} while(false)
#define LOG_ERROR(x) do {++notification_errors;} while(false)
#include "notification_method.inc"
#undef LOG_ERROR
#undef LOG_INFO
#undef DEBUG
#undef SPELLutils

static void notification_test(bool bench) {
    SPELLipcMessage msg("MSG_NOTIFY");
    msg.setSender("handoff_procedure_root#0");msg.setType(MSG_TYPE_NOTIFY);
    msg.set("DataType","LINE");msg.set("Csp","1");msg.set("CodeName","code");
    msg.set("StageId","stage");msg.set("StageTitle","title");
    msg.set("ExtraA","a");msg.set("ExtraB","b");msg.set("ExtraC","c");
    if(bench) {
        for(const auto& field:{"Csp","CodeName","StageId","StageTitle"}) msg.set(field,std::string(200,'x'));
    }
    SPELLexecutor executor;
    executor.executorNotification(msg);
    if(bench) {
        measure=true;
        for(int n=0;n<10000;++n) executor.executorNotification(msg);
        measure=false;return;
    }
    const auto original=msg.data();
    auto& context=SPELLcontext::instance();
    require(context.summaries==1 && context.last.stageId=="stage");
    executor.executorNotification(msg);
    require(context.summaries==1 && msg.data()==original);
    for(const auto& kind:{"CALL","RETURN"}) {
        msg.set("DataType",kind);msg.set("Csp",kind);
        executor.executorNotification(msg);require(executor.m_model.stack==kind);
    }
    msg.setType(MSG_TYPE_NOTIFY_ASYNC);msg.set("DataType","LINE");msg.set("StageTitle",u8"é中🙂");
    executor.executorNotification(msg);require(context.summaries==2 && context.last.stageTitle==u8"é中🙂");
    msg.set("DataType","STATUS");msg.set("ExecutorStatus","ERROR");
    msg.set("ErrorMsg"," error ");msg.set("ErrorReason"," reason ");
    const auto error_source=msg.data();
    executor.executorNotification(msg);
    require(executor.status==STATUS_ERROR && executor.error=="error" && executor.reason=="reason");
    require(msg.data()==error_source);
    msg.set("ErrorMsg","");msg.set("ErrorReason","");executor.executorNotification(msg);
    require(executor.error.empty() && executor.reason.empty());
    msg.set("ExecutorStatus","RUNNING");executor.executorNotification(msg);
    require(executor.statuses==3 && executor.status==STATUS_RUNNING);
    msg.setType(MSG_TYPE_REQUEST);executor.executorNotification(msg);require(notification_errors==1);
    msg.setType(MSG_TYPE_NOTIFY);msg.set("DataType","UNKNOWN");executor.executorNotification(msg);
    require(executor.statuses==3 && context.summaries==2);
    // Missing fields keep the old empty-string behavior; borrowed values cannot
    // outlive this call or alias subsequent mutations of the source message.
    SPELLipcMessage missing("MSG_NOTIFY");missing.setType(MSG_TYPE_NOTIFY);
    missing.set("DataType","LINE");executor.executorNotification(missing);
    require(executor.m_model.stack.empty() && executor.m_model.code.empty());
    msg.set("DataType","LINE");msg.set("Csp",std::string(200,'q'));
    executor.executorNotification(msg);msg.set("Csp","changed");
    require(executor.m_model.stack==std::string(200,'q'));

}
