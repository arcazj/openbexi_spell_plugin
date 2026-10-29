// SPDX-License-Identifier: GPL-3.0-or-later
// Private v0.8 candidate, derived from native_bridge.cpp SHA256
// f575bcfc080413e601b79b35d8c4ea5131724b43d22cd5de61650d3d858b5fb5
// Local JSON transport around the original qualified SPELL IPC client.
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <iostream>
#include <memory>
#include <mutex>
#include <stdexcept>
#include "fields.inc"

using Json=nlohmann::json;
#include "bridge_frame.H"
#include "bridge_input.H"
std::mutex outputMutex;
void emit(const Json& value) {
    std::lock_guard<std::mutex> guard(outputMutex);
    std::cout << value.dump(-1,' ',false,Json::error_handler_t::replace) << std::endl;
}
void emitFrame(const SPELLipcMessage& message,const char* event,unsigned sequence=0) {
    std::lock_guard<std::mutex> guard(outputMutex);
    static V08BridgeFrame encoder;
    const auto& bytes=event?encoder.event(event,message):encoder.reply(sequence,message);
    std::cout << bytes << std::endl;
    encoder.releaseLargeBuffers();
}
class Peer final:public SPELLipcInterfaceListener {
public:
    SPELLipcClientInterface* client=nullptr;
    void processMessage(const SPELLipcMessage& message) override {
        // Publish before acknowledging: terminal status must never overtake
        // output which the executor already considers delivered.
        emitFrame(message,"message");
        if (message.getType()==MSG_TYPE_NOTIFY && message.hasField(MessageField::FIELD_MSG_SEQUENCE)) {
            SPELLipcMessage ack(ExecutorMessages::ACKNOWLEDGE);
            ack.setType(MSG_TYPE_ONEWAY);ack.setSender("GUI");
            ack.setReceiver(message.get(MessageField::FIELD_PROC_ID));
            ack.set(MessageField::FIELD_PROC_ID,message.get(MessageField::FIELD_PROC_ID));
            ack.set(MessageField::FIELD_MSG_SEQUENCE,message.get(MessageField::FIELD_MSG_SEQUENCE));
            client->sendMessage(ack);
        }
    }
    SPELLipcMessage processRequest(const SPELLipcMessage& message) override {
        // GUI prompts use MSG_PROMPT/MSG_ANSWER, not synchronous IPC requests.
        emitFrame(message,"unsupportedRequest");
        SPELLipcMessage reply("MSG_ERROR");reply.setType(MSG_TYPE_ERROR);
        reply.set(MessageField::FIELD_ERROR,"Unsupported host request");
        return reply;
    }
    void processConnectionError(int,std::string error,std::string reason) override {
        emit({{"event","connectionError"},{"error",error+": "+reason}});
    }
    void processConnectionClosed(int) override { emit({{"event","connectionClosed"}}); }
};

// This endpoint only publishes notifications and queues acknowledgements. It
// never waits for a request inside the callback. Preserve channel receive order
// instead of spawning one independently scheduled worker for every GUI message.
class OrderedClient final:public SPELLipcClientInterface {
public:
    using SPELLipcClientInterface::SPELLipcClientInterface;
protected:
    void incomingMessage(const SPELLipcMessage& message) override {
        if (m_connected && m_listener) m_listener->processMessage(message);
    }
};

int main(int argc,char** argv) {
    if (argc!=2) return 2;
    Peer peer;
    try {
        OrderedClient client("OPENBEXI-HOST-V1","127.0.0.1",std::stoi(argv[1]));
        peer.client=&client;client.initialize(&peer);client.connect();
        emit({{"event","connected"},{"protocol",1}});
        // Keep one input buffer for this connection; the unchanged 4 MiB check
        // bounds accepted content. JSON parsing owns its result independently.
        std::string line;
        while (std::cin.good()) {
            line.clear();
            char ch;
            while (std::cin.get(ch) && ch!='\n') {
                if (line.size()>=4*1024*1024) throw std::runtime_error("Host message exceeds 4 MiB");
                line+=ch;
            }
            if (line.empty()) break;
            Json request=Json::parse(line);
            const auto sequence=request.at("seq").get<unsigned>();
            try {
                auto message=SPELLipcMessage::v08FromId(v08BridgeString(request.at("id")));
                message.setSender("GUI");message.v08SetReceiver(v08BridgeString(request.at("receiver")));
                // The request owns these fields throughout this synchronous loop.
                // v08Set() copies into independently owned native strings.
                const auto fields=request.find("fields");
                if (fields!=request.end())
                    for (const auto& item:fields->items())
                        message.v08Set(item.key(),v08BridgeString(item.value()));
                if (request.at("operation")=="request") {
                    message.setType(MSG_TYPE_REQUEST);
                    auto reply=client.sendRequest(message,7000);
                    if (reply.isVoid()) throw std::runtime_error("Native request timed out");
                    emitFrame(reply,nullptr,sequence);
                } else if (request.at("operation")=="send") {
                    message.setType(MSG_TYPE_ONEWAY);client.sendMessage(message);
                    emit({{"seq",sequence},{"ok",true}});
                } else throw std::runtime_error("Unknown bridge operation");
            } catch (const SPELLcoreException& error) {
                emit({{"seq",sequence},{"ok",false},{"error",error.what()}});
            } catch (const std::exception& error) {
                emit({{"seq",sequence},{"ok",false},{"error",error.what()}});
            }
        }
        client.disconnect();
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; }
      catch (const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
