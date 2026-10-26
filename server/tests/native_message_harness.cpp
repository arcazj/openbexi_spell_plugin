// SPDX-License-Identifier: GPL-3.0-or-later
// Compiles the real frozen message class and the candidate codec separately.
#include "SPELL_IPC/SPELLipcMessage.H"
#include <atomic>
#include <iostream>
#include <stdexcept>
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
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    std::string mode=argv[1];
    SPELLipcMessage m("MSG_NOTIFY");m.setType(MSG_TYPE_NOTIFY_ASYNC);
    m.setSender("root#0");m.setReceiver("GUI");m.setSequence(-1);m.setKey(97);
    m.set("Csp","root:14");m.set("ExecutorStatus","RUNNING");
    if(mode=="wire") {
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
    } else if(mode=="alloc_parse"||mode=="alloc_data") {
        for(auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence","User"})m.set(key,"handoff_root:14");
        auto data=m.data();
        measuring=true;
        for(int i=0;i<10000;++i) {
            if(mode=="alloc_parse") {SPELLipcMessage parsed;parsed.fromData(data);}
            else {auto wire=m.data();if(wire.empty())return 4;}
        }
        measuring=false;
    } else return 3;
    std::cout<<"{\"digest\":"<<digest<<",\"allocated_bytes\":"<<allocated<<",\"allocations\":"<<allocations<<"}"<<std::endl;
}
