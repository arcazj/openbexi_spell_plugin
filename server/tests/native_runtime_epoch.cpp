// SPDX-License-Identifier: GPL-3.0-or-later
// Actual epoch reader, JSON encoder, Unix peer pin and admission exchange.
#include "admission_ipc.H"
#include <atomic>
#include <cassert>
#include <cstdarg>
#include <dirent.h>
#include <fcntl.h>
#include <iostream>
#include <thread>
#include <vector>
#include <pthread.h>

#ifdef V08_FROZEN_EPOCH
static std::string v08_read_runtime_epoch(const char* path) {
    std::ifstream stream(path);std::string epoch;std::getline(stream,epoch);
    if(!stream || epoch.size()!=36 || stream.peek()!=EOF)
        throw std::runtime_error("Native runtime epoch unavailable");
    return epoch;
}
#endif
static std::string epochPath;
static std::atomic<int> lastEpochFd{-1}, fault{0}, reads{0};
static std::atomic<bool> entered{false};
extern "C" int __real_open(const char*,int,...);
extern "C" ssize_t __real_read(int,void*,size_t);
extern "C" ssize_t __real___read_chk(int,void*,size_t,size_t);
extern "C" int __wrap_open(const char* path,int flags,...) {
    mode_t mode=0;
    if(flags&O_CREAT){va_list arguments;va_start(arguments,flags);mode=va_arg(arguments,int);va_end(arguments);}
    const int fd=__real_open(path,flags,mode);
    if(fd>=0 && epochPath==path) {
        assert((fcntl(fd,F_GETFD)&FD_CLOEXEC)!=0);
        lastEpochFd=fd;
    }
    return fd;
}
extern "C" ssize_t __wrap_read(int fd,void* bytes,size_t size) {
    if(fd==lastEpochFd.load() && fault.load()) {
        const int mode=fault.load();const int serial=++reads;
        if(mode==1) {
            if(serial==1){errno=EINTR;return -1;}
            size=std::min(size,size_t(4));
        } else if(mode==2){errno=EIO;return -1;}
        else if(mode==3){entered=true;for(;;){pthread_testcancel();sched_yield();}}
    }
    return __real_read(fd,bytes,size);
}
extern "C" ssize_t __wrap___read_chk(int fd,void* bytes,size_t size,size_t available) {
    if(size>available)return __real___read_chk(fd,bytes,size,available);
    return __wrap_read(fd,bytes,size);
}
extern "C" size_t __sanitizer_get_heap_size(void);
extern "C" size_t __sanitizer_get_current_allocated_bytes(void);
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*,size_t),void (*)(const volatile void*));
static std::atomic<uint64_t> eightKiB{0};
static void allocation(const volatile void*,size_t size){if(size==8192)++eightKiB;}
static void freed(const volatile void*){}
static const std::string A="11111111-1111-4111-8111-111111111111";
static const std::string B="22222222-2222-4222-8222-222222222222";

static int descriptors() {
    auto* directory=opendir("/proc/self/fd");assert(directory);
    int count=0;while(readdir(directory))++count;closedir(directory);return count;
}
static void replaceEpoch(const std::string& value) {
    const auto next=epochPath+".next";
    const int fd=::open(next.c_str(),O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);assert(fd>=0);
    assert(write(fd,value.data(),value.size())==static_cast<ssize_t>(value.size()));
    assert(write(fd,"\n",1)==1);assert(close(fd)==0);
    assert(rename(next.c_str(),epochPath.c_str())==0);
}
static void measure(const char* socketPath) {
    assert(__sanitizer_install_malloc_and_free_hooks(allocation,freed)>0);
    const auto agent=std::to_string(getpid());
    assert(setenv("OPENBEXI_V08_RUNTIME_EPOCH",epochPath.c_str(),1)==0);
    assert(setenv("OPENBEXI_V08_ADMISSION_SOCKET",socketPath,1)==0);
    assert(setenv("OPENBEXI_V08_AGENT_PID",agent.c_str(),1)==0);
    constexpr int requests=10000;
    int listener=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);assert(listener>=0);
    sockaddr_un address{};address.sun_family=AF_UNIX;
    assert(strlen(socketPath)<sizeof(address.sun_path));strcpy(address.sun_path,socketPath);
    assert(bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address))==0);
    assert(listen(listener,16)==0);
    std::atomic<int> observed{0};
    std::thread provider([&] {
        for(int index=0;index<requests;++index) {
            const int peer=accept(listener,nullptr,nullptr);assert(peer>=0);
            std::string packet;char bytes[256];
            while(packet.find('\n')==std::string::npos) {
                const auto count=::read(peer,bytes,sizeof(bytes));assert(count>0);
                packet.append(bytes,static_cast<size_t>(count));assert(packet.size()<1024);
            }
            auto body=nlohmann::json::parse(packet);
            assert(body.size()==3 && body["schema"]=="epoch-component" && body["sequence"]==index && body["runtime_epoch"]==(index<requests/2?A:B));
            if(index==requests/2-1)replaceEpoch(B);
            assert(write(peer,"ALLOW\n",6)==6);close(peer);++observed;
        }
    });
    const auto beforeHeap=__sanitizer_get_heap_size();
    const auto beforeLive=__sanitizer_get_current_allocated_bytes();
    const auto beforeEight=eightKiB.load();
    for(int index=0;index<requests;++index)
        v08_native_request({{"schema","epoch-component"},{"sequence",index}});
    provider.join();close(listener);unlink(socketPath);
    assert(observed==requests);
    const auto afterHeap=__sanitizer_get_heap_size();
    const auto afterLive=__sanitizer_get_current_allocated_bytes();
    std::cout<<"{\"requests\":"<<observed<<",\"fresh_epoch_rotated\":true,\"file_buffer_allocations\":"<<(eightKiB.load()-beforeEight)
        <<",\"heap_growth_bytes\":"<<(afterHeap-beforeHeap)<<",\"live_before\":"<<beforeLive
        <<",\"live_after\":"<<afterLive<<"}\n";
}
static void measureReader() {
    assert(__sanitizer_install_malloc_and_free_hooks(allocation,freed)>0);
    const auto beforeHeap=__sanitizer_get_heap_size();
    const auto beforeLive=__sanitizer_get_current_allocated_bytes();
    const auto beforeEight=eightKiB.load();
    for(int count=0;count<10000;++count)assert(v08_read_runtime_epoch(epochPath.c_str())==A);
    const auto afterHeap=__sanitizer_get_heap_size();
    const auto afterLive=__sanitizer_get_current_allocated_bytes();
    std::cout<<"{\"reads\":10000,\"file_buffer_allocations\":"<<(eightKiB.load()-beforeEight)
        <<",\"heap_growth_bytes\":"<<(afterHeap-beforeHeap)<<",\"live_before\":"<<beforeLive
        <<",\"live_after\":"<<afterLive<<"}\n";
}
int main(int argc,char** argv) {
    assert(argc>=3);const std::string mode=argv[1];epochPath=argv[2];
    if(mode=="read") {
        try {const auto value=v08_read_runtime_epoch(epochPath.c_str());std::cout<<nlohmann::json({{"accepted",true},{"value",value}}).dump()<<'\n';}
        catch(const std::exception&){std::cout<<"{\"accepted\":false}\n";}
    } else if(mode=="measure"){assert(argc==4);measure(argv[3]);}
    else if(mode=="measure-reader")measureReader();
    else if(mode=="faults") {
        fault=1;assert(v08_read_runtime_epoch(epochPath.c_str())==A);
        assert(reads>=11);
        assert(fcntl(lastEpochFd,F_GETFD)==-1 && errno==EBADF);
        fault=2;
        try{v08_read_runtime_epoch(epochPath.c_str());assert(false);}catch(const std::runtime_error&){}
        assert(fcntl(lastEpochFd,F_GETFD)==-1 && errno==EBADF);
        fault=0;assert(v08_read_runtime_epoch(epochPath.c_str())==A);
        std::cout<<"{\"partial_eintr_read_error_and_close\":true}\n";
    } else if(mode=="concurrent") {
        const int before=descriptors();std::atomic<int> observations{0};
        std::vector<std::thread> readers;
        for(int index=0;index<8;++index)readers.emplace_back([&]{for(int count=0;count<1000;++count){const auto value=v08_read_runtime_epoch(epochPath.c_str());assert(value==A||value==B);++observations;}});
        for(int count=0;count<100;++count)replaceEpoch(count%2?A:B);
        for(auto& reader:readers)reader.join();
        replaceEpoch(B);assert(v08_read_runtime_epoch(epochPath.c_str())==B);
        assert(before==descriptors() && observations==8000);
        std::cout<<"{\"concurrent_reads\":8000,\"fresh_rotation\":true,\"fd_leak\":false}\n";
    } else if(mode=="cancel") {
        const int before=descriptors();fault=3;
        pthread_t reader{};
        assert(pthread_create(&reader,nullptr,[](void*)->void*{v08_read_runtime_epoch(epochPath.c_str());return nullptr;},nullptr)==0);
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        while(!entered){assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();}
        assert(pthread_cancel(reader)==0);void* status=nullptr;assert(pthread_join(reader,&status)==0 && status==PTHREAD_CANCELED);
        fault=0;assert(fcntl(lastEpochFd,F_GETFD)==-1 && errno==EBADF);
        assert(before==descriptors());
        std::cout<<"{\"cancelled_read_closed_owned_fd\":true}\n";
    } else assert(false);
}
