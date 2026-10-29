// SPDX-License-Identifier: GPL-3.0-or-later
// Component environment around verbatim Context methods. The native transport,
// executor startup/binding, logging and service registry are explicit test seams.
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#define DEBUG(x) do {} while (false)
#define LOG_INFO(x) do {} while (false)
#define LOG_ERROR(x) do {} while (false)
#define THROW_EXCEPTION(a,b,c) throw SPELLcoreException(std::string(a) + ": " + (b))
constexpr int CLIENT_MODE_BACKGROUND=1, OPEN_MODE_VISIBLE=1;
struct SPELLcoreException : std::runtime_error { using std::runtime_error::runtime_error; };
namespace ExecutorMessages { const std::string ACKNOWLEDGE="ACKNOWLEDGE"; }
namespace MessageField { const std::string FIELD_PROC_ID="ProcId"; }
struct SPELLipcMessage {
    std::string id="ACKNOWLEDGE";
    std::map<std::string,std::string> fields{{"ProcId","child#0"},{"MsgSequence","17"}};
    std::string getId() const { return id; }
    std::string get(const std::string& key) const { auto it=fields.find(key); return it==fields.end()?"":it->second; }
};
struct Interleaving {
    std::mutex mutex;
    std::condition_variable changed;
    bool binding_entered=false, publish=false, ack_done=false, registry_attempt=false;
    bool fail_start=false;
    template<class F> void wait(F condition) {
        std::unique_lock<std::mutex> lock(mutex);
        if (!changed.wait_for(lock,std::chrono::seconds(3),condition))
            throw std::runtime_error("component interleaving timed out");
    }
} interleaving;
thread_local bool ack_thread=false;
struct SPELLmutex {
    std::recursive_mutex value;
    void lock() {
        if (ack_thread) {
            std::lock_guard<std::mutex> lock(interleaving.mutex);
            interleaving.registry_attempt=true; interleaving.changed.notify_all();
        }
        value.lock();
    }
    void unlock() { value.unlock(); }
};
struct SPELLmonitor {
    SPELLmutex& mutex;
    explicit SPELLmonitor(SPELLmutex& value):mutex(value) { mutex.lock(); }
    ~SPELLmonitor() { mutex.unlock(); }
};
struct SPELLexecutorStartupParams {
    int getClientMode() const { return 0; }
    int getOpenMode() const { return OPEN_MODE_VISIBLE; }
    void setContextName(const std::string&) {}
    void setConfigFile(const std::string&) {}
};
struct SPELLconfiguration {
    static SPELLconfiguration& instance() { static SPELLconfiguration value; return value; }
    std::string getFile() { return "fixture.xml"; }
};
struct Model {
    std::string getInstanceId() const { return "child#0"; }
    std::string getProcId() const { return "child"; }
    int getInstanceNum() const { return 0; }
};
struct SPELLclient { void processMessageFromClient(const SPELLipcMessage&); };
struct SPELLexecutor;
std::vector<SPELLexecutor*> allocations;
std::atomic<int> delivered{0};
struct SPELLexecutor {
    SPELLclient* owner;
    Model model;
    SPELLexecutor(const SPELLexecutorStartupParams&, SPELLclient* client):owner(client) { allocations.push_back(this); }
    Model& getModel() { return model; }
    SPELLclient* getControllingClient() { return owner; }
    void start() {
        {
            std::lock_guard<std::mutex> lock(interleaving.mutex);
            interleaving.binding_entered=true; interleaving.changed.notify_all();
        }
        interleaving.wait([] { return interleaving.publish; });
        if (interleaving.fail_start) throw SPELLcoreException("identity binding rejected");
    }
    void sendMessageToExecutor(const SPELLipcMessage& message) {
        if (message.get("ProcId")!="child#0" || message.get("MsgSequence")!="17")
            throw std::runtime_error("ACK fields changed");
        ++delivered;
    }
};
struct SPELLserviceManager {
    static SPELLserviceManager& instance() { static SPELLserviceManager value; return value; }
    SPELLexecutor* getService(const std::string&) { throw SPELLcoreException("No such executor"); }
};
std::string noInstanceId(const std::string& value) { return value.substr(0,value.find('#')); }
struct SPELLexecutorManager {
    using ExecutorMap=std::map<std::string,SPELLexecutor*>;
    ExecutorMap m_executors;
    SPELLmutex m_lock;
    std::string m_contextName="fixture";
    static SPELLexecutorManager& instance() { static SPELLexecutorManager value; return value; }
    void startExecutor(SPELLexecutorStartupParams&,SPELLclient*);
    void recoverExecutor(SPELLexecutorStartupParams&,SPELLclient*);
    SPELLexecutor* getExecutor(const std::string&);
    void acknowledgeExecutor(const SPELLipcMessage&,SPELLclient*);
    void addInstanceNumber(const std::string&,int) {}
    void addExecutorModel(SPELLexecutor* value) { m_executors.emplace(value->getModel().getInstanceId(),value); }
    void deleteExecutorFiles(const SPELLexecutorStartupParams&) {}
};

// VERBATIM_METHODS

int main(int argc,char** argv) {
    if (argc!=2) return 2;
    std::string mode=argv[1];
    auto& manager=SPELLexecutorManager::instance();
    SPELLclient owner, observer;
    SPELLexecutorStartupParams config;
    SPELLipcMessage message;
    bool wrong_owner=mode.find("observer")!=std::string::npos;
    bool fail=mode.find("failed")!=std::string::npos;
    bool recover=mode.find("recover")!=std::string::npos;
    bool immediate=mode=="published" || mode=="nonack" || mode=="unknown" || mode=="command";
    bool failed_start=false, premature=false;
    if (immediate) {
        if (mode!="unknown") manager.addExecutorModel(new SPELLexecutor(config,&owner));
        if (mode=="nonack") {
            message.id="CMD_RUN";
#ifdef CANDIDATE
            manager.acknowledgeExecutor(message,&owner);
#endif
        } else {
            if (mode=="command") message.id="CMD_RUN";
            owner.processMessageFromClient(message);
        }
    } else {
        interleaving.fail_start=fail;
        std::thread startup([&] {
            try {
                if (recover) manager.recoverExecutor(config,&owner);
                else manager.startExecutor(config,&owner);
            } catch (const SPELLcoreException&) { failed_start=true; }
        });
        interleaving.wait([] { return interleaving.binding_entered; });
        std::thread acknowledgement([&] {
            ack_thread=true;
            (wrong_owner?observer:owner).processMessageFromClient(message);
            std::lock_guard<std::mutex> lock(interleaving.mutex);
            interleaving.ack_done=true; interleaving.changed.notify_all();
        });
        interleaving.wait([] { return interleaving.registry_attempt || interleaving.ack_done; });
        {
            std::lock_guard<std::mutex> lock(interleaving.mutex);
            premature=interleaving.ack_done;
            interleaving.publish=true; interleaving.changed.notify_all();
        }
        startup.join(); acknowledgement.join();
    }
    int expected=wrong_owner || fail || mode=="unknown" || mode=="nonack" ? 0 : 1;
    bool okay=delivered==expected && failed_start==fail;
#ifdef CANDIDATE
    okay=okay && !premature;
#endif
    std::cout << "{\"case\":\"" << mode << "\",\"delivered\":" << delivered
              << ",\"expected\":" << expected << ",\"before_publication_return\":" << premature
              << ",\"startup_failed\":" << failed_start << "}\n";
    manager.m_executors.clear();
    for(auto* allocation:allocations) delete allocation;
    if (!okay) { std::cerr << "ACK routing component assertion failed\n"; return 41; }
    return 0;
}
