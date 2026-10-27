// SPDX-License-Identifier: GPL-3.0-or-later
// Exact upstream constants; only callback collaborators are fixtures.
namespace MessageId {
static const std::string MSG_ID_PROMPT_START("MSG_PROMPT_START"), MSG_ID_PROMPT_END("MSG_PROMPT_END");
}
namespace ExecutorMessages {
static const std::string MSG_NOTIF_EXEC_CLOSE("MSG_NOTIF_EXEC_CLOSE");
}
struct RoutingController {
    unsigned calls=0;
    bool fail=false;
    void processMessageFromExecutor(const SPELLipcMessage&) {++calls;if(fail)throw 7;}
};
struct SPELLexecutorIPC {
    RoutingController m_controller;
    unsigned observers=0;
    void notifyMessage(const SPELLipcMessage&) {++observers;}
    void processMessage(const SPELLipcMessage& msg);
};
#define TICK_IN do {} while(false)
#define TICK_OUT do {} while(false)
#include "routing_method.inc"
#undef TICK_IN
#undef TICK_OUT
static void routing_test(bool bench) {
    SPELLexecutorIPC router;
    SPELLipcMessage message("MSG_NOTIFICATION");
    if(bench) {
        measure=true;
        for(int n=0;n<10000;++n)router.processMessage(message);
        measure=false;
        require(router.m_controller.calls==10000 && router.observers==10000);
        return;
    }
    for(const auto& id: {std::string("MSG_NOTIFICATION"), MessageId::MSG_ID_PROMPT_START,
                        MessageId::MSG_ID_PROMPT_END, ExecutorMessages::MSG_NOTIF_EXEC_CLOSE,
                        std::string(""), std::string("unknown\0message",15), std::string(u8"é中🙂")}) {
        message.setId(id);message.set("payload","unchanged");
        const auto before=message.data();
        router.m_controller.calls=router.observers=0;
        router.processMessage(message);
        require(router.m_controller.calls==unsigned(id!=MessageId::MSG_ID_PROMPT_START && id!=MessageId::MSG_ID_PROMPT_END));
        require(router.observers==unsigned(id!=ExecutorMessages::MSG_NOTIF_EXEC_CLOSE));
        require(message.data()==before);
    }
    message.setId("MSG_NOTIFICATION");router.m_controller.fail=true;
    const auto observers=router.observers;
    try {router.processMessage(message);require(false);} catch(int n) {require(n==7);}
    require(router.observers==observers);
}
