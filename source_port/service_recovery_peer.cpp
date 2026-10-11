// SPDX-License-Identifier: GPL-3.0-or-later
// Original IPC integration fixture. This is not a replacement executor.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <csignal>
#include <vector>
#include <cerrno>
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
    if (argc!=3) return 2;
    const std::string scenario=argv[2];
    if (scenario!="failure" && scenario!="crash") return 2;
    const std::string prefix="/out/service-"+scenario,instance="native_resilient";
    ServerPeer peer;
    SPELLipcClientInterface client("SERVICE-RECOVERY-QUALIFICATION","127.0.0.1",std::stoi(argv[1]));
    peer.client=&client;
    auto require=[](bool ok,const std::string& reason) { if (!ok) throw std::runtime_error(reason); };
    try {
        client.initialize(&peer);client.connect();
        auto request=[&](const std::string& id) {
            SPELLipcMessage message(id);
            message.setType(MSG_TYPE_REQUEST);message.setSender("GUI");message.setReceiver("CTX");
            message.set(MessageField::FIELD_HOST,"service-recovery-qualification");
            message.set(MessageField::FIELD_PROC_ID,instance);
            auto result=client.sendRequest(message,7000);
            require(!result.isVoid(),"Service request timed out: "+id);
            if (id!=ContextMessages::REQ_SERVICE_INFO)
                require(result.getType()!=MSG_TYPE_ERROR,"Service request failed: "+result.dataStr());
            return result;
        };
        auto pids=[&]() {
            std::vector<int> values;
            std::ifstream input(prefix+"-starts.txt");int pid=0;
            while (input>>pid) { require(pid>1,"Invalid child PID");values.push_back(pid); }
            return values;
        };
        auto waitGeneration=[&](size_t generation) {
            auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(18);
            do {
                auto info=request(ContextMessages::REQ_SERVICE_INFO);
                const auto starts=pids();
                if (starts.size()==generation && info.get(MessageField::FIELD_EXEC_STATUS)=="RUNNING") {
                    const int pid=starts.back();
                    require(std::filesystem::read_symlink("/proc/"+std::to_string(pid)+"/exe")=="/out/SPELL-Service_v3",
                        "Restart did not launch the original native service executable");
                    return pid;
                }
                require(starts.size()<=generation,"Unexpected extra service restart");
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            } while(std::chrono::steady_clock::now()<deadline);
            throw std::runtime_error("Service generation did not become ready");
        };
        request(ContextMessages::REQ_GUI_LOGIN);
        const int first=waitGeneration(1);
        if (scenario=="failure") {
            std::ofstream trigger(prefix+"-trigger.txt");trigger<<"raise";
        } else {
            // The executable identity was checked immediately above; this PID
            // belongs to the isolated test process group, never a user service.
            require(::kill(first,SIGKILL)==0,"Could not inject owned child process loss");
        }
        const int second=waitGeneration(2);
        require(first!=second,"Watchdog did not replace the failed process");
        require(::kill(first,0)!=0 && errno==ESRCH,"Previous service child was not reaped");
        request(ContextMessages::REQ_GUI_LOGOUT);client.disconnect();
        std::cout<<"SERVICE_RESTART_VERIFIED "<<scenario<<" "<<first<<" "<<second<<std::endl;
        return 0;
    } catch(const SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; }
      catch(const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
