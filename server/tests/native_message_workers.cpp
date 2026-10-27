// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_IPC/SPELLipcIncoming.H"
#include <atomic>
#include <cassert>
#include <iostream>
#include <memory>
#include <vector>
#include <chrono>
#include <stdexcept>
#include <set>
#include <sys/syscall.h>
#include <unistd.h>
static std::set<long> tids;
static std::mutex tidsMutex;
struct Listener:SPELLipcInterfaceListener {
    std::atomic<int> calls{0},active{0};
    std::atomic<bool> blocked{false};
    bool fail=false;
    void processMessage(const SPELLipcMessage& msg) override {
        assert(msg.getId()=="payload");
        {std::lock_guard<std::mutex> lock(tidsMutex);tids.insert(syscall(SYS_gettid));}
        ++active;
        while(blocked)std::this_thread::yield();
        --active;++calls;
        if(fail)throw std::runtime_error("expected");
    }
    SPELLipcMessage processRequest(const SPELLipcMessage& msg) override {
        processMessage(msg);return SPELLipcMessage();
    }
};
static std::unique_ptr<SPELLipcIncomingBase> message(Listener& l) {
    return std::make_unique<SPELLipcIncomingMessage>("id","interface",SPELLipcMessage("payload"),l);
}
static void waitFor(std::atomic<int>& value,int target) {
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    while(value!=target && std::chrono::steady_clock::now()<end)std::this_thread::yield();
    assert(value==target);
}
int main(int argc,char** argv) {
    assert(argc==2);std::string mode=argv[1];Listener l;
    if(mode=="sequential") {
        for(int i=0;i<10000;++i) {auto m=message(l);m->start();m->join();assert(m->isFinished());}
        assert(l.calls==10000);
        std::cout<<"{\"calls\":"<<l.calls<<",\"os_threads_created\":"<<tids.size()<<"}\n";
    } else if(mode=="overflow") {
        l.blocked=true;std::vector<std::unique_ptr<SPELLipcIncomingBase>> jobs;
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
    } else if(mode=="shutdown") {
#if V08_WORKERS
        V08MessageWorkers pool;std::atomic<int> calls{0};
        std::array<V08MessageTicket,8> tickets;
        auto callback=[](void* p){std::this_thread::sleep_for(std::chrono::milliseconds(10));++*static_cast<std::atomic<int>*>(p);};
        for(auto& t:tickets)assert(pool.tryStart(&calls,callback,t));
        pool.shutdown();for(auto& t:tickets){pool.join(t);assert(t.done);}
        V08MessageTicket late;assert(!pool.tryStart(&calls,callback,late));assert(calls==8);
#endif
        std::cout<<"{\"shutdown_drained\":true}\n";
    } else return 2;
}
