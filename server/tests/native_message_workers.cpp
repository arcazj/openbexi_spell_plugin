// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_IPC/SPELLipcIncoming.H"
#include "SPELL_IPC/SPELLipcTrash.H"
#include <atomic>
#include <cassert>
#include <iostream>
#include <memory>
#include <vector>
#include <array>
#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <set>
#include <pthread.h>
#include <sys/syscall.h>
#include <unistd.h>
extern "C" size_t __sanitizer_get_heap_size();
extern "C" size_t __sanitizer_get_current_allocated_bytes();
#if V08_WORKERS
extern size_t v08TestIdle();
#endif
static std::set<long> tids;
static std::mutex tidsMutex;
static bool retentionMeasurement=false;
static std::array<long,10000> retentionTids{};
static size_t retentionCount=0;
struct Listener:SPELLipcInterfaceListener {
    std::atomic<int> calls{0},active{0};
    std::atomic<bool> blocked{false};
    bool fail=false;
    void processMessage(const SPELLipcMessage& msg) override {
        assert(msg.getId()=="payload");
        {std::lock_guard<std::mutex> lock(tidsMutex);
         if(retentionMeasurement){assert(retentionCount<retentionTids.size());retentionTids[retentionCount++]=syscall(SYS_gettid);}
         else tids.insert(syscall(SYS_gettid));}
        ++active;
        while(blocked)std::this_thread::yield();
        --active;++calls;
        if(fail)throw std::runtime_error("expected");
    }
    SPELLipcMessage processRequest(const SPELLipcMessage& msg) override {
        processMessage(msg);return SPELLipcMessage();
    }
};
static void dispose(SPELLipcIncomingBase* m) {
#if V08_WORKERS
    m->v08Dispose();
#else
    delete m;
#endif
}
using MessageOwner=std::unique_ptr<SPELLipcIncomingBase,decltype(&dispose)>;
static MessageOwner message(Listener& l) {
#if V08_WORKERS
    return MessageOwner(SPELLipcIncomingMessage::v08Create("id","interface",SPELLipcMessage("payload"),l),dispose);
#else
    return MessageOwner(new SPELLipcIncomingMessage("id","interface",SPELLipcMessage("payload"),l),dispose);
#endif
}
static void waitFor(std::atomic<int>& value,int target) {
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    while(value!=target && std::chrono::steady_clock::now()<end)std::this_thread::yield();
    assert(value==target);
}
int main(int argc,char** argv) {
    assert(argc==2);std::string mode=argv[1];Listener l;
    if(mode=="retention" || mode=="request_retention") {
        tids.clear();l.calls=0;
        retentionMeasurement=true;
        const size_t initial=__sanitizer_get_heap_size();
        if(mode=="request_retention") {
            SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
            for(int i=0;i<10000;++i) {
                SPELLipcIncomingRequest r("id","interface",SPELLipcMessage("payload"),mutex,&channel,l);
                SPELLipcIncomingBase& base=r;base.start();base.join();assert(base.isFinished());
            }
        } else for(int i=0;i<10000;++i){auto m=message(l);m->start();m->join();}
        const size_t after=__sanitizer_get_heap_size();
        std::sort(retentionTids.begin(),retentionTids.end());
        const auto distinct=std::unique(retentionTids.begin(),retentionTids.end())-retentionTids.begin();
        std::cout<<"{\"calls\":"<<l.calls<<",\"os_threads_created\":"<<distinct
                 <<",\"heap_growth_bytes\":"<<(after-initial)<<",\"live_bytes\":"
                 <<__sanitizer_get_current_allocated_bytes()<<"}\n";
    } else if(mode=="retention_bursts") {
        // Five simultaneous callbacks reproduce the measured native Context
        // peak. Include all 10,000 calls from a fresh component process.
        retentionMeasurement=true;
        const size_t initial=__sanitizer_get_heap_size();
        for(int wave=0;wave<2000;++wave) {
            l.blocked=true;std::vector<MessageOwner> jobs;jobs.reserve(5);
            for(int i=0;i<5;++i){jobs.push_back(message(l));jobs.back()->start();}
            waitFor(l.active,5);l.blocked=false;
            for(auto& m:jobs){m->join();assert(m->isFinished());}
        }
        const size_t after=__sanitizer_get_heap_size();
        std::sort(retentionTids.begin(),retentionTids.end());
        const auto distinct=std::unique(retentionTids.begin(),retentionTids.end())-retentionTids.begin();
        assert(l.calls==10000 && retentionCount==10000);
        std::cout<<"{\"calls\":"<<l.calls<<",\"simultaneous\":5,\"os_threads_created\":"<<distinct
                 <<",\"heap_growth_bytes\":"<<(after-initial)<<",\"live_bytes\":"
                 <<__sanitizer_get_current_allocated_bytes()<<"}\n";
    } else if(mode=="message_thread_exit" || mode=="request_thread_exit" ||
              mode=="message_pthread_cancel" || mode=="request_pthread_cancel") {
        struct ExitingListener:Listener {
            std::atomic<int> entered{0},cleaned{0};
            pthread_t original{};
            bool cancellation=false;
            void processMessage(const SPELLipcMessage&) override {
                struct Cleanup {
                    std::atomic<int>& count;
                    ~Cleanup(){++count;}
                } cleanup{cleaned};
                original=pthread_self();++entered;
                if(cancellation)for(;;)::usleep(1000);
                pthread_exit(nullptr);
            }
            SPELLipcMessage processRequest(const SPELLipcMessage& message) override {
                processMessage(message);return SPELLipcMessage();
            }
        } exiting;
        exiting.cancellation=mode.find("pthread_cancel")!=std::string::npos;
        const bool requests=mode.rfind("request_",0)==0;
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
        // Exceed all five reusable slots. Exited slots must not be reused;
        // subsequent callbacks still have the original dedicated fallback.
        for(int n=0;n<12;++n) {
            MessageOwner job=requests?
                MessageOwner(new SPELLipcIncomingRequest("id","interface",SPELLipcMessage("payload"),mutex,&channel,exiting),dispose):
                message(exiting);
            job->start();waitFor(exiting.entered,n+1);
            if(exiting.cancellation)assert(pthread_cancel(exiting.original)==0);
            job->join();
            assert(job->isFinished() && exiting.cleaned==n+1);
        }
        std::cout<<"{\"callbacks\":12,\"unwound_cleanups\":12,\"native_finished\":true}\n";
    } else if(mode=="sequential") {
        for(int i=0;i<10000;++i) {auto m=message(l);m->start();m->join();assert(m->isFinished());}
        assert(l.calls==10000);
        std::cout<<"{\"calls\":"<<l.calls<<",\"os_threads_created\":"<<tids.size()<<",\"processors_constructed\":"<<v08TestConstructed<<"}\n";
    } else if(mode=="overflow") {
        l.blocked=true;std::vector<MessageOwner> jobs;
        for(int i=0;i<24;++i) {jobs.push_back(message(l));jobs.back()->start();}
        waitFor(l.active,24); // Must not queue a callback behind blocked workers.
        l.blocked=false;for(auto& m:jobs){m->join();assert(m->isFinished());}
        assert(l.calls==24);std::cout<<"{\"parallel_callbacks\":24}\n";
    } else if(mode=="concurrent") {
        std::vector<std::thread> owners;
        for(int i=0;i<12;++i) owners.emplace_back([&]{
            for(int n=0;n<500;++n){auto m=message(l);m->start();m->join();assert(m->isFinished());}
        });
        for(auto& owner:owners)owner.join();assert(l.calls==6000);
        std::cout<<"{\"calls\":6000}\n";
    } else if(mode=="cancel") {
        l.blocked=true;auto m=message(l);m->start();waitFor(l.active,1);m->cancel();
        std::atomic<bool> joined{false};std::thread owner([&]{m->join();joined=true;});
        std::this_thread::sleep_for(std::chrono::milliseconds(40));assert(!joined);
        l.blocked=false;owner.join();assert(joined && l.calls==1);
        std::cout<<"{\"join_waits_for_callback_after_cancel\":true}\n";
    } else if(mode=="request_nested") {
        struct Nested:Listener {
            std::atomic<bool> entered{false};
            SPELLipcMessage processRequest(const SPELLipcMessage& msg) override {
                processMessage(msg);
                if(!entered.exchange(true)) {
                    SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
                    SPELLipcIncomingRequest nested("nested","interface",SPELLipcMessage("payload"),mutex,&channel,*this);
                    SPELLipcIncomingBase& base=nested;base.start();base.join();assert(base.isFinished());
                }
                return SPELLipcMessage();
            }
        } nested;
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
        SPELLipcIncomingRequest outer("outer","interface",SPELLipcMessage("payload"),mutex,&channel,nested);
        SPELLipcIncomingBase& base=outer;base.start();base.join();
        assert(base.isFinished() && nested.calls==2 && tids.size()==2);
        std::cout<<"{\"nested_completed\":true,\"distinct_callback_threads\":2}\n";
    } else if(mode=="request_nested_deep") {
        struct Nested:Listener {
            std::atomic<int> entered{0};
            SPELLipcMessage processRequest(const SPELLipcMessage& msg) override {
                processMessage(msg);
                if(++entered<13) {
                    SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
                    SPELLipcIncomingRequest next("nested","interface",SPELLipcMessage("payload"),mutex,&channel,*this);
                    SPELLipcIncomingBase& base=next;base.start();base.join();assert(base.isFinished());
                }
                return SPELLipcMessage();
            }
        } nested;
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
        SPELLipcIncomingRequest outer("outer","interface",SPELLipcMessage("payload"),mutex,&channel,nested);
        SPELLipcIncomingBase& base=outer;base.start();base.join();
        assert(base.isFinished() && nested.calls==13 && tids.size()==13);
        std::cout<<"{\"nested_completed\":true,\"distinct_callback_threads\":13}\n";
    } else if(mode=="request_collector") {
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;SPELLipcTrash trash("requests");
        for(int i=0;i<2500;++i) {
            auto* r=new SPELLipcIncomingRequest("id","interface",SPELLipcMessage("payload"),mutex,&channel,l);
            assert(trash.place(r));while(trash.haveData())trash.clearData();
        }
        assert(l.calls==2500);std::cout<<"{\"joined_collected_requests\":2500}\n";
    } else if(mode=="request_unwind") {
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;l.fail=true;
        SPELLipcIncomingRequest r("id","interface",SPELLipcMessage("payload"),mutex,&channel,l);
        bool caught=false;try{r.run();}catch(const std::runtime_error&){caught=true;}
        assert(caught && r.isStarted() && r.isFinished() && !r.wait(20));
        std::cout<<"{\"request_completion_on_unwind\":true}\n";
    } else if(mode=="request_concurrent" || mode=="request_cancel" || mode=="request_rebind") {
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
        if(mode=="request_rebind") {
            Listener second;
            for(int i=0;i<1000;++i) {
                SPELLipcIncomingRequest r("id","interface",SPELLipcMessage("payload"),mutex,&channel,i%2?l:second);
                SPELLipcIncomingBase& base=r;base.start();base.join();assert(base.isFinished());
            }
            assert(l.calls==500 && second.calls==500);
            std::cout<<"{\"listeners_rebound\":true}\n";
        } else {
            l.blocked=true;std::vector<MessageOwner> jobs;
            const int count=mode=="request_cancel"?1:24;
            for(int i=0;i<count;++i) {
                jobs.emplace_back(new SPELLipcIncomingRequest("id","interface",SPELLipcMessage("payload"),mutex,&channel,l),dispose);
                jobs.back()->start();
            }
            waitFor(l.active,count); // A busy reusable slot must not queue these.
            if(mode=="request_cancel")jobs.front()->cancel();
            std::atomic<bool> joined{false};
            std::thread owner([&]{for(auto& r:jobs)r->join();joined=true;});
            std::this_thread::sleep_for(std::chrono::milliseconds(40));assert(!joined);
            l.blocked=false;owner.join();assert(joined && l.calls==count);
            for(const auto& r:jobs)assert(r->isFinished());
            std::cout<<"{\"callbacks\":"<<count<<",\"joined_before_disposal\":true}\n";
        }
    } else if(mode=="requests") {
        SPELLmutex mutex;SPELLipcChannel* channel=nullptr;
        for(int i=0;i<20;++i) {
            SPELLipcIncomingRequest r("id","interface",SPELLipcMessage("payload"),mutex,&channel,l);
            SPELLipcIncomingBase& base=r;base.start();base.join();assert(base.isFinished());
        }
        assert(tids.size()==20 && l.calls==20);std::cout<<"{\"request_threads\":20}\n";
    } else if(mode=="exceptions") {
        l.fail=true;auto m=message(l);bool caught=false;
        try{m->run();}catch(const std::runtime_error&){caught=true;}
        assert(caught && m->isStarted() && m->isFinished() && !m->wait(20));
        std::cout<<"{\"completion_on_unwind\":true}\n";
    } else if(mode=="rebind") {
        Listener second;
        for(int i=0;i<1000;++i){
            auto m=message(i%2?second:l);
            assert(!m->isFinished() && !m->isStarted() && m->getIfcName()=="interface");
            m->start();m->join();assert(m->isFinished() && m->isStarted());
        }
        assert(l.calls==500 && second.calls==500);
        std::cout<<"{\"listener_rebound_and_flags_reset\":true}\n";
    } else if(mode=="collector") {
        SPELLipcTrash trash("test");
        for(int i=0;i<2500;++i){auto m=message(l);assert(trash.place(m.get()));m.release();
            while(trash.haveData())trash.clearData();}
        assert(l.calls==2500);
        std::cout<<"{\"calls\":2500,\"node_allocations\":"<<v08TestNodeAllocations<<"}\n";
    } else if(mode=="collector_bound") {
        SPELLipcTrash trash("test");
        for(int round=0;round<2;++round){l.blocked=true;
            for(int i=0;i<64;++i){auto m=message(l);assert(trash.place(m.get()));m.release();}
            waitFor(l.active,64);l.blocked=false;while(trash.haveData())trash.clearData();}
        assert(l.calls==128);
        std::cout<<"{\"node_allocations\":"<<v08TestNodeAllocations<<"}\n";
    } else if(mode=="collector_cancel") {
        SPELLipcTrash trash("test");l.blocked=true;
        for(int i=0;i<24;++i){auto m=message(l);assert(trash.place(m.get()));m.release();}
        waitFor(l.active,24);trash.cancelAndCleanRequests(0);
        std::atomic<bool> cleared{false};std::thread owner([&]{trash.clearData();cleared=true;});
        std::this_thread::sleep_for(std::chrono::milliseconds(40));assert(!cleared);
        l.blocked=false;owner.join();while(trash.haveData())trash.clearData();
        assert(l.calls==24);std::cout<<"{\"joined_before_reuse\":true}\n";
    } else if(mode=="bounded_cache") {
#if V08_WORKERS
        std::vector<MessageOwner> jobs;l.blocked=true;
        for(int i=0;i<64;++i){jobs.push_back(message(l));jobs.back()->start();}
        waitFor(l.active,64);l.blocked=false;for(auto& m:jobs)m->join();jobs.clear();
        assert(v08TestIdle()==32 && v08TestConstructed==64);
        for(int i=0;i<33;++i)jobs.push_back(message(l));
        assert(v08TestIdle()==0 && v08TestConstructed==65);
        for(auto& m:jobs){m->start();m->join();}jobs.clear();assert(v08TestIdle()==32);
#endif
        std::cout<<"{\"passed\":true}\n";
    } else if(mode=="oversized_identity") {
#if V08_WORKERS
        MessageOwner m(SPELLipcIncomingMessage::v08Create(std::string(4096,'x'),"interface",SPELLipcMessage("payload"),l),dispose);
        m->start();m->join();m.reset();assert(v08TestIdle()==0);
#endif
        std::cout<<"{\"passed\":true}\n";
    } else return 2;
}
