// SPDX-License-Identifier: GPL-3.0-or-later
#include "audit_file.H"
#include <csignal>
#include <sys/resource.h>
#include <thread>
#include <vector>
#ifdef V08_AUDIT_FAULT_WRAPPERS
static int fault=0, fault_calls=0;
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" int __real_fdatasync(int);
extern "C" ssize_t __wrap_write(int fd,const void* data,size_t size) {
    if(fd>2 && fault==1 && fault_calls++==0){errno=EINTR;return -1;}
    if(fd>2 && fault==2) {
        if(fault_calls++==0)return __real_write(fd,data,size/2);
        errno=ENOSPC;return -1;
    }
    return __real_write(fd,data,size);
}
extern "C" int __wrap_fdatasync(int fd) {
    if(fault==3){errno=EIO;return -1;}
    return __real_fdatasync(fd);
}
#endif
int main(int argc,char** argv) {
    if(argc<3)return 2;
    const std::string mode=argv[1],path=argv[2];
    V08AuditFile output;
    if(mode=="append") {
        output.open(path,true);output.write_line("RESTART");return 0;
    }
    if(mode=="restore") {
        if(argc!=4)return 2;
        output.open(path);output.copy_from(argv[3]);return 0;
    }
    if(mode=="quota") {
        std::signal(SIGXFSZ,SIG_IGN);
        const rlimit limit{64*1024,64*1024};
        if(::setrlimit(RLIMIT_FSIZE,&limit)!=0)return 3;
    }
    output.open(path);
#ifdef V08_AUDIT_FAULT_WRAPPERS
    if(mode=="interrupted" || mode=="partial-failure" || mode=="sync-failure") {
        output.write_line("BASE");
        fault=mode=="interrupted"?1:mode=="partial-failure"?2:3;
        output.write_line("UNCERTAIN-RECORD");
        std::puts("ACK");return 0;
    }
#endif
    if(mode=="normal") {
        std::vector<std::thread> threads;
        for(int t=0;t<4;++t)threads.emplace_back([&,t]{
            for(int i=0;i<100;++i)output.write_line(std::to_string(t)+":"+std::to_string(i));
        });
        for(auto& thread:threads)thread.join();
        return 0;
    }
    if(mode=="hold") {
        std::puts("READY");std::fflush(stdout);
        char c;return ::read(STDIN_FILENO,&c,1)==1?0:4;
    }
    if(mode=="quota" || mode=="full-disk") {
        // Every acknowledged record was synced. A failing record is preserved
        // as an uncertain tail; there is no retry or record deletion.
        const std::string record(4095,'x');
        for(unsigned int i=0;i<100000;++i) {
            output.write_line(record);
            std::printf("ACK %u\n",i);std::fflush(stdout);
        }
        return 5;
    }
    output.write_line("NEW");
}
