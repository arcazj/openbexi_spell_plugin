// SPDX-License-Identifier: GPL-3.0-or-later
// Force an asynchronous error to collide with a pending request's correlation ID.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcServerInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipcHelper.H"
#include <atomic>
#include <chrono>
#include <iostream>
#include <thread>

class ClientListener final:public SPELLipcInterfaceListener {
public:
    std::atomic_int errors{0},unexpected{0};
    void processMessage(const SPELLipcMessage& msg) override {
        if (msg.getId()=="MSG_ERROR" && msg.getType()==MSG_TYPE_ERROR &&
            msg.get("DataType")=="STATUS" && msg.get("ErrorReason")=="forced collision") ++errors;
        else ++unexpected;
    }
    SPELLipcMessage processRequest(const SPELLipcMessage&) override { return SPELLipcMessage(); }
    void processConnectionError(int,std::string,std::string) override {}
    void processConnectionClosed(int) override {}
};
class ServerListener final:public SPELLipcInterfaceListener {
public:
    SPELLipcServerInterface* server=nullptr;
    void processMessage(const SPELLipcMessage&) override {}
    SPELLipcMessage processRequest(const SPELLipcMessage& request) override {
        if (request.getId()=="REQ_EXEC_STATUS") {
            auto notification=SPELLipcHelper::createErrorResponse("MSG_ERROR",request);
            notification.setSequence(request.getSequence());
            notification.set("DataType","STATUS");
            notification.set("ExecutorStatus","ERROR");
            notification.set("ProcId","main#1");
            notification.set("ErrorReason","forced collision");
            server->sendMessage(request.getKey(),notification);
            auto response=SPELLipcHelper::createResponse("RSP_EXEC_STATUS",request);
            response.set("ExecutorStatus","ERROR");
            return response;
        }
        auto response=SPELLipcHelper::createErrorResponse("MSG_ERROR",request);
        response.set("ErrorReason","synchronous rejection");
        return response;
    }
    void processConnectionError(int,std::string,std::string) override {}
    void processConnectionClosed(int) override {}
};
int main() {
    ClientListener clientListener;ServerListener serverListener;
    SPELLipcServerInterface server("ERROR-ROUTING",0,0);serverListener.server=&server;
    server.initialize(&serverListener);server.connect();server.start();
    SPELLipcClientInterface client("ERROR-ROUTING","127.0.0.1",server.getPort());
    client.initialize(&clientListener);client.connect();
    int correct=0;
    // Repeated collisions also detect stale replies leaking into later requests.
    for (int i=0;i<16;++i) {
        SPELLipcMessage request("REQ_EXEC_STATUS");request.setType(MSG_TYPE_REQUEST);
        request.setSender("GUI");request.setReceiver("main#1");
        auto response=client.sendRequest(request,1000);
        if (response.getType()==MSG_TYPE_RESPONSE && response.getId()=="RSP_EXEC_STATUS" &&
            response.get("ExecutorStatus")=="ERROR") ++correct;
    }
    SPELLipcMessage request("REQ_REJECT");request.setType(MSG_TYPE_REQUEST);
    request.setSender("GUI");request.setReceiver("main#1");
    auto response=client.sendRequest(request,1000);
    const bool rejection=response.getType()==MSG_TYPE_ERROR && response.getId()=="MSG_ERROR" &&
        response.get("ErrorReason")=="synchronous rejection";
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
    while (clientListener.errors<16 && std::chrono::steady_clock::now()<deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    client.disconnect();server.disconnect();
    std::cout<<"CORRELATED_STATUS_RESPONSES "<<correct<<"/16\n"
             <<"ASYNC_ERROR_NOTIFICATIONS "<<clientListener.errors<<"/16\n"
             <<"SYNCHRONOUS_ERROR_RESPONSE "<<rejection<<"\n"
             <<"UNEXPECTED_NOTIFICATIONS "<<clientListener.unexpected<<std::endl;
    return correct==16 && clientListener.errors==16 && rejection && clientListener.unexpected==0 ? 0 : 1;
}
