#include "SPELL_IPC/SPELLipcIncoming.H"
#include <cstdio>
#include <stdexcept>
static bool enabled=false;static size_t bytes=0,calls=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*,size_t size){if(enabled){bytes+=size;++calls;}}
class Peer:public SPELLipcInterfaceListener{
 public:
 void processMessage(const SPELLipcMessage&)override{}
 SPELLipcMessage processRequest(const SPELLipcMessage&)override{return SPELLipcMessage();}
 void processConnectionError(int,std::string,std::string)override{}
 void processConnectionClosed(int)override{}
};
class Message:public SPELLipcIncomingMessage{
 public:using SPELLipcIncomingMessage::SPELLipcIncomingMessage;
 std::string payload(){return getMessage().data();}
};
class Request:public SPELLipcIncomingRequest{
 public:using SPELLipcIncomingRequest::SPELLipcIncomingRequest;
 std::string payload(){return getMessage().data();}
};
int main(){
 Peer peer;SPELLipcMessage msg("MSG_NOTIFY");msg.setKey(97);msg.setSequence(123);
 for(auto key:{"ProcId","Csp","CodeName","DataType","StageId","StageTitle","MsgSequence","ExecutorStatus","User"})msg.set(key,"handoff_root:14");
 const auto wire=msg.data();SPELLmutex lock;SPELLipcChannel* channel=nullptr;
 {Message m("id","CTX-TO-EXECUTOR",msg,peer);Request r("req","CTX-TO-EXECUTOR",msg,lock,&channel,peer);
 msg.set("User","changed");if(m.payload()!=wire||r.payload()!=wire||m.getKey()!=97||r.getKey()!=97)return 2;}
 enabled=true;
 for(int i=0;i<10000;i++){Message m("id","CTX-TO-EXECUTOR",msg,peer);if(m.getKey()!=97)return 3;}
 enabled=false;std::printf("incoming allocations=%zu bytes=%zu message_size=%zu\n",calls,bytes,sizeof(SPELLipcMessage));
}
