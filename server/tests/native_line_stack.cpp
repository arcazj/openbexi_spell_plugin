// SPDX-License-Identifier: GPL-3.0-or-later
#include "line_stack.H"
#include <atomic>
#include <cassert>
#include <cstdio>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>
static bool measuring=false;
static size_t allocations=0,allocatedBytes=0;
static void allocated(const volatile void*,size_t size){if(measuring){++allocations;allocatedBytes+=size;}}
static void freed(const volatile void*){}
extern "C" int __sanitizer_install_malloc_and_free_hooks(void(*)(const volatile void*,size_t),void(*)(const volatile void*));
#define ISTR(n) std::to_string(n)
using SPELLmonitor=std::lock_guard<std::recursive_mutex>;
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#include "SPELL_EXC/SPELLcallstackIF.H"
struct StackAdapter:SPELLcallstackIF {
    void reset() override {}
    unsigned getCurrentLine() override {return 0;}
    const std::string getCodeName() override {return {};}
    void stepOver(const SPELLstepOverMode&) override {}
    void setStage(const std::string&,const std::string&) override {}
    const std::string getStage() override {return {};}
    const void skipCurrentLine() override {}
    const bool isSteppingOver() override {return false;}
    void setRecoveryMode() override {}
    void moveToLevel(unsigned) override {}
    void enableNotifications(bool) override {}
};
#pragma GCC diagnostic pop
struct SPELLcallstack:StackAdapter {
    std::recursive_mutex m_lock;
    std::string m_stack,m_fullStackString;
    const std::string getStack();const std::string getFullStack();
    void v08StackInto(std::string&);void v08FullStackInto(std::string&);
};
struct SPELLexecutor {
    SPELLcallstack stack;
    static SPELLexecutor& instance(){static SPELLexecutor value;return value;}
    SPELLcallstackIF& getCallstack(){return stack;}
};
struct Audit {
    FILE* file;
    explicit Audit(const char* path):file(std::fopen(path,"wb")){assert(file);std::setvbuf(file,nullptr,_IONBF,0);}
    ~Audit(){assert(std::fclose(file)==0);}
    void writeLine(const std::string& text){assert(std::fwrite(text.data(),1,text.size(),file)==text.size());assert(std::fputc('\n',file)!=EOF);}
};
struct SPELLcif {
    bool m_errorState=false;
    std::recursive_mutex m_lineLock;
    std::string m_lastStack;
    Audit* m_asRun=nullptr;
    unsigned execution=1,notifications=0;
    std::function<void()> nested;
    std::string getAvailableStack();void v08AvailableStackInto(std::string&);void notifyLine();
    unsigned getNumExecutions()const{return execution;}
    void specificNotifyLine(){++notifications;if(nested)nested();}
};
namespace MessageField {const std::string FIELD_TIME="Time",FIELD_MSG_SEQUENCE="MsgSequence",FIELD_CSP="Csp",FIELD_EXECUTION_MODE="ExecutionMode";}
namespace MessageValue {const std::string DATA_EXEC_MODE_MANUAL="MANUAL",DATA_EXEC_MODE_PROCEDURE="PROCEDURE";}
namespace SPELLutils {static void timestamp(std::string& out){out="2026-10-27T00:00:00";}}
struct SPELLipcMessage {
    std::map<std::string,std::string> fields;
    void set(std::string key,std::string value){fields[key]=value;}
    std::string& getRef(std::string key){return fields[key];}
};
struct SPELLserverCif:SPELLcif {
    unsigned m_sequence=0;bool manual=false;
    bool isManual()const{return manual;}
    void completeMessage(SPELLipcMessage&);
};
#include "line_methods.inc"
static uint64_t digest(uint64_t result,const std::string& text){for(unsigned char c:text)result=(result^c)*UINT64_C(1099511628211);return result;}
static void nestedStorage(){
    std::vector<std::unique_ptr<V08LineStack>> leases;
    for(int i=0;i<16;++i){leases.emplace_back(new V08LineStack);leases.back()->value()=std::string(100,'a'+i);}
    for(int i=0;i<16;++i)assert(leases[i]->value()==std::string(100,'a'+i));
    {V08LineStack large;large.value().assign(100000,'x');}
    for(int i=0;i<16;++i)assert(leases[i]->value()==std::string(100,'a'+i));
}
int main(int argc,char**argv){
    assert(argc==2&&__sanitizer_install_malloc_and_free_hooks(allocated,freed)>0);
    nestedStorage();std::vector<std::thread> threads;
    for(int i=0;i<8;++i)threads.emplace_back(nestedStorage);
    for(auto& thread:threads)thread.join();
    auto& stack=SPELLexecutor::instance().stack;
#if V08_STACK_REUSE
    struct OtherStack:StackAdapter {
        const std::string getStack() override {return "alternate-stack";}
        const std::string getFullStack() override {return "alternate-full-stack";}
    } other;
    std::string copied;
    v08CopyCallstackSnapshot(other,copied,false);assert(copied=="alternate-stack");
    v08CopyCallstackSnapshot(other,copied,true);assert(copied=="alternate-full-stack");
#endif
    const std::string a="long-procedure-identifier-root#1:00001",b="long-procedure-identifier-root#1:00002";
    Audit audit(argv[1]);SPELLserverCif cif;cif.m_asRun=&audit;SPELLipcMessage message;
    stack.m_stack=a;stack.m_fullStackString.clear();cif.notifyLine();cif.notifyLine();assert(cif.notifications==1);
    cif.m_errorState=true;stack.m_stack=b;cif.notifyLine();assert(cif.notifications==1);cif.m_errorState=false;
    stack.m_fullStackString=u8"é中🙂/nested#0:42";cif.execution=4294967295u;cif.notifyLine();
    bool nested=false;cif.nested=[&]{if(!nested){nested=true;stack.m_fullStackString=b;cif.notifyLine();}};
    stack.m_fullStackString=a;cif.notifyLine();cif.nested={};assert(cif.notifications==4);
    for(const auto& value:{a,b}){stack.m_fullStackString=value;cif.completeMessage(message);}
    cif.m_lastStack=a;cif.execution=1;
    allocations=allocatedBytes=0;measuring=true;
    for(int i=0;i<10000;++i){stack.m_fullStackString=i%2?a:b;cif.notifyLine();}
    measuring=false;const auto notificationAllocations=allocations,notificationBytes=allocatedBytes;
    allocations=allocatedBytes=0;measuring=true;
    for(int i=0;i<10000;++i)cif.completeMessage(message);
    measuring=false;const auto metadataAllocations=allocations,metadataBytes=allocatedBytes;
    uint64_t hash=UINT64_C(14695981039346656037);
    for(bool manual:{false,true})for(unsigned count:{0u,1u,4294967295u}){
        cif.manual=manual;cif.execution=count;cif.completeMessage(message);
        assert(message.fields[MessageField::FIELD_CSP]==stack.m_fullStackString+"/"+ISTR(count));
        for(const auto& field:message.fields){hash=digest(hash,field.first);hash=digest(hash,field.second);}
    }
    std::printf("{\"notification_allocations\":%zu,\"notification_bytes\":%zu,\"metadata_allocations\":%zu,\"metadata_bytes\":%zu,\"metadata_digest\":%llu}\n",notificationAllocations,notificationBytes,metadataAllocations,metadataBytes,static_cast<unsigned long long>(hash));
}
