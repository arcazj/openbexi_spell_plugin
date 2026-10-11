// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_PRC/SPELLprocessManager.H"
#include "SPELL_UTIL/SPELLerror.H"
#include "SPELL_IPC/SPELLsocket.H"
#include "SPELL_IPC/SPELLipcIncoming.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include <sys/socket.h>
#include <signal.h>
#include <pthread.h>
#include <fcntl.h>
#include <unistd.h>
#include <atomic>
#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

void require(bool valid,const char* reason) { if (!valid) throw std::runtime_error(reason); }

class Restart final:public SPELLprocessListener {
public:
    std::atomic<int> finished{0},failures{0};
    void processStarted(const std::string) override {}
    void processFailed(const std::string) override { ++failures; }
    void processKilled(const std::string) override { ++failures; }
    void processFinished(const std::string id,const int& code) override {
        if (code!=0) ++failures;
        if (++finished==1) {
            // Reproduce removal/replacement from the monitor's own callback
            // while another thread still holds the original process in wait.
            SPELLprocessManager::instance().clearProcess(id);
            SPELLprocessManager::instance().startProcess(id,"/bin/sleep 0.02");
        }
    }
};

class IncomingListener final:public SPELLipcInterfaceListener {
public:
    bool fail=false;
    void processMessage(const SPELLipcMessage&) override { if (fail) throw std::runtime_error("handler failure"); }
    SPELLipcMessage processRequest(const SPELLipcMessage&) override {
        if (fail) throw std::runtime_error("handler failure");
        return SPELLipcMessage("response");
    }
    void processConnectionError(int,std::string,std::string) override {}
    void processConnectionClosed(int) override {}
};
class Interrupted final:public SPELLprocessListener {
public:
    std::atomic<pthread_t> worker{0};
    std::atomic<int> finished{0},failures{0};
    void processStarted(const std::string) override { worker=pthread_self(); }
    void processFinished(const std::string,const int& code) override { if (code==0) ++finished; else ++failures; }
    void processFailed(const std::string) override { ++failures; }
    void processKilled(const std::string) override { ++failures; }
};
void interruptWait(int) {}
int main(int argc,char**) {
    if (argc>1) {
        sigset_t mask;
        if (sigprocmask(SIG_SETMASK,nullptr,&mask)!=0) return 1;
        for (int value : {SIGINT,SIGTERM,SIGHUP,SIGQUIT})
            if (sigismember(&mask,value)) return 2;
        return 0;
    }
    try {
        for (int action=0;action<4;++action) {
            int pair[2]; require(socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0,"socketpair failed");
            auto socket=std::make_unique<SPELLsocket>(pair[0],"",std::vector<std::string>{});
            if (action==0) socket->close();
            if (action==1) socket->shutdownRead();
            if (action==2) socket->shutdownWrite();
            if (action==3) require(socket->shutdown()==0,"shutdown failed");
            int replacement=open("/dev/null",O_RDONLY);
            require(replacement==pair[0],"Descriptor reuse fixture failed");
            socket->close(); socket->shutdownRead(); socket->shutdownWrite(); socket->shutdown(); socket.reset();
            require(fcntl(replacement,F_GETFD)!=-1,"Repeated cleanup closed a reused descriptor");
            close(replacement); close(pair[1]);
        }
        IncomingListener listener;
        SPELLmutex channelLock;
        SPELLipcChannel* channel=nullptr;
        for (bool fail : {false,true}) {
            listener.fail=fail;
            SPELLipcMessage message("qualification");
            SPELLipcIncomingMessage incoming("message","qualification",message,listener);
            SPELLipcIncomingRequest request("request","qualification",message,channelLock,&channel,listener);
            for (SPELLipcIncomingBase* processor : {static_cast<SPELLipcIncomingBase*>(&incoming),static_cast<SPELLipcIncomingBase*>(&request)}) {
                bool rejected=false;
                try { processor->run(); } catch (const std::runtime_error&) { rejected=true; }
                require(rejected==fail,"Unexpected callback exception result");
                require(processor->isStarted() && processor->isFinished() && !processor->wait(10),"Failed handler did not signal completion");
            }
        }
        auto& manager=SPELLprocessManager::instance();
        sigset_t mask,previousMask;
        sigemptyset(&mask);
        for (int value : {SIGINT,SIGTERM,SIGHUP,SIGQUIT}) sigaddset(&mask,value);
        require(pthread_sigmask(SIG_BLOCK,&mask,&previousMask)==0,"Could not set parent signal mask");
        manager.startProcess("signal-mask","/out/qualify_process --signal-mask");
        require(manager.waitProcess("signal-mask")==0,"Child inherited blocked termination signals");
        manager.clearProcess("signal-mask");
        require(pthread_sigmask(SIG_SETMASK,&previousMask,nullptr)==0,"Could not restore signal mask");
        struct sigaction action{};
        action.sa_handler=interruptWait;
        sigemptyset(&action.sa_mask);
        require(sigaction(SIGUSR1,&action,nullptr)==0,"Could not install test interrupt");
        Interrupted interrupted;
        manager.addListener("interrupt",&interrupted);
        manager.startProcess("interrupt","/bin/sleep 0.3");
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        while (!interrupted.worker && std::chrono::steady_clock::now()<deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        require(interrupted.worker!=0,"Monitor thread did not start");
        for (int count=0;count<5;++count) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            require(pthread_kill(interrupted.worker,SIGUSR1)==0,"Could not interrupt monitor wait");
        }
        require(manager.waitProcess("interrupt")==0,"EINTR lost the child exit status");
        manager.clearProcess("interrupt");
        manager.removeListener("interrupt",&interrupted);
        require(interrupted.finished==1 && interrupted.failures==0,"Interrupted monitor emitted a false failure");

        for (int code: {0,7}) {
            std::string id="exit-"+std::to_string(code);
            manager.startProcess(id,"exit "+std::to_string(code));
            require(manager.waitProcess(id)==code,"Wrong child exit status");
            manager.clearProcess(id);
        }
        std::vector<std::unique_ptr<Restart>> listeners;
        for (int iteration=0;iteration<20;++iteration) {
            auto listener=std::make_unique<Restart>();
            std::string id="restart-"+std::to_string(iteration);
            manager.addListener(id,listener.get());
            manager.startProcess(id,"/bin/sleep 0.02");
            require(manager.waitProcess(id)==0,"Original child failed");
            require(manager.waitProcess(id)==0,"Replacement child failed");
            manager.clearProcess(id);
            require(listener->finished==2 && listener->failures==0,"Wrong callback lifecycle");
            listeners.push_back(std::move(listener));
        }
        manager.startProcess("duplicate","/bin/sleep 0.03");
        bool rejected=false;
        try { manager.startProcess("duplicate","/bin/true"); }
        catch (const SPELLcoreException&) { rejected=true; }
        require(rejected,"Duplicate process identifier accepted");
        require(manager.waitProcess("duplicate")==0,"Duplicate request damaged original child");
        manager.clearProcess("duplicate");
        std::cout << "{\"socket_reuse_cases\":4,\"exit_status_cases\":2,\"callback_restarts\":20,\"duplicate_rejected\":true,\"child_signal_mask_checks\":4,\"interrupted_waits\":1,\"incoming_completion_cases\":4}" << std::endl;
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
      catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    return 1;
}
