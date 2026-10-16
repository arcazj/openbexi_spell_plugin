// SPDX-License-Identifier: GPL-3.0-or-later
// Independent controller client using the original SPELL IPC protocol.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Context.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <chrono>
#include <atomic>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <thread>

using Fields=std::initializer_list<std::pair<std::string,std::string>>;
// The production IPC client dispatches messages to independent worker threads.
// This oracle must observe TCP arrival order, not worker scheduling order.
class OrderedControllerClient final:public SPELLipcClientInterface {
    std::ofstream wire;
public:
    OrderedControllerClient(const std::string& name,const std::string& host,int port,
                            const std::string& evidence)
        :SPELLipcClientInterface(name,host,port),wire(evidence) {}
    void incomingMessage(const SPELLipcMessage& message) override {
        wire << message.dataStr() << std::endl;
        if (m_connected && m_listener) m_listener->processMessage(message);
    }
};
static void require(bool ok,const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
class ControllerPeer final:public SPELLipcInterfaceListener {
public:
    SPELLipcClientInterface* client=nullptr;
    std::atomic_bool rejectedJump{false};
    std::atomic_bool finalOutput{false}, terminalSeen{false}, outputOrdered{false};
    void processMessage(const SPELLipcMessage& message) override {
        if (message.hasField(MessageField::FIELD_TEXT) &&
            message.get(MessageField::FIELD_TEXT).find("NATIVE_OUTPUT_BARRIER")!=std::string::npos)
            finalOutput=true;
        if (message.hasField(MessageField::FIELD_PROC_ID) &&
            message.get(MessageField::FIELD_PROC_ID)=="native quoted ' space#1" &&
            message.hasField(MessageField::FIELD_EXEC_STATUS) &&
            message.get(MessageField::FIELD_EXEC_STATUS)=="FINISHED") {
            outputOrdered=finalOutput.load(); terminalSeen=true;
        }
        if (message.hasField(MessageField::FIELD_TEXT) &&
            message.get(MessageField::FIELD_TEXT).find("Unable to go to line -1")!=std::string::npos)
            rejectedJump.store(true);
        if (message.getType()!=MSG_TYPE_NOTIFY || !message.hasField(MessageField::FIELD_MSG_SEQUENCE)) return;
        SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);
        ack.setType(MSG_TYPE_ONEWAY);
        ack.setSender("GUI"); ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));
        ack.set(MessageField::FIELD_PROC_ID,message.get(MessageField::FIELD_PROC_ID));
        ack.set(MessageField::FIELD_MSG_SEQUENCE,message.get(MessageField::FIELD_MSG_SEQUENCE));
        client->sendMessage(ack);
    }
    SPELLipcMessage processRequest(const SPELLipcMessage&) override { return SPELLipcMessage(); }
    void processConnectionError(int,std::string error,std::string reason) override {
        std::cerr << error << ": " << reason << std::endl;
    }
    void processConnectionClosed(int) override {}
};
int main(int argc,char** argv) {
    if (argc!=3) return 2;
    const std::string procedure=argv[2],instance=procedure+"#1";
    ControllerPeer peer;
    OrderedControllerClient client("CONTROLLER-QUALIFICATION","127.0.0.1",std::stoi(argv[1]),
                                 "/out/"+procedure+"-wire.log");
    peer.client=&client;
    try {
        client.initialize(&peer); client.connect();
        auto message=[&](const std::string& id,bool context,Fields fields) {
            SPELLipcMessage result(id);
            result.setSender("GUI"); result.setReceiver(context ? "CTX" : instance);
            result.set(MessageField::FIELD_PROC_ID,instance);
            for (const auto& field:fields) result.set(field.first,field.second);
            return result;
        };
        auto request=[&](const std::string& id,bool context=false,Fields fields={}) {
            auto msg=message(id,context,fields); msg.setType(MSG_TYPE_REQUEST);
            auto reply=client.sendRequest(msg,7000);
            require(!reply.isVoid() && reply.getType()!=MSG_TYPE_ERROR,"IPC failure: "+id+" "+reply.dataStr());
            return reply;
        };
        auto command=[&](const std::string& id,Fields fields={}) {
            auto msg=message(id,false,fields); msg.setType(MSG_TYPE_ONEWAY);
            client.sendMessage(msg);
            std::cout << "COMMAND " << id << std::endl;
        };
        auto waitStatus=[&](const std::string& wanted,int line=0) {
            auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);
            std::string last;
            do {
                // Ask the executor directly, rather than trusting cached context status.
                auto reply=request(ExecutorMessages::REQ_EXEC_STATUS);
                const auto status=reply.get(MessageField::FIELD_EXEC_STATUS);
                last=status+" "+reply.get(MessageField::FIELD_CSP);
                const auto stack=reply.get(MessageField::FIELD_CSP);
                const auto location=procedure+":"+std::to_string(line);
                if (status==wanted && (!line || stack==location || stack.find(location+"/")!=std::string::npos)) {
                    std::cout << "OBSERVED " << last << std::endl; return;
                }
                require(status!="ERROR" || wanted=="ERROR","Executor failed: "+reply.dataStr());
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            } while (std::chrono::steady_clock::now()<deadline);
            throw std::runtime_error("Expected "+wanted+" at "+std::to_string(line)+", got "+last);
        };
        auto variables=[&]() {
            require(request(ExecutorMessages::REQ_WVARIABLES_ENABLED).get(MessageField::FIELD_WVARIABLES_ENABLED)=="False",
                "Fixture expects on-demand variable inspection with automatic watching disabled");
            auto reply=request(ExecutorMessages::REQ_GET_VARIABLES);
            std::istringstream names(reply.get(MessageField::FIELD_VARIABLE_NAME));
            std::istringstream values(reply.get(MessageField::FIELD_VARIABLE_VALUE));
            std::map<std::string,std::string> result;
            std::string name,value;
            while (std::getline(names,name,'\4') && std::getline(values,value,'\4')) result[name]=value;
            return result;
        };
        auto lineOf=[&](const std::string& marker) {
            std::ifstream source("/out/executor-data/Procedures/"+procedure+".py");
            int line=0;std::string text;
            while (std::getline(source,text)) { ++line; if (text.find(marker)!=std::string::npos) return line; }
            throw std::runtime_error("Fixture marker missing: "+marker);
        };
        request(ContextMessages::REQ_GUI_LOGIN,true,{{MessageField::FIELD_HOST,"controller-qualification"}});
        request(ContextMessages::REQ_OPEN_EXEC,true,{
            {MessageField::FIELD_GUI_MODE,"CONTROL"},{MessageField::FIELD_ARGS,"{}"},
            {MessageField::FIELD_OPEN_MODE,"{Automatic:True,Visible:True,Blocking:False}"}});
        // The open response precedes executor login; wait on the context first.
        auto ready=std::chrono::steady_clock::now()+std::chrono::seconds(10);
        while (request(ContextMessages::REQ_EXEC_INFO,true).get(MessageField::FIELD_EXEC_STATUS)!="PAUSED") {
            require(std::chrono::steady_clock::now()<ready,"Executor did not initially pause");
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        waitStatus("PAUSED");
        if (procedure=="native_controls") {
            auto configuration=request(ExecutorMessages::REQ_GET_CONFIG);
            require(configuration.hasField("ExecDelay"),"Executor config missing execution delay");
            request(ExecutorMessages::REQ_SET_BREAKPOINT,false,{
                {MessageField::FIELD_BREAKPOINT_PROC,procedure},
                {MessageField::FIELD_BREAKPOINT_LINE,std::to_string(lineOf("# BREAK"))},
                {MessageField::FIELD_BREAKPOINT_TYPE,"PERMANENT"}});
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("PAUSED",lineOf("# BREAK"));
            require(variables().at("value")=="21","Breakpoint did not preserve value");
            request(ExecutorMessages::REQ_CHANGE_VARIABLE,false,{
                {MessageField::FIELD_VARIABLE_NAME,"value"},{MessageField::FIELD_VARIABLE_VALUE,"40"},
                {MessageField::FIELD_VARIABLE_GLOBAL,"True"}});
            require(variables().at("value")=="40","Variable update did not persist");
            request(ExecutorMessages::REQ_CLEAR_BREAKPOINT);
            command(ExecutorMessages::MSG_CMD_STEP);
            waitStatus("RUNNING"); // The pending step cannot masquerade as a pause.
            waitStatus("PAUSED",lineOf("# SKIP"));
            require(variables().at("checkpoint")=="41","Step did not execute exactly one statement");
            command(ExecutorMessages::MSG_CMD_SKIP); waitStatus("PAUSED",lineOf("# GOTO_FROM"));
            command(ExecutorMessages::MSG_CMD_GOTO,{{MessageField::FIELD_GOTO_LINE,"-1"}});
            auto rejectionDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
            while (!peer.rejectedJump.load()) {
                require(std::chrono::steady_clock::now()<rejectionDeadline,"Invalid Goto did not report rejection");
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
            }
            waitStatus("PAUSED",lineOf("# GOTO_FROM"));
            command(ExecutorMessages::MSG_CMD_GOTO,{{MessageField::FIELD_GOTO_LINE,std::to_string(lineOf("# GOTO_TO"))}});
            waitStatus("PAUSED",lineOf("# GOTO_TO"));
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("FINISHED");
        } else if (procedure=="native_pause" || procedure=="native_abort") {
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("RUNNING");
            // A procedure-owned marker proves that the try/finally body is active.
            auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
            while (!std::ifstream("/out/"+procedure+"-ready.txt")) {
                require(std::chrono::steady_clock::now()<deadline,"Loop did not start");
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
            }
            command(ExecutorMessages::MSG_CMD_PAUSE); waitStatus("PAUSED");
            const auto value=variables().at("counter");
            std::this_thread::sleep_for(std::chrono::milliseconds(150));
            require(variables().at("counter")==value,"Procedure continued while paused");
            if (procedure=="native_abort") {
                command(ExecutorMessages::MSG_CMD_ABORT); waitStatus("ABORTED");
            } else {
                request(ExecutorMessages::REQ_CHANGE_VARIABLE,false,{
                    {MessageField::FIELD_VARIABLE_NAME,"stop"},{MessageField::FIELD_VARIABLE_VALUE,"True"},
                    {MessageField::FIELD_VARIABLE_GLOBAL,"True"}});
                command(ExecutorMessages::MSG_CMD_RUN); waitStatus("FINISHED");
            }
        } else if (procedure=="native_shared" || procedure=="native_child_parent" || procedure=="native_wait") {
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("FINISHED");
        } else if (procedure=="native_prompt") {
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("PROMPT");
            auto prompt=request(ExecutorMessages::REQ_EXEC_STATUS);
            require(prompt.get(MessageField::FIELD_TEXT)=="Continue qualification?","Prompt text differs");
            command(MessageId::MSG_ID_PROMPT_ANSWER,{{MessageField::FIELD_RVALUE,"0"}});
            waitStatus("FINISHED");
        } else if (procedure=="native_failure") {
            command(ExecutorMessages::MSG_CMD_RUN); waitStatus("ERROR");
            auto failure=request(ExecutorMessages::REQ_EXEC_STATUS);
            require(failure.get(MessageField::FIELD_REASON).find("intentional controller failure")!=std::string::npos,
                "Original Python failure details lost: "+failure.dataStr());
        } else throw std::runtime_error("Unknown controller scenario");
        request(ContextMessages::REQ_CLOSE_EXEC,true);
        if (procedure=="native_controls") {
            const std::string quoted="native quoted ' space#1";
            auto quotedRequest=[&](const std::string& id,Fields fields={}) {
                auto msg=message(id,true,fields);msg.setType(MSG_TYPE_REQUEST);
                msg.set(MessageField::FIELD_PROC_ID,quoted);
                auto reply=client.sendRequest(msg,7000);
                require(!reply.isVoid() && reply.getType()!=MSG_TYPE_ERROR,"Quoted procedure request failed: "+reply.dataStr());
                return reply;
            };
            quotedRequest(ContextMessages::REQ_OPEN_EXEC,{
                {MessageField::FIELD_GUI_MODE,"CONTROL"},{MessageField::FIELD_ARGS,"{}"},
                {MessageField::FIELD_OPEN_MODE,"{Automatic:True,Visible:True,Blocking:False}"}});
            bool ran=false,finished=false;
            auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);
            while (std::chrono::steady_clock::now()<deadline) {
                const auto status=quotedRequest(ContextMessages::REQ_EXEC_INFO).get(MessageField::FIELD_EXEC_STATUS);
                if (status=="PAUSED" && !ran) {
                    auto msg=message(ExecutorMessages::MSG_CMD_RUN,false,{});
                    msg.setType(MSG_TYPE_ONEWAY);msg.setReceiver(quoted);
                    msg.set(MessageField::FIELD_PROC_ID,quoted);client.sendMessage(msg);ran=true;
                }
                if (status=="FINISHED") { finished=true;break; }
                require(status!="ERROR" && status!="ABORTED","Quoted procedure failed");
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            }
            require(ran && finished,"Quoted procedure did not finish");
            auto terminalDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
            while (!peer.terminalSeen && std::chrono::steady_clock::now()<terminalDeadline)
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            require(peer.terminalSeen && peer.outputOrdered,"Native terminal status overtook final Display output");
            std::cout<<"OUTPUT_BEFORE_TERMINAL_VERIFIED"<<std::endl;
            quotedRequest(ContextMessages::REQ_CLOSE_EXEC);
            std::cout<<"QUOTED_PROCEDURE_COMPLETE"<<std::endl;
        }
        request(ContextMessages::REQ_GUI_LOGOUT,true);
        client.disconnect();
        std::cout << "CONTROLLER_SCENARIO_COMPLETE " << procedure << std::endl;
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
      catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    return 1;
}
