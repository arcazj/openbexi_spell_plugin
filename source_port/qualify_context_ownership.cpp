// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the original context-side model and login worker independently.
#include "SPELL_CTX/SPELLexecutor.H"
#include "SPELL_UTIL/SPELLerror.H"
#include "SPELL_UTIL/SPELLtime.H"
#include "SPELL_IPC/SPELLipc_Executor.H"
#include <atomic>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <limits>

void require(bool value,const char* message) { if (!value) throw std::runtime_error(message); }
class ModelProbe final:public SPELLexecutor {
public:
    std::atomic_int succeeded{0},failed{0};
    ModelProbe():SPELLexecutor(SPELLexecutorStartupParams("ownership#1","2000-01-01_000000"),nullptr) {}
    std::atomic_bool logged{false};
    bool isLoggedIn() override { return logged; }
    void loggedIn(bool value) { logged=value; }
    void publish(SPELLexecutorStatus status) {
        SPELLipcMessage notification("model-status");
        notification.setType(MSG_TYPE_NOTIFY_ASYNC);
        notification.set(MessageField::FIELD_DATA_TYPE,MessageValue::DATA_TYPE_STATUS);
        notification.set(MessageField::FIELD_EXEC_STATUS,status==STATUS_PAUSED ? "PAUSED" : "RUNNING");
        executorNotification(notification);
    }
    void notifyUnrelated() { publish(STATUS_RUNNING); }
    void reconnectCompleted(bool success) override { if (success) ++succeeded;else ++failed; }
};

int main() {
    try {
        SPELLtime fractional(10,532,750,false),one(1,true);
        require(fractional+one==SPELLtime(11,532,750,false),"Addition lost fractional seconds");
        SPELLtime almost(5,999,999,true),micro(0,0,1,true);
        require(almost+micro==SPELLtime(6,true),"Addition failed fractional carry");
        SPELLtime newer(11,100,100,false),older(10,900,200,false);
        auto difference=newer-older;
        require(difference==SPELLtime(0,199,900,true) && difference.isDelta(),"Subtraction failed fractional borrow");
        auto assigned=fractional;assigned+=one;
        require(assigned==fractional+one,"Compound time addition differs");
        assigned=newer;assigned-=older;
        require(assigned==difference,"Compound time subtraction differs");
        require(older-newer==SPELLtime(0,true),"Negative difference did not saturate at zero");
        SPELLtime fullMicroseconds(10,532,532750,false);
        require(fullMicroseconds+one==fractional+one,"Python TIME fractional representation differs");
        bool overflow=false;
        try { auto invalid=SPELLtime(std::numeric_limits<unsigned long>::max(),true)+one;(void)invalid; }
        catch(const std::overflow_error&) { overflow=true; }
        require(overflow,"Native time overflow silently wrapped");
        std::cout<<"NATIVE_TIME_ARITHMETIC_CASES 8"<<std::endl;
        ModelProbe model;
        model.publish(STATUS_PAUSED);
        require(!model.waitStatus(STATUS_PAUSED,0),"Already reached status should not time out");
        model.publish(STATUS_RUNNING);
        std::thread transition([&]{std::this_thread::sleep_for(std::chrono::milliseconds(15));model.publish(STATUS_PAUSED);});
        bool timeout=model.waitStatus(STATUS_PAUSED,500);
        transition.join();require(!timeout,"Missed the requested status transition");
        model.publish(STATUS_RUNNING);
        std::thread noise([&]{for(int n=0;n<20;++n){model.notifyUnrelated();std::this_thread::sleep_for(std::chrono::milliseconds(10));}});
        auto start=std::chrono::steady_clock::now();
        timeout=model.waitStatus(STATUS_PAUSED,60);
        auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
        noise.join();
        require(timeout,"Unreached status did not time out");
        require(elapsed<160,"Unrelated status notifications extended the deadline");
        model.loggedIn(true);
        { LoginMonitor monitor(model,100);monitor.start();monitor.join(); }
        require(model.succeeded==1 && model.failed==0,"Login completion bypassed virtual owner routing");
        model.loggedIn(false);
        { LoginMonitor monitor(model,35);monitor.start();monitor.join(); }
        require(model.succeeded==1 && model.failed==1,"Login timeout bypassed virtual owner routing");
        start=std::chrono::steady_clock::now();
        { LoginMonitor monitor(model);monitor.start();monitor.stop();monitor.join(); }
        elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
        require(elapsed<500 && model.succeeded==1 && model.failed==1,"Cancelled monitor invoked an owner callback");
        std::cout<<"{\"status_cases\":3,\"login_success\":true,\"login_timeout\":true,\"login_cancelled\":true}"<<std::endl;
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; }
      catch (const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
