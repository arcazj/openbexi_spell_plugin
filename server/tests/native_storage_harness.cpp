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
int main(int argc,char** argv) {
    require(argc==2);const std::string mode=argv[1];
    auto source=fixture();
    if(mode=="bench") {
        {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
        measure=true;
        for(int n=0;n<10000;++n) {auto a=source;auto b=a;SPELLipcMessage c;c=b;}
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
#endif
    } else return 2;
    std::cout<<"{\"allocations\":"<<calls<<",\"allocated_bytes\":"<<bytes
             <<",\"message_size\":"<<sizeof(SPELLipcMessage)<<"}\n";
}
