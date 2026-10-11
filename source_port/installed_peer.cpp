// SPDX-License-Identifier: GPL-3.0-or-later
// Installed-artifact qualification through the original IPC protocol.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_IPC/SPELLipc_Listener.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>

class Peer final:public SPELLipcInterfaceListener {
public:
    SPELLipcClientInterface* client=nullptr;
    void processMessage(const SPELLipcMessage& message) override {
        if (message.getType()!=MSG_TYPE_NOTIFY || !client) return;
        SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);
        ack.setType(MSG_TYPE_ONEWAY);ack.setSender("GUI");
        ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));
        ack.set(MessageField::FIELD_PROC_ID,message.get(MessageField::FIELD_PROC_ID));
        ack.set(MessageField::FIELD_MSG_SEQUENCE,message.get(MessageField::FIELD_MSG_SEQUENCE));
        client->sendMessage(ack);
    }
    SPELLipcMessage processRequest(const SPELLipcMessage&) override { return SPELLipcMessage(); }
    void processConnectionError(int,std::string error,std::string reason) override {
        std::cerr<<error<<": "<<reason<<std::endl;
    }
    void processConnectionClosed(int) override {}
};

SPELLipcMessage request(SPELLipcClientInterface& client,const std::string& id,bool listener=false) {
    SPELLipcMessage message(id);message.setType(MSG_TYPE_REQUEST);
    message.setSender("GUI");message.setReceiver(listener ? "LST" : "CTX");
    message.set(MessageField::FIELD_CTX_NAME,"example");
    message.set(MessageField::FIELD_HOST,"installed-artifact-qualification");
    message.set(MessageField::FIELD_GUI_MODE,listener ? "Development" : "CONTROL");
    message.set(MessageField::FIELD_PROC_ID,"installed_native#1");
    message.set(MessageField::FIELD_ARGS,"{'value':21}");
    message.set(MessageField::FIELD_OPEN_MODE,"{Automatic:True,Visible:True,Blocking:False}");
    auto result=client.sendRequest(message,10000);
    if (result.isVoid() || result.getType()==MSG_TYPE_ERROR)
        throw std::runtime_error("Installed IPC request failed: "+id+" "+result.dataStr());
    return result;
}

int main(int argc,char** argv) {
    if (argc!=2) return 2;
    Peer listenerPeer,contextPeer;
    SPELLipcClientInterface listener("INSTALLED-LISTENER","127.0.0.1",std::stoi(argv[1]));
    try {
        listenerPeer.client=&listener;listener.initialize(&listenerPeer);listener.connect();
        request(listener,ContextMessages::REQ_GUI_LOGIN,true);
        int port=0;
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(15);
        while (std::chrono::steady_clock::now()<deadline) {
            auto info=request(listener,ContextMessages::REQ_CTX_INFO,true);
            if (info.get(MessageField::FIELD_CTX_STATUS)==MessageValue::DATA_CTX_RUNNING) {
                port=std::stoi(info.get(MessageField::FIELD_CTX_PORT));break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        if (port<=0) throw std::runtime_error("Installed context did not start");
        SPELLipcClientInterface context("INSTALLED-CONTEXT","127.0.0.1",port);
        contextPeer.client=&context;context.initialize(&contextPeer);context.connect();
        request(context,ContextMessages::REQ_GUI_LOGIN);
        request(context,ContextMessages::REQ_OPEN_EXEC);
        bool ran=false,finished=false;
        deadline=std::chrono::steady_clock::now()+std::chrono::seconds(15);
        while (std::chrono::steady_clock::now()<deadline) {
            auto info=request(context,ContextMessages::REQ_EXEC_INFO);
            const auto status=info.get(MessageField::FIELD_EXEC_STATUS);
            if (status=="PAUSED" && !ran) {
                SPELLipcMessage command(ExecutorMessages::MSG_CMD_RUN);
                command.setType(MSG_TYPE_ONEWAY);command.setSender("GUI");
                command.setReceiver("installed_native#1");
                command.set(MessageField::FIELD_PROC_ID,"installed_native#1");
                context.sendMessage(command);ran=true;
            }
            if (status=="FINISHED") { finished=true;break; }
            if (status=="ERROR" || status=="ABORTED")
                throw std::runtime_error("Installed procedure failed: "+info.dataStr());
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        if (!ran || !finished) throw std::runtime_error("Installed procedure did not complete visible Run");
        request(context,ContextMessages::REQ_CLOSE_EXEC);
        request(context,ContextMessages::REQ_GUI_LOGOUT);context.disconnect();contextPeer.client=nullptr;
        request(listener,ContextMessages::REQ_CLOSE_CTX,true);
        request(listener,ContextMessages::REQ_GUI_LOGOUT,true);listener.disconnect();listenerPeer.client=nullptr;
        std::cout<<"INSTALLED_LISTENER_CONTEXT_EXECUTOR_CLOSED"<<std::endl;
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; }
      catch (const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
