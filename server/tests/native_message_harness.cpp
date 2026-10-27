// SPDX-License-Identifier: GPL-3.0-or-later
// Compiles the real frozen message class and the candidate codec separately.
#include "SPELL_IPC/SPELLipcMessage.H"
#include <atomic>
#include <limits>
#include <iostream>
#include <stdexcept>
#include <utility>
#include "bridge_encode.inc"
static bool measuring=false;
static size_t allocated=0, allocations=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*, size_t size) {
    if(measuring) { allocated+=size; ++allocations; }
}
static void require(bool ok) { if(!ok) throw std::runtime_error("codec invariant failed"); }
static uint64_t digest=1469598103934665603ULL;
static void record(const std::string& value) {
    for(unsigned char byte:value) { digest^=byte; digest*=1099511628211ULL; }
}
static std::string legacy_wire(const SPELLipcMessage& m) {
    std::string wire;
    wire+=m.dataItem(MessageField::FIELD_SENDER_ID,m.getSender());
    wire+=m.dataItem(MessageField::FIELD_RECEIVER_ID,m.getReceiver());
    wire+=m.dataItem(MessageField::FIELD_SEQUENCE,m.getSequenceStr());
    wire+=m.dataItem(MessageField::FIELD_ID,m.getId());
    wire+=m.dataItem(MessageField::FIELD_TYPE,MessageType::TypeStr[m.getType()]);
    wire+=m.dataItem(MessageField::FIELD_IPC_KEY,ISTR(m.getKey()));
    for(const auto& p:m.v08Fields())wire+=m.dataItem(p.first,p.second);
    return wire;
}
#include "native_output_harness.inc"
static void readInput(SPELLipcMessage& message,const std::string& data) {
#if V08_CODEC_REUSE
    message.v08ReadData(data);
#else
    message=SPELLipcMessage();message.fromData(data);
#endif
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    std::string mode=argv[1];
    SPELLipcMessage m("MSG_NOTIFY");m.setType(MSG_TYPE_NOTIFY_ASYNC);
    m.setSender("root#0");m.setReceiver("GUI");m.setSequence(-1);m.setKey(97);
    m.set("Csp","root:14");m.set("ExecutorStatus","RUNNING");
    if(mode=="input_reuse") {
        SPELLipcMessage parsed;
        for(int i=0;i<256;++i) {
            m.set("Binary",std::string(64,static_cast<char>(i)));
            m.set("Unicode",u8"é中🙂");
            auto packet=m.data()+m.dataItem("Csp","last");
            readInput(parsed,packet);record(parsed.data());
            auto copy=parsed;parsed.set("Csp","changed");
            require(copy.get("Csp")=="last");
            readInput(parsed,m.dataItem("only","value"));
            SPELLipcMessage fresh;fresh.fromData(m.dataItem("only","value"));
            require(parsed.data()==fresh.data()&&parsed.getCompressed()==fresh.getCompressed());
            record(parsed.data());
            parsed.set(MessageField::FIELD_ID,"stale-metadata-property");
            parsed.fromData(m.data());require(!parsed.hasField(MessageField::FIELD_ID));
            readInput(parsed,"");require(parsed.data()==SPELLipcMessage().data());
        }
    } else if(mode=="input_malformed") {
        SPELLipcMessage parsed;
        const auto packet=m.data();
        for(size_t cut=1;cut<packet.size();++cut) {
            readInput(parsed,packet);auto malformed=packet.substr(0,cut);
            try {readInput(parsed,malformed);}catch(const SPELLipcError&) {
                require(parsed.v08Fields().empty()&&parsed.getId()=="<void>");
            }
            readInput(parsed,packet);require(parsed.data()==packet);
        }
        auto huge=m.dataItem("large",std::string(2*1024*1024,'x'));
        readInput(parsed,huge);require(parsed.get("large").size()==2*1024*1024);
        readInput(parsed,packet);require(!parsed.hasField("large"));
        std::string many;
        for(int i=0;i<5000;++i)many+=m.dataItem(std::to_string(i),"value");
        readInput(parsed,many);require(parsed.v08Fields().size()==5000);
        readInput(parsed,packet);require(parsed.data()==packet);
    } else if(mode=="alloc_mixed_input") {
        SPELLipcMessage line("MSG_NOTIFICATION"),ack("MSG_ACKNOWLEDGE");
        for(auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence","User","Csp","ExecutorStatus"})
            line.set(key,std::string(64,'x'));
        ack.set("Ack",std::string(64,'a'));
        const auto linePacket=line.data(),ackPacket=ack.data();
        SPELLipcMessage parsed;
        for(int i=0;i<64;++i){readInput(parsed,linePacket);readInput(parsed,ackPacket);}
        measuring=true;
        for(int i=0;i<10000;++i){readInput(parsed,linePacket);readInput(parsed,ackPacket);}
        measuring=false;
        require(parsed.data()==ackPacket&&parsed.v08Fields().size()==1);
    } else if(mode=="alloc_input") {
        for(auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence","User"})m.set(key,"handoff_root:14");
        auto packet=m.data();SPELLipcMessage parsed;readInput(parsed,packet);
        measuring=true;
        for(int i=0;i<10000;++i)readInput(parsed,packet);
        measuring=false;
    } else if(mode=="output") {
        check_output(m);
    } else if(mode=="alloc_output") {
        for(auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence","User"})m.set(key,"handoff_root:14");
        SPELLipcOutput out;out.m_socket.wire.reserve(4096);
        measuring=true;
        for(int i=0;i<10000;++i) {out.m_socket.wire.clear();out.m_socket.calls=0;out.send(m);}
        measuring=false;
    } else if(mode=="request_ids") {
        for(const auto& sender:std::vector<std::string>{"", "root#0",std::string(48,'s'),std::string("n\0ul",4),u8"é中🙂"})
        for(const auto& receiver:std::vector<std::string>{"CTX",std::string(48,'r'),""})
        for(int key:{-2147483647-1,-1,0,97,2147483647})
        for(long sequence:{std::numeric_limits<long>::min(),-2147483648L,-2L,-1L,0L,2147483647L,std::numeric_limits<long>::max()}) {
            m.setSender(sender);m.setReceiver(receiver);m.setKey(key);m.setSequence(sequence);
            const long stored=m.getSequence();
            const auto expected=std::to_string(key)+"-"+receiver+"-"+sender+
                (stored==-1?"":":"+std::to_string(stored));
            require(m.requestId()==expected);record(m.requestId());
        }
    } else if(mode=="alloc_request_ids") {
        m.setSender(std::string(48,'s'));m.setReceiver(std::string(48,'r'));
        m.setSequence(12345);m.setKey(97);
        measuring=true;
        for(int i=0;i<10000;++i){auto value=m.requestId();require(value.size()>96);}
        measuring=false;
    } else if(mode=="wire") {
        for(int i=0;i<256;++i) {
            m.setSequence(i%2 ? -2147483647L : 2147483648L+i);
            m.setType(static_cast<SPELLipcMessageType>(i%12));
            m.set(std::string(i%33,'k'),std::string(i*3,static_cast<char>(i)));
            m.set("Unicode",u8"é中🙂");m.set("Empty","");
            m.set("Binary",std::string("a\0b",3));
            auto wire=m.data();require(wire==legacy_wire(m));record(wire);
            SPELLipcMessage parsed;parsed.fromData(wire);
            record(parsed.data());record(parsed.requestId());record(parsed.responseId());
            require(parsed.get("Binary")==std::string("a\0b",3));
        }
    } else if(mode=="moves"||mode=="alloc_move") {
        m.set("Binary",std::string("a\0b",3));m.set("large",std::string(1000,'x'));
        m.setCompressed(true);const auto wire=m.data();
        auto copy=m;copy.set("large","changed");require(m.data()==wire);
        measuring=mode=="alloc_move";
        SPELLipcMessage moved(std::move(m));
        SPELLipcMessage target;target=std::move(moved);
        measuring=false;
        require(target.data()==wire&&target.getCompressed()&&target.getKey()==97);
        // Only destruction and reassignment are required of moved-from values.
        m=SPELLipcMessage("reassigned");moved=target;
        require(m.getId()=="reassigned"&&moved.data()==wire);
        if(mode=="moves"){record(target.data());record(std::to_string(sizeof(m)));}
    } else if(mode=="bridge") {
        m.set("Csp",u8"é中🙂");m.set("VarName","");m.set("VarValue",std::string("a\0b\xff",4));
        m.set("DefaultProvided","true");m.set("TimeoutMicroseconds","123");
        m.set("not-in-whitelist","hidden");
        auto value=encode(m);
        require(value.size()==5&&value["id"]==m.getId()&&value["type"]==m.getType());
        require(value["sender"]==m.getSender()&&value["receiver"]==m.getReceiver());
        require(value["fields"]["Csp"]==u8"é中🙂"&&value["fields"]["VarName"]=="");
        require(value["fields"]["VarValue"]==std::string("a\0b\xff",4));
        require(value["fields"]["DefaultProvided"]=="true"&&value["fields"]["TimeoutMicroseconds"]=="123");
        require(!value["fields"].contains("not-in-whitelist"));
        record(value.dump(-1,' ',false,Json::error_handler_t::replace));
        for(const char* event:{"message","unsupportedRequest"}) {
            auto frame=encodeEvent(event,m);require(frame.size()==2&&frame["event"]==event&&frame["message"]==value);
            record(frame.dump(-1,' ',false,Json::error_handler_t::replace));
        }
        for(auto type:{MSG_TYPE_RESPONSE,MSG_TYPE_ERROR}) {
            m.setType(type);auto frame=encodeReply(4294967295u,m);
            require(frame.size()==3&&frame["seq"]==4294967295u&&frame["ok"]==(type!=MSG_TYPE_ERROR));
            require(frame["message"]==encode(m));record(frame.dump(-1,' ',false,Json::error_handler_t::replace));
        }
    } else if(mode=="cached_frames") {
        V08BridgeFrame encoder;
        for (int i=0;i<256;++i) {
            m.set("VarValue",std::string(64,static_cast<char>(i)));
            m.set("Csp",u8"é中🙂");m.set("not-in-whitelist","hidden");
            m.set("DefaultProvided",i%2?"true":"");
            for (const char* event:{"message","unsupportedRequest"})
                require(encoder.event(event,m)==encodeEvent(event,m).dump(-1,' ',false,Json::error_handler_t::replace));
            m.setType(i%2?MSG_TYPE_ERROR:MSG_TYPE_RESPONSE);
            require(encoder.reply(4294967295u-i,m)==encodeReply(4294967295u-i,m).dump(-1,' ',false,Json::error_handler_t::replace));
            SPELLipcMessage empty;
            require(encoder.event("message",empty)==encodeEvent("message",empty).dump(-1,' ',false,Json::error_handler_t::replace));
        }
        m.set("VarValue",std::string(2*1024*1024,'x'));
        require(encoder.event("message",m)==encodeEvent("message",m).dump(-1,' ',false,Json::error_handler_t::replace));
        encoder.releaseLargeBuffers();
        m.clear();require(encoder.event("message",m)==encodeEvent("message",m).dump(-1,' ',false,Json::error_handler_t::replace));
    } else if(mode=="duplicates") {
        auto wire=m.data()+m.dataItem("Csp","last")+m.dataItem(MessageField::FIELD_ID,"last-id");
        m.fromData(wire);require(m.getId()=="last-id"&&m.get("Csp")=="last");
        require(!m.hasField(MessageField::FIELD_ID));record(m.data());
    } else if(mode=="partial_metadata") {
        m.setCompressed(true);
        m.fromData(m.dataItem("only","value"));
        require(m.getId()=="MSG_NOTIFY"&&m.getKey()==97&&m.getSequence()==-1&&m.getCompressed());
        require(m.v08Fields().size()==1);record(m.data());
        m.fromData("");require(m.v08Fields().empty()&&m.getId()=="MSG_NOTIFY");record(m.data());
    } else if(mode=="malformed") {
        for(const auto& field:{m.dataItem("", ""),m.dataItem("x", "a"),m.dataItem("long-key",std::string(200,'v'))}) {
            for(size_t cut=1;cut<field.size();++cut) {
                m.set("old","value");bool rejected=false;
                auto packet=m.dataItem(MessageField::FIELD_ID,"replacement")+field.substr(0,cut);
                try {m.fromData(packet);}catch(const SPELLipcError&){rejected=true;}
                require(rejected&&m.getId()=="MSG_NOTIFY"&&m.getKey()==97&&m.v08Fields().empty());
            }
        }
        for(auto tail:{std::string("\0\1x\xff\xff\xff\xff",7), std::string("\xff\xffx",3)}) {
            bool rejected=false;try{m.fromData(tail);}catch(const SPELLipcError&){rejected=true;}
            require(rejected);
        }
    } else if(mode=="oversize_key") {
        m.set(std::string(65536,'x'),"v");bool rejected=false;
        try{m.data();}catch(const SPELLipcError&){rejected=true;}require(rejected);
    } else if(mode=="alloc_parse"||mode=="alloc_data"||mode=="alloc_bridge"||mode=="alloc_frame"||mode=="alloc_cached_frame") {
        for(auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence","User"})m.set(key,"handoff_root:14");
        auto data=m.data();
        V08BridgeFrame encoder;
        encoder.event("message",m);
        measuring=true;
        for(int i=0;i<10000;++i) {
            if(mode=="alloc_cached_frame") {require(!encoder.event("message",m).empty());}
            else if(mode=="alloc_parse") {SPELLipcMessage parsed;parsed.fromData(data);}
            else if(mode=="alloc_frame") {auto value=encodeEvent("message",m);require(value.size()==2);}
            else if(mode=="alloc_bridge") {auto value=encode(m);require(value.size()==5);}
            else {auto wire=m.data();if(wire.empty())return 4;}
        }
        measuring=false;
    } else return 3;
    std::cout<<"{\"digest\":"<<digest<<",\"allocated_bytes\":"<<allocated<<",\"allocations\":"<<allocations<<"}"<<std::endl;
}
