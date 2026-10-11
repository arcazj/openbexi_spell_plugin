// SPDX-License-Identifier: GPL-3.0-or-later
// Independent ownership probes against the original native IPC classes.
#include "SPELL_IPC/SPELLsocket.H"
#include "SPELL_IPC/SPELLipcClientInterface.H"
#include "SPELL_IPC/SPELLipcServerInterface.H"
#include "SPELL_IPC/SPELLipcError.H"
#include "SPELL_IPC/SPELLipcTrash.H"
#include "SPELL_IPC/SPELLipcIncoming.H"
#include "SPELL_IPC/SPELLipcInterfaceListener.H"
#include <sys/socket.h>
#include <netinet/in.h>
#include <dirent.h>
#include <unistd.h>
#include <atomic>
#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

void require(bool value,const char* reason) { if (!value) throw std::runtime_error(reason); }
int descriptors() {
    DIR* directory=opendir("/proc/self/fd");require(directory,"Cannot enumerate owned descriptors");
    int count=0;
    while (readdir(directory)) ++count;
    closedir(directory);return count;
}
class Listener final:public SPELLipcInterfaceListener {
public:
    void processMessage(const SPELLipcMessage&) override {}
    SPELLipcMessage processRequest(const SPELLipcMessage&) override { return SPELLipcMessage(); }
    void processConnectionError(int,std::string,std::string) override {}
    void processConnectionClosed(int) override {}
};
class OwnedWorker final:public SPELLipcIncomingBase {
    SPELLevent& gate;
    std::atomic_int& destroyed;
public:
    OwnedWorker(Listener& listener,SPELLevent& gate,std::atomic_int& destroyed):
        SPELLipcIncomingBase("owned","qualification",SPELLipcMessage("owned"),listener),gate(gate),destroyed(destroyed) {}
    ~OwnedWorker() override { ++destroyed; }
    void run() override { setStarted();gate.wait();finish(); }
};
class SlowListener final:public SPELLipcInterfaceListener {
public:
    std::atomic_int entered{0};
    SPELLevent release;
    SlowListener() { release.clear(); }
    void processMessage(const SPELLipcMessage&) override {}
    SPELLipcMessage processRequest(const SPELLipcMessage&) override {
        ++entered;release.wait();return SPELLipcMessage("response");
    }
    void processConnectionError(int,std::string,std::string) override {}
    void processConnectionClosed(int) override {}
};
void concurrentDisconnect() {
    Listener clientListener;SlowListener serverListener;
    SPELLipcServerInterface server("OWNERSHIP",0,0);
    server.initialize(&serverListener);server.connect();server.start();
    SPELLipcClientInterface client("OWNERSHIP","127.0.0.1",server.getPort());
    client.initialize(&clientListener);client.connect();
    std::atomic_int returned{0},failures{0};std::vector<std::thread> requests;
    for (int i=0;i<8;++i) requests.emplace_back([&] {
        try {
            SPELLipcMessage request("blocked");request.setType(MSG_TYPE_REQUEST);
            request.setSender("probe");request.setReceiver("server");
            client.sendRequest(request,500);
            ++returned;
        } catch (...) { ++failures; }
    });
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while (serverListener.entered<8 && std::chrono::steady_clock::now()<deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    const bool admitted=serverListener.entered==8;
    std::cout<<"CONCURRENT_REQUESTS_ADMITTED "<<serverListener.entered<<std::endl;
    // Server handlers remain blocked while the client revokes its channel and
    // cancels pending responses. Both owner calls must safely converge.
    std::thread first([&]{client.disconnect();});
    std::thread second([&]{client.disconnect();});
    first.join();second.join();
    for (auto& request:requests) request.join();
    std::cout<<"CLIENT_DISCONNECTED_WITH_PENDING_REQUESTS "<<returned<<std::endl;
    serverListener.release.set();server.disconnect();
    require(admitted,"Did not admit every concurrent IPC request");
    require(returned==8 && failures==0,"Disconnect lost or raised from pending requests");
}
int main() {
    try {
        int port=0;
        std::unique_ptr<SPELLsocket> listening(SPELLsocket::listen(&port));
        const int baseline=descriptors();
        for (int i=0;i<40;++i) {
            int occupied=port;bool rejected=false;
            try { std::unique_ptr<SPELLsocket> duplicate(SPELLsocket::listen(&occupied)); }
            catch (const SPELLipcError&) { rejected=true; }
            require(rejected,"Duplicate listener unexpectedly bound the owned port");
        }
        require(descriptors()==baseline,"Failed bind attempts leaked descriptors");
        int reserved=::socket(AF_INET,SOCK_STREAM,0);require(reserved>=0,"Cannot reserve refused port");
        sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
        require(::bind(reserved,reinterpret_cast<sockaddr*>(&address),sizeof(address))==0,"Cannot bind refused port");
        socklen_t size=sizeof(address);
        require(getsockname(reserved,reinterpret_cast<sockaddr*>(&address),&size)==0,"Cannot get refused port");
        const int reservedBaseline=descriptors();
        for (int i=0;i<100;++i) {
            bool rejected=false;
            try { std::unique_ptr<SPELLsocket> connection(SPELLsocket::connect("127.0.0.1",ntohs(address.sin_port))); }
            catch (const SPELLipcError&) { rejected=true; }
            require(rejected,"Connection to bound non-listening owned socket succeeded");
        }
        require(descriptors()==reservedBaseline,"Failed connects leaked descriptors");
        ::close(reserved);
        Listener listener;SPELLevent gate;gate.clear();std::atomic_int destroyed{0};
        SPELLipcTrash collector("ownership");collector.start();
        auto worker=std::make_unique<OwnedWorker>(listener,gate,destroyed);
        OwnedWorker* active=worker.get();
        require(collector.place(worker.get()),"Open collector refused worker");worker.release();
        active->waitStarted();
        std::atomic_bool shutdownDone{false};
        std::thread closing([&]{collector.shutdown();collector.join();shutdownDone=true;});
        std::this_thread::sleep_for(std::chrono::milliseconds(80));
        const bool waited=!shutdownDone.load();
        gate.set();closing.join();
        require(waited,"Shutdown returned before its admitted worker completed");
        require(destroyed==1,"Admitted worker was not destroyed exactly once");
        auto late=std::make_unique<OwnedWorker>(listener,gate,destroyed);
        require(!collector.place(late.get()),"Closed collector admitted new worker");
        require(!late->isStarted(),"Rejected worker started after collector shutdown");
        late.reset();require(destroyed==2,"Rejected worker lost caller ownership");
        concurrentDisconnect();
        std::cout<<"{\"failed_bind_attempts\":40,\"failed_connect_attempts\":100,\"descriptor_leaks\":0,\"shutdown_joins_admitted_worker\":true,\"closed_admission_rejected\":true,\"concurrent_cancelled_requests\":8,\"concurrent_disconnect_calls\":2}"<<std::endl;
        return 0;
    } catch (const SPELLipcError& error) { std::cerr<<error.what()<<std::endl; }
      catch (const std::exception& error) { std::cerr<<error.what()<<std::endl; }
    return 1;
}
