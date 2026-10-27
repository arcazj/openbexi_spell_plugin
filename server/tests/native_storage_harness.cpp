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
extern "C" size_t metadata_size();
extern "C" size_t metadata_capacity();
extern "C" bool metadata_empty();
extern "C" void storage_trace_start();
extern "C" void storage_trace_dump();
#endif
static void require(bool ok) { if(!ok)std::abort(); }
static SPELLipcMessage fixture() {
    SPELLipcMessage message("MSG_NOTIFY");
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
#include "native_notification_harness.inc"
#include "native_routing_harness.inc"
int main(int argc,char** argv) {
    require(argc==2);const std::string mode=argv[1];
    auto source=fixture();
    if(mode=="storage_trace" || mode=="storage_trace_off") {
#if V08_STORAGE
        storage_trace_dump(); // Disabled diagnostics emit nothing.
        if(mode=="storage_trace")storage_trace_start();
        for(int n=0;n<30;++n) {
            auto copy=source;
            SPELLipcMessage fresh("ACK");
            fresh.set("ProcId","root");fresh.set("DataType","ACK");
            auto queued=copy;compare(queued,copy);
        }
        storage_trace_dump();
#endif
    } else if(mode=="notification" || mode=="notification_bench") {
        notification_test(mode=="notification_bench");
    } else if(mode=="routing" || mode=="routing_bench") {
        routing_test(mode=="routing_bench");
    } else if(mode=="metadata_bench") {
        SPELLipcMessage shape("MSG_NOTIF_EXEC_OP_LONG");
        shape.setSender("handoff_procedure_root#0");
        shape.setReceiver("handoff_controller_observer#0");
        for(int n=0;n<10;++n) {auto copy=shape;copy.clear();}
        measure=true;
        for(int n=0;n<10000;++n) {auto copy=shape;copy.clear();}
        measure=false;
    } else if(mode=="metadata") {
        std::vector<std::unique_ptr<SPELLipcMessage>> live;
        for(int n=0;n<100;++n) {
            auto value=std::make_unique<SPELLipcMessage>("LONG_MESSAGE_IDENTIFIER"+std::to_string(n));
            value->setSender(std::string("sender\0",7)+std::string(200,'a'+n%26));
            value->setReceiver(std::string(300,'A'+n%26));
            auto copy=*value;compare(copy,*value);
            SPELLipcMessage pointer(value.get());pointer.setCompressed(value->getCompressed());
            // Pointer construction deliberately adds the upstream empty User property.
            auto withUser=*value;withUser.set("User","");compare(pointer,withUser);
            auto moved=std::move(copy);compare(moved,*value);
            moved.clear();require(moved.getId().empty());compare(*value,*value);
            SPELLipcMessage::Properties fields;
            fields["payload"]="test";
            SPELLipcMessage explicitFields(value->getId(),fields);
            require(explicitFields.getId()==value->getId());
            live.push_back(std::move(value));
        }
        live.clear();
        for(int n=0;n<100;++n) {
            SPELLipcMessage empty;require(empty.getId()=="<void>");
            require(empty.getSender()==MessageId::GENERIC_ID && empty.getReceiver()==MessageId::GENERIC_ID);
            require(empty.v08Fields().empty());
            auto huge=source;huge.setId(std::string(1024*1024,'x'));
            huge.setSender(std::string(1024*1024,'y'));huge.clear();
        }
#if V08_STORAGE
        require(metadata_size()<=32 && metadata_capacity()<=32*64*1024);
        require(metadata_empty());
#endif
    } else if(mode=="bench") {
        {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
        measure=true;
        for(int n=0;n<10000;++n) {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
        measure=false;
    } else if(mode=="mixed_bench" || mode=="saturated_bench") {
        // Interleaved native LINE, ACK, and control shapes: same-size shapes
        // deliberately have different keys. Short metadata isolates map nodes.
        if(mode=="saturated_bench") {
            // Startup traffic fills the bounded cache with unrelated layouts.
            // Steady-state layouts must be able to displace more than one slot.
            std::vector<std::unique_ptr<SPELLipcMessage>> startup;
            for(int n=0;n<32;++n) {
                auto item=std::make_unique<SPELLipcMessage>("INIT");
                item->set("startup-"+std::to_string(n),"value");
                startup.push_back(std::move(item));
            }
            startup.clear();
        }
        std::vector<SPELLipcMessage> shapes;
        shapes.reserve(4);
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
    } else if(mode=="clear_bench") {
        SPELLipcMessage shape("MSG");shape.setSender("X");shape.setReceiver("Y");
        shape.setType(MSG_TYPE_NOTIFY_ASYNC);shape.setKey(13);shape.setSequence(42);
        shape.setCompressed(true);
        for(int key=0;key<9;++key)shape.set("key-"+std::to_string(key),"value");
        auto complete=[&] {
            auto queued=shape;
            queued.clear();
            require(queued.v08Fields().empty());
            require(queued.getId().empty() && queued.getSender().empty() && queued.getReceiver().empty());
            require(queued.getType()==shape.getType() && queued.getKey()==13);
            require(queued.getSequence()==42 && queued.getCompressed());
        };
        for(int n=0;n<10;++n)complete();
        measure=true;
        for(int n=0;n<10000;++n)complete();
        measure=false;
    } else if(mode=="clear") {
        for(int n=0;n<100;++n) {
            auto message=source;auto independent=message;
            if(n%3==0)message.set("large",std::string(1024*1024,'x'));
            if(n%3==1)for(int k=0;k<100;++k)message.set(std::to_string(k),"x");
            message.clear();message.clear();
            require(message.v08Fields().empty());
            require(message.getId().empty() && message.getSender().empty() && message.getReceiver().empty());
            require(message.getSequence()==42 && message.getKey()==13 && message.getCompressed());
            require(message.getType()==source.getType());
            compare(independent,source);
            SPELLipcMessage decoded;decoded.fromData(message.data());
            // Compression is carried by socket framing, outside data().
            decoded.setCompressed(message.getCompressed());compare(decoded,message);
            message.set("new","value");require(message.v08Fields().size()==1);
        }
    } else if(mode=="fragmented_bench") {
        // Forward a full message, then construct a short acknowledgement while
        // the next full queued copy is live. The producer can split a cached
        // map; its remaining nodes still belong exclusively to the cache.
        SPELLipcMessage shape("MSG");
        for(int key=0;key<9;++key) shape.set("key-"+std::to_string(key),"value");
        auto cycle=[&] {
            {auto forwarded=shape;require(forwarded.v08Fields()==shape.v08Fields());}
            SPELLipcMessage ack("ACK");
            for(int key=0;key<4;++key) ack.set("key-"+std::to_string(key),"ok");
            {auto queued=shape;require(queued.v08Fields()==shape.v08Fields());}
            require(ack.v08Fields().size()==4);
            for(int key=0;key<4;++key)require(ack.get("key-"+std::to_string(key))=="ok");
        };
        for(int n=0;n<100;++n)cycle();
        measure=true;
        for(int n=0;n<10000;++n)cycle();
        measure=false;
    } else if(mode=="fresh_bench") {
        // Real notification construction uses set() for each field. Include
        // changing keys and order; cached fields must never escape into a new
        // message before explicitly being set by its producer.
        auto construct=[](int n) {
            SPELLipcMessage item("MSG");
            require(item.v08Fields().empty());
            for(int k=0;k<8;++k) {
                const auto key=std::to_string((k+n)%8)+"-"+std::to_string(n%3);
                item.set(key,"value");
                require(item.v08Fields().size()==static_cast<size_t>(k+1));
            }
            return item;
        };
        for(int n=0;n<30;++n) {auto item=construct(n);}
        measure=true;
        for(int n=0;n<10000;++n) {auto item=construct(n);}
        measure=false;
    } else if(mode=="fresh") {
        for(int n=0;n<1000;++n) {
            SPELLipcMessage item("MSG");
            require(item.v08Fields().empty());
            for(int k=0;k<n%20;++k) {
                const auto key="key-"+std::to_string((k+n)%20);
                item.set(key,std::to_string(n));
                require(item.v08Fields().size()==static_cast<size_t>(k+1));
            }
            item.set("Binary",std::string("a\0b",3));
            item.set(std::string("K\0x",3),u8"é中🙂");
            item.set("Empty","");
            auto copy=item;
            item.set("Binary",std::string("x\0y",3));
            require(copy.get("Binary")==std::string("a\0b",3));
            require(copy.get(std::string("K\0x",3))==u8"é中🙂");
            require(copy.get("Empty").empty());
            auto bytes=item.data();SPELLipcMessage decoded;decoded.fromData(bytes);
            compare(item,decoded);
        }
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
        }
    } else if(mode=="threads") {
        std::vector<std::thread> workers;
        for(int t=0;t<8;++t) workers.emplace_back([&,t] {
            auto local=source;
            for(int n=0;n<1000;++n) {
                // Exercise producer construction concurrently with copying.
                auto fresh=fixture();compare(fresh,source);
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
#endif
    } else return 2;
    std::cout<<"{\"allocations\":"<<calls<<",\"allocated_bytes\":"<<bytes
             <<",\"message_size\":"<<sizeof(SPELLipcMessage)<<"}\n";
}
