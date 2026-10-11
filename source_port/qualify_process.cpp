// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_PRC/SPELLprocessManager.H"
#include "SPELL_UTIL/SPELLerror.H"
#include "SPELL_IPC/SPELLsocket.H"
#include <sys/socket.h>
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

int main() {
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
        auto& manager=SPELLprocessManager::instance();
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
        std::cout << "{\"socket_reuse_cases\":4,\"exit_status_cases\":2,\"callback_restarts\":20,\"duplicate_rejected\":true}" << std::endl;
        return 0;
    } catch (const SPELLcoreException& error) { std::cerr << error.what() << std::endl; }
      catch (const std::exception& error) { std::cerr << error.what() << std::endl; }
    return 1;
}
