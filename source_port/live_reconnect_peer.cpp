// SPDX-License-Identifier: GPL-3.0-or-later
// Crash only the verified context in this fixture's isolated process group.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_IPC/SPELLipc_Listener.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <cstdlib>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <unistd.h>

void require(bool ok,const std::string& why) { if (!ok) throw std::runtime_error(why); }
class Peer final:public SPELLipcInterfaceListener {
public:
    SPELLipcClientInterface* client=nullptr;
    void processMessage(const SPELLipcMessage& message) override {
        if (!message.hasField(MessageField::FIELD_MSG_SEQUENCE) || !client) return;
        SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);ack.setType(MSG_TYPE_ONEWAY);
        ack.setSender("GUI");ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));
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
int main(int argc,char** argv) {
    if (argc!=4) return 2;
    const bool service=std::string(argv[3])=="service";
    const std::string base=service ? "native_live_service" : "native_live_executor";
    const std::string instance=base+(service ? "" : "#1"),prefix="/out/"+base;
    const char* ownedGroup=std::getenv("OPENBEXI_QUALIFICATION_PGID");
    if (!ownedGroup) return 2;
    const int group=std::stoi(ownedGroup);
    if (group<=1) return 2;
    Peer contextPeer,listenerPeer;
    std::unique_ptr<SPELLipcClientInterface> context;
    SPELLipcClientInterface listener("LIVE-RECONNECT-LST","127.0.0.1",std::stoi(argv[2]));
    auto request=[&](SPELLipcClientInterface& client,const std::string& id,bool lst=false,const std::string& receiver="CTX") {
        SPELLipcMessage message(id);message.setType(MSG_TYPE_REQUEST);
        message.setSender("GUI");message.setReceiver(lst ? "LST" : receiver);
        message.set(MessageField::FIELD_PROC_ID,instance);
        message.set(MessageField::FIELD_CTX_NAME,"example");
        message.set(MessageField::FIELD_HOST,"live-reconnect-qualification");
        message.set(MessageField::FIELD_GUI_MODE,lst ? "Development" : "CONTROL");
        message.set(MessageField::FIELD_ARGS,"{}");
        message.set(MessageField::FIELD_OPEN_MODE,"{Automatic:True,Visible:True,Blocking:False}");
        return client.sendRequest(message,3000);
    };
    auto connectContext=[&](int port) {
        context=std::make_unique<SPELLipcClientInterface>("LIVE-RECONNECT-CTX","127.0.0.1",port);
        contextPeer.client=context.get();context->initialize(&contextPeer);context->connect();
        auto reply=request(*context,ContextMessages::REQ_GUI_LOGIN);
        require(!reply.isVoid() && reply.getType()!=MSG_TYPE_ERROR,"Context GUI login failed");
    };
    auto command=[&](const std::string& id) {
        SPELLipcMessage message(id);message.setType(MSG_TYPE_ONEWAY);
        message.setSender("GUI");message.setReceiver(instance);message.set(MessageField::FIELD_PROC_ID,instance);
        context->sendMessage(message);
    };
    auto info=[&] { return request(*context,service ? ContextMessages::REQ_SERVICE_INFO : ContextMessages::REQ_EXEC_INFO); };
    auto waitStatus=[&](const std::string& expected) {
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(12);
        do {
            auto reply=info();
            if (!reply.isVoid() && reply.getType()!=MSG_TYPE_ERROR && reply.get(MessageField::FIELD_EXEC_STATUS)==expected) return;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        } while(std::chrono::steady_clock::now()<deadline);
        throw std::runtime_error("Live process did not become "+expected);
    };
    auto lines=[&](const std::string& suffix) {
        std::ifstream file(prefix+suffix);int count=0;std::string line;
        while(std::getline(file,line)) ++count;
        return count;
    };
    try {
        listener.initialize(&listenerPeer);listener.connect();
        request(listener,ContextMessages::REQ_GUI_LOGIN,true);
        connectContext(std::stoi(argv[1]));
        if (!service) {
            auto reply=request(*context,ContextMessages::REQ_OPEN_EXEC);
            require(!reply.isVoid() && reply.getType()!=MSG_TYPE_ERROR,"Cannot open live executor");
            waitStatus("PAUSED");command(ExecutorMessages::MSG_CMD_RUN);
        }
        waitStatus("RUNNING");
        const auto ready=std::chrono::steady_clock::now()+std::chrono::seconds(4);
        while(lines("-progress.txt")<2 && std::chrono::steady_clock::now()<ready)
            std::this_thread::sleep_for(std::chrono::milliseconds(30));
        int pid=0,parent=0;std::ifstream boot(prefix+"-starts.txt");boot>>pid>>parent;
        require(pid>1 && parent>1 && parent!=::getpid(),"Invalid owned native process identifiers");
        require(std::filesystem::read_symlink("/proc/"+std::to_string(pid)+"/exe")==
            (service ? "/out/SPELL-Service_v3" : "/out/SPELL-Executor_v3"),"Child executable identity differs");
        require(std::filesystem::read_symlink("/proc/"+std::to_string(parent)+"/exe")=="/out/SPELL-Context","Parent is not native context");
        require(::getpgid(parent)==group && ::getpgid(pid)==group,"Process is outside owned session");
        require(lines("-progress.txt")>=2,"Live process never progressed");
        require(::kill(parent,SIGKILL)==0,"Cannot inject owned context loss");
        context->disconnect();context.reset();contextPeer.client=nullptr;
        std::cout<<"OWNED_CONTEXT_KILLED "<<parent<<" CHILD_SURVIVES "<<pid<<std::endl;
        // Wait for the listener's original delayed restart and fresh context PID.
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(24);
        int replacement=0,port=0;
        do {
            for (const auto& entry:std::filesystem::directory_iterator("/proc")) {
                const auto name=entry.path().filename().string();
                if (name.empty() || name.find_first_not_of("0123456789")!=std::string::npos) continue;
                const int candidate=std::stoi(name);std::error_code error;
                if (candidate!=parent && ::getpgid(candidate)==group &&
                    std::filesystem::read_symlink(entry.path()/"exe",error)=="/out/SPELL-Context") replacement=candidate;
            }
            auto response=request(listener,ContextMessages::REQ_CTX_INFO,true);
            if (replacement && response.get(MessageField::FIELD_CTX_STATUS)==MessageValue::DATA_CTX_RUNNING) {
                port=std::stoi(response.get(MessageField::FIELD_CTX_PORT));break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        } while(std::chrono::steady_clock::now()<deadline);
        require(port>0,"Listener did not replace context");
        connectContext(port);waitStatus("PAUSED");
        require(::kill(pid,0)==0,"Original native child did not survive");
        require(lines("-starts.txt")==1,"Context/watchdog launched a duplicate child");
        const int paused=lines("-progress.txt");
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        require(lines("-progress.txt")==paused,"Reconnected child progressed before explicit resume");
        auto response=request(*context,ContextMessages::REQ_ATTACH_EXEC);
        require(!response.isVoid() && response.getType()!=MSG_TYPE_ERROR,"Cannot regain native child control");
        command(ExecutorMessages::MSG_CMD_RUN);waitStatus("RUNNING");
        const auto resumed=std::chrono::steady_clock::now()+std::chrono::seconds(4);
        while (lines("-progress.txt")==paused && std::chrono::steady_clock::now()<resumed)
            std::this_thread::sleep_for(std::chrono::milliseconds(40));
        if (lines("-progress.txt")==paused) {
            auto state=request(*context,ExecutorMessages::REQ_EXEC_STATUS,false,instance);
            std::cerr<<"STALLED_CHILD_STATE "<<state.dataStr()<<std::endl;
            if (::getpgid(pid)==group && std::filesystem::exists("/proc/"+std::to_string(pid)+"/exe")) {
                ::kill(pid,SIGUSR1);
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                const auto diagnostic="timeout 8 /usr/bin/gdb --batch -ex 'set pagination off' -ex 'thread apply all bt' -p "+
                    std::to_string(pid)+" >"+prefix+"-native-stacks.txt 2>&1";
                std::system(diagnostic.c_str());
            }
        }
        require(lines("-progress.txt")>paused,"Reconnected native child did not resume");
        std::cout<<"RECONNECTED_CHILD_RESUMED "<<argv[3]<<std::endl;
        // Upstream context shutdown deliberately killAll()s ordinary procedures.
        // Exercise their normal Close command while this GUI still acknowledges
        // notifications; services are gracefully closed by context shutdown.
        if (!service) {
            auto closed=request(*context,ContextMessages::REQ_CLOSE_EXEC);
            require(!closed.isVoid() && closed.getType()!=MSG_TYPE_ERROR,"Cannot close reconnected procedure");
            std::cout<<"RECONNECTED_PROCEDURE_CLOSED"<<std::endl;
        }
        request(*context,ContextMessages::REQ_GUI_LOGOUT);context->disconnect();
        request(listener,ContextMessages::REQ_GUI_LOGOUT,true);listener.disconnect();
        std::cout<<"LIVE_CONTEXT_RECONNECT_VERIFIED "<<argv[3]<<" "<<pid<<" "<<replacement<<std::endl;
        return 0;
    } catch(const SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; }
      catch(const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
