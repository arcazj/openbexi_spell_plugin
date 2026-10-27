// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <string>
#include <atomic>
#include <list>
#include <memory>
inline std::atomic<size_t> v08TestNodeAllocations{0};
template<class T> struct V08TestAllocator {
    using value_type=T;
    V08TestAllocator()=default;
    template<class U> V08TestAllocator(const V08TestAllocator<U>&) {}
    T* allocate(size_t n){v08TestNodeAllocations+=n;return std::allocator<T>{}.allocate(n);}
    void deallocate(T* p,size_t n){std::allocator<T>{}.deallocate(p,n);}
    template<class U> bool operator==(const V08TestAllocator<U>&)const{return true;}
    template<class U> bool operator!=(const V08TestAllocator<U>&)const{return false;}
};
inline std::atomic<size_t> v08TestConstructed{0};
#include <thread>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <utility>
#define DEBUG(x) do {} while(0)
#define LOG_INFO(x) do {} while(0)
#define ISTR(x) std::to_string(x)
class SPELLmutex { public: std::recursive_mutex value; };
struct SPELLmonitor { std::lock_guard<std::recursive_mutex> lock; SPELLmonitor(SPELLmutex& m):lock(m.value){} };
class SPELLevent {
    std::mutex mutex;std::condition_variable changed;bool cleared=false;
public:
    SPELLevent(bool=false){}
    void clear(){std::lock_guard<std::mutex> lock(mutex);cleared=true;}
    void set(){std::lock_guard<std::mutex> lock(mutex);cleared=false;changed.notify_all();}
    bool wait(long ms=5000){std::unique_lock<std::mutex> lock(mutex);return !changed.wait_for(lock,std::chrono::milliseconds(ms),[&]{return !cleared;});}
};
class SPELLthread {
    std::thread thread;
protected:
    std::string m_threadId;
    void v08ResetThreadId(const std::string& id){m_threadId=id;}
    bool v08ReleaseThreadId(){bool b=m_threadId.capacity()<=1024;m_threadId.clear();return b;}
public:
    SPELLthread(std::string id):m_threadId(std::move(id)){++v08TestConstructed;}
    virtual ~SPELLthread()=default;
    virtual void run()=0;
    void start(){thread=std::thread([this]{doRun();});}
    void join(){if(thread.joinable())thread.join();}
    void doRun(){run();}
    void setRunning(bool){}
};
class SPELLipcMessage {
    std::string id;int key=0,sequence=0;
public:
    SPELLipcMessage(std::string value=""):id(std::move(value)){}
    int getKey()const{return key;}
    int getSequence()const{return sequence;}
    std::string getSequenceStr()const{return std::to_string(sequence);}
    std::string getId()const{return id;}
    std::string getSender()const{return "sender";}
    std::string getReceiver()const{return "receiver";}
    void setSender(const std::string&){} void setReceiver(const std::string&){}
    void setSequence(int value){sequence=value;}
    void clear(){id.clear();} bool isVoid()const{return id.empty();}
};
struct SPELLipcOutput {void send(SPELLipcMessage&){};};
struct SPELLipcChannel {SPELLipcOutput output;SPELLipcOutput& getWriter(){return output;}};
struct SPELLipcInterfaceListener {
    virtual ~SPELLipcInterfaceListener()=default;
    virtual void processMessage(const SPELLipcMessage&)=0;
    virtual SPELLipcMessage processRequest(const SPELLipcMessage&)=0;
};
