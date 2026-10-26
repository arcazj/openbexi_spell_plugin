// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_IPC/SPELLipcMessage.H"
#include <atomic>
#include <iostream>
#include <memory>
#include <thread>
#include <vector>
static std::atomic<bool> measure{false};
static std::atomic<size_t> calls{0}, bytes{0};
extern "C" void __sanitizer_malloc_hook(const volatile void*, size_t size) {
    if (measure.load(std::memory_order_relaxed)) {
        calls.fetch_add(1,std::memory_order_relaxed);
        bytes.fetch_add(size,std::memory_order_relaxed);
    }
}
#if V08_STORAGE
extern "C" size_t storage_size();
extern "C" size_t storage_capacity();
extern "C" size_t storage_fields();
#endif
static void require(bool ok) { if(!ok)std::abort(); }
static SPELLipcMessage fixture() {
    SPELLipcMessage message("MSG_NOTIFICATION");
    message.setSender("handoff_procedure_root#0");message.setReceiver("GUI");
    message.setType(MSG_TYPE_NOTIFY_ASYNC);message.setKey(13);message.setSequence(42);
    message.setCompressed(true);
    for (auto key:{"ProcId","CodeName","DataType","StageId","StageTitle","MsgSequence",
                  "User","Csp","ExecutorStatus"}) message.set(key,"handoff_procedure_root:14");
    return message;
}
static void compare(const SPELLipcMessage& a,const SPELLipcMessage& b) {
    require(a.data()==b.data() && a.getCompressed()==b.getCompressed());
}
#include "native_line_harness.inc"
int main(int argc,char** argv) {
    require(argc==2);const std::string mode=argv[1];
    auto source=fixture();
    if(mode=="line" || mode=="line_bench") {line_case(mode);
    } else if(mode=="bench") {
        {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
        measure=true;
        for(int n=0;n<10000;++n) {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
        measure=false;
    } else if(mode=="mixed_bench") {
        SPELLipcMessage other("LONG_ALTERNATE_MESSAGE_ID");
        other.setSender("different-procedure-origin#1");
        other.setReceiver("different-long-receiver-name");
        other.set("PromptId","alternate-unicode-identity");
        other.set("Answer","alternate-content");
        {auto a=source;auto b=a;auto c=other;auto d=c;}
        measure=true;
        for(int n=0;n<10000;++n) {auto a=source;auto b=a;auto c=other;auto d=c;}
        measure=false;
    } else if(mode=="decode_bench") {
        const auto wire=source.data();SPELLipcMessage parsed;
#if V08_STORAGE
        parsed.v08ReadData(wire);parsed.v08ReadData(wire);
#else
        parsed.fromData(wire);
#endif
        measure=true;
        for(int n=0;n<10000;++n) {
#if V08_STORAGE
            parsed.v08ReadData(wire);
#else
            parsed=SPELLipcMessage();parsed.fromData(wire);
#endif
        }
        measure=false;require(parsed.data()==source.data());
    } else if(mode=="metadata") {
        auto message=source;
        message.fromData(source.dataItem("only","value"));
        require(message.getSender()==source.getSender());
        // The frozen decoder is not a safe malformed-packet oracle.
#if V08_STORAGE
        bool rejected=false;
        try {message.fromData(source.dataItem(MessageField::FIELD_ID,"different-long-id")
                             +std::string("\0\1x\xff\xff\xff\xff",7));}
        catch(const SPELLipcError&) {rejected=true;}
        require(rejected && message.getId()==source.getId());
        require(message.v08Fields().empty());
#endif
        for(int n=0;n<100;++n) {
            const auto packet=source.dataItem(MessageField::FIELD_ID,std::string(2*1024*1024,'i'));
            message.fromData(packet);require(message.getId().size()==2*1024*1024);
            message.fromData(source.data());compare(message,source);
        }
    } else if(mode=="shape_bench" || mode=="saturated_bench") {
        // Preserve the exact-key cache regression added by ad5ccc1. The same
        // field counts deliberately carry different key inventories.
        if(mode=="saturated_bench") {
            std::vector<std::unique_ptr<SPELLipcMessage>> startup;
            for(int n=0;n<32;++n) {
                auto item=std::make_unique<SPELLipcMessage>("STARTUP");
                item->set("startup-"+std::to_string(n),"value");
                startup.push_back(std::move(item));
            }
            startup.clear();
        }
        std::vector<SPELLipcMessage> shapes;
        for (int kind=0;kind<4;++kind) {
            SPELLipcMessage item("MSG");item.setSender("X");item.setReceiver("Y");
            for (int field=0;field<(kind==1?2:8);++field)
                item.set(std::to_string(kind)+"-"+std::to_string(field),"value");
            shapes.push_back(std::move(item));
        }
        for (int warm=0;warm<3;++warm)
            for (const auto& shape:shapes) {auto copy=shape;compare(copy,shape);}
        measure=true;
        for (int n=0;n<10000;++n)
            for (const auto& shape:shapes) {
                auto copy=shape;
                require(copy.v08Fields()==shape.v08Fields());
            }
        measure=false;
    } else if(mode=="copy") {
        for(int n=0;n<256;++n) {
            source.set("Binary",std::string(100,static_cast<char>(n)));
            source.set("Unicode",u8"é中🙂");source.set("Empty","");
            auto a=source;compare(a,source);
            SPELLipcMessage b(&source);compare(b,source);
            a.set("User","different");require(source.get("User")!="different");
            SPELLipcMessage c;c=a;compare(c,a);c=c;compare(c,a);
            c=SPELLipcMessage("EMPTY");require(c.v08Fields().empty());
            auto saved=a;auto moved=std::move(a);compare(moved,saved);
        }
    } else if(mode=="shapes") {
        for(int n=0;n<1000;++n) {
            SPELLipcMessage a("shape");
            for(int k=0;k<n%20;++k)a.set("key-"+std::to_string(k),std::to_string(n));
            auto b=a;compare(a,b);b=source;compare(b,source);b=a;compare(a,b);
            SPELLipcMessage empty;auto c=empty;require(c.v08Fields().empty());
            SPELLipcMessage self("empty-self-assignment");
            self=self;require(self.v08Fields().empty() && self.getId()=="empty-self-assignment");
        }
    } else if(mode=="threads") {
        std::vector<std::thread> workers;
        for(int t=0;t<8;++t) workers.emplace_back([&,t] {
            auto local=source;
            for(int n=0;n<1000;++n) {
                local.set("User",std::to_string(t));auto a=local;auto b=a;
                a.set("User","changed");require(b.get("User")==std::to_string(t));
                compare(local,b);
            }
        });
        for(auto& worker:workers)worker.join();
    } else if(mode=="bounds") {
#if V08_STORAGE
        std::vector<std::unique_ptr<SPELLipcMessage>> live;
        for(int n=0;n<100;++n) live.emplace_back(new SPELLipcMessage(source));
        live.clear();require(storage_size()<=32);
        require(storage_capacity()<=32*64*1024);require(storage_fields()<=32*64);
        for(int n=0;n<50;++n) {
            auto huge=source;huge.set("huge",std::string(1024*1024,'x'));
            auto other=huge;compare(huge,other);
            auto wide=source;for(int k=0;k<100;++k)wide.set(std::to_string(k),"x");
            auto copied=wide;compare(wide,copied);
        }
        require(storage_size()<=32);require(storage_capacity()<=32*64*1024);
        require(storage_fields()<=32*64);
        SPELLipcMessage emptyHuge(std::string(2*1024*1024,'x'));
        emptyHuge=source;compare(emptyHuge,source);
        require(storage_capacity()<=32*64*1024);
#endif
    } else return 2;
    std::cout<<"{\"allocations\":"<<calls<<",\"allocated_bytes\":"<<bytes
             <<",\"message_size\":"<<sizeof(SPELLipcMessage)
             <<",\"line_digest\":"<<line_digest<<",\"deliveries\":"<<line_deliveries<<"}\n";
}
