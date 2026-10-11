// SPDX-License-Identifier: GPL-3.0-or-later
// Original IPC integration fixture. This is not a replacement executor.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <thread>

class ServerPeer final:public SPELLipcInterfaceListener {
public:
    SPELLipcClientInterface* client=nullptr;
    void processMessage(const SPELLipcMessage& message) override {
        std::cout << "EVENT " << message.dataStr() << std::endl;
        if (message.hasField(MessageField::FIELD_MSG_SEQUENCE)) {
            SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);
            ack.setType(MSG_TYPE_ONEWAY);
            ack.setSender("GUI"); ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));
            ack.set(MessageField::FIELD_PROC_ID,message.get(MessageField::FIELD_PROC_ID));
            ack.set(MessageField::FIELD_MSG_SEQUENCE,message.get(MessageField::FIELD_MSG_SEQUENCE));
            client->sendMessage(ack);
        }
    }
    SPELLipcMessage processRequest(const SPELLipcMessage& message) override {
        std::cerr << "UNEXPECTED_REQUEST " << message.dataStr() << std::endl;
        return SPELLipcMessage();
    }
    void processConnectionError(int,std::string error,std::string reason) override {
        std::cerr << error << ": " << reason << std::endl;
    }
    void processConnectionClosed(int) override {}
};

int main(int argc,char** argv) {
    if (argc!=3 && argc!=4) return 2;
    const bool service=argc==4 && std::string(argv[3])=="--service";
    ServerPeer peer;
    SPELLipcClientInterface client("SERVER-QUALIFICATION","127.0.0.1",std::stoi(argv[1]));
    peer.client=&client;
    const std::string instance=std::string(argv[2])+(service ? "" : "#1");
    try {
        client.initialize(&peer); client.connect();
        auto request=[&](const std::string& id) {
            SPELLipcMessage message(id);
            message.setType(MSG_TYPE_REQUEST);
            message.setSender("GUI"); message.setReceiver("CTX");
            message.set(MessageField::FIELD_HOST,"qualification");
            message.set(MessageField::FIELD_PROC_ID,instance);
            message.set(MessageField::FIELD_GUI_MODE,"CONTROL");
            message.set(MessageField::FIELD_ARGS,"{'value':21}");
            message.set(MessageField::FIELD_OPEN_MODE,"{Automatic:True,Visible:True,Blocking:False}");
            SPELLipcMessage result=client.sendRequest(message,10000);
            std::cout << "RESPONSE " << result.dataStr() << std::endl;
            if (result.isVoid() || (result.getType()==MSG_TYPE_ERROR && !(service && id==ContextMessages::REQ_SERVICE_INFO)))
                throw std::runtime_error("Original IPC request failed: "+id);
            return result;
        };
        request(ContextMessages::REQ_GUI_LOGIN);
        if (!service) request(ContextMessages::REQ_OPEN_EXEC);
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(15);
        bool finished=false,runSent=false;
        while (std::chrono::steady_clock::now()<deadline) {
            auto info=request(service ? ContextMessages::REQ_SERVICE_INFO : ContextMessages::REQ_EXEC_INFO);
            const std::string status=info.get(MessageField::FIELD_EXEC_STATUS);
            if (service && status=="RUNNING" && std::filesystem::exists("/out/service-pid.txt") &&
                std::filesystem::exists("/out/service-result.txt")) { finished=true;break; }
            if (!service && status=="FINISHED") { finished=true;break; }
            if (!service && status=="PAUSED" && !runSent) {
                SPELLipcMessage command(ExecutorMessages::MSG_CMD_RUN);
                command.setType(MSG_TYPE_ONEWAY);
                command.setSender("GUI"); command.setReceiver(instance);
                command.set(MessageField::FIELD_PROC_ID,instance);
                client.sendMessage(command);
                runSent=true;
                std::cout << "SERVER_RUN_SENT" << std::endl;
            }
            if (status=="ERROR" || status=="ABORTED")
                throw std::runtime_error("Executor failed: "+status);
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        if (!finished) throw std::runtime_error("Executor did not finish");
        if (service) {
            int pid=0;
            std::ifstream("/out/service-pid.txt") >> pid;
            if (pid<=0 || std::filesystem::read_symlink("/proc/"+std::to_string(pid)+"/exe")!="/out/SPELL-Service_v3")
                throw std::runtime_error("Service result did not come from the real service executable");
            std::cout << "SERVICE_EXECUTABLE_VERIFIED " << pid << std::endl;
            std::cout << "NATIVE_SERVICE_RUNNING" << std::endl;
        } else {
            std::cout << "SERVER_EXECUTOR_FINISHED" << std::endl;
            request(ContextMessages::REQ_CLOSE_EXEC);
            std::cout << "SERVER_EXECUTOR_CLOSED" << std::endl;
        }
        request(ContextMessages::REQ_GUI_LOGOUT);
        client.disconnect();
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
      catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    return 1;
}
