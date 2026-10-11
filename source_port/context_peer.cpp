// SPDX-License-Identifier: GPL-3.0-or-later
// Qualification peer using the original IPC client, serializer and constants.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Listener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <set>

class Peer final:public SPELLipcInterfaceListener {
public:
    void processMessage(const SPELLipcMessage& message) override {
        std::cout << "EVENT " << message.dataStr() << std::endl;
    }
    SPELLipcMessage processRequest(const SPELLipcMessage&) override { return SPELLipcMessage(); }
    void processConnectionError(int,std::string error,std::string reason) override {
        std::cerr << error << ": " << reason << std::endl;
    }
    void processConnectionClosed(int) override {}
};

int main(int argc,char** argv) {
    if (argc!=2 && argc!=3) return 2;
    Peer peer;
    SPELLipcClientInterface client("QUALIFICATION","127.0.0.1",std::stoi(argv[1]));
    try {
        client.initialize(&peer);
        client.connect();
        auto request=[&](const std::string& id) {
            SPELLipcMessage message(id);
            message.setType(MSG_TYPE_REQUEST);
            message.setSender("GUI"); message.setReceiver("LST");
            message.set(MessageField::FIELD_CTX_NAME,"example");
            message.set(MessageField::FIELD_GUI_MODE,"Development");
            SPELLipcMessage result=client.sendRequest(message,7000);
            std::cout << "RESPONSE " << result.dataStr() << std::endl;
            if (result.isVoid() || result.getType()==MSG_TYPE_ERROR)
                throw std::runtime_error("Original IPC request failed: "+id);
            return result;
        };
        request(ContextMessages::REQ_GUI_LOGIN);
        auto contexts=request(ContextMessages::REQ_CTX_LIST);
        if (contexts.get(MessageField::FIELD_CTX_LIST)!="example")
            throw std::runtime_error("Wrong context inventory");
        bool running=false;
        int contextPort=0;
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(12);
        while (std::chrono::steady_clock::now()<deadline) {
            auto info=request(ContextMessages::REQ_CTX_INFO);
            if (info.get(MessageField::FIELD_CTX_STATUS)==MessageValue::DATA_CTX_RUNNING) {
                if (std::stoi(info.get(MessageField::FIELD_CTX_PORT))<=0)
                    throw std::runtime_error("Context did not publish its client port");
                contextPort=std::stoi(info.get(MessageField::FIELD_CTX_PORT));
                running=true;break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(150));
        }
        if (!running) throw std::runtime_error("Context did not become RUNNING");
        std::cout << "CONTEXT_STARTED" << std::endl;
        if (argc==3) {
            const std::string mode=argv[2];
            const std::set<std::string> controls={"native_controls","native_pause","native_abort","native_prompt","native_failure","native_shared","native_child_parent","native_wait"};
            std::string command;
            if (mode=="--service" || mode=="--server")
                command="/out/server_peer "+std::to_string(contextPort)+(mode=="--service" ? " native_service --service" : " native_server");
            else if (mode=="--service-failure" || mode=="--service-crash")
                command="/out/service_recovery_peer "+std::to_string(contextPort)+" "+mode.substr(10);
            else if (controls.count(mode)) command="/out/controller_peer "+std::to_string(contextPort)+" "+mode;
            else throw std::runtime_error("Unknown context qualification scenario");
            if (std::system(command.c_str())!=0) throw std::runtime_error("Server executor peer failed");
        }
        request(ContextMessages::REQ_CLOSE_CTX);
        std::cout << "CONTEXT_CLOSED" << std::endl;
        request(ContextMessages::REQ_GUI_LOGOUT);
        client.disconnect();
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
      catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    return 1;
}
