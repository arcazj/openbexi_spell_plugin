// SPDX-License-Identifier: GPL-3.0-or-later
#include "audit_file.H"
#include <csignal>
#include <sys/resource.h>
#include <sys/mman.h>
#include <thread>
#include <vector>
#ifdef V08_AUDIT_FAULT_WRAPPERS
static int fault=0, fault_calls=0;
static bool record_synced=false;
static bool ignored_range_revisited=false;
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" int __real_fdatasync(int);
extern "C" int __real_posix_fadvise(int,off_t,off_t,int);
extern "C" ssize_t __wrap_write(int fd,const void* data,size_t size) {
    if(fd>2)record_synced=false;
    if(fd>2 && fault==1 && fault_calls++==0){errno=EINTR;return -1;}
    if(fd>2 && fault==2) {
        if(fault_calls++==0)return __real_write(fd,data,size/2);
        errno=ENOSPC;return -1;
    }
    if(fd>2 && fault==4 && fault_calls++==0) {
        const auto written=__real_write(fd,data,size/2);
        if(written<0)return written;
        const char marker[]="PARTIAL\n";
        if(__real_write(STDOUT_FILENO,marker,sizeof(marker)-1)!=sizeof(marker)-1)_exit(75);
        char permission;
        if(::read(STDIN_FILENO,&permission,1)!=1)_exit(75);
        return written;
    }
    return __real_write(fd,data,size);
}
extern "C" int __wrap_fdatasync(int fd) {
    if(fault==3){errno=EIO;return -1;}
    const int result=__real_fdatasync(fd);
    if(result==0)record_synced=true;
    return result;
}
extern "C" int __wrap_posix_fadvise(int fd,off_t offset,off_t length,int advice) {
    if(fault==5)return EOPNOTSUPP;
    if(fault==6 && (!record_synced || advice!=POSIX_FADV_DONTNEED ||
        offset % ::sysconf(_SC_PAGESIZE)!=0 || length<=0 ||
        length % ::sysconf(_SC_PAGESIZE)!=0))_exit(76);
    // A legal successful advisory no-op must not permanently exclude the
    // first four completed batches from subsequent advice. No bytes are lost.
    if(fault==7) {
        if(!record_synced || advice!=POSIX_FADV_DONTNEED)_exit(76);
        if(fault_calls++<4)return 0;
        if(offset==0 && length>=4*65536)ignored_range_revisited=true;
    }
    return __real_posix_fadvise(fd,offset,length,advice);
}
#endif
static int report_cache(const std::string& path) {
    // Observe residency before any verification read can repopulate the cache.
    const int input=::open(path.c_str(),O_RDONLY|O_CLOEXEC);
    if(input<0)return 7;
    struct stat info{};
    if(::fstat(input,&info)!=0 || info.st_size<=0)return 7;
    const auto pages=static_cast<size_t>((info.st_size+::sysconf(_SC_PAGESIZE)-1)/::sysconf(_SC_PAGESIZE));
    std::vector<unsigned char> resident(pages);
    void* view=::mmap(nullptr,info.st_size,PROT_READ,MAP_SHARED,input,0);
    if(view==MAP_FAILED || ::mincore(view,info.st_size,resident.data())!=0)return 7;
    size_t cached=0;for(const auto page:resident)if(page&1)++cached;
    if(::munmap(view,info.st_size)!=0 || ::close(input)!=0)return 7;
    std::printf("CACHE %zu %zu\n",cached,pages);return 0;
}
int main(int argc,char** argv) {
    if(argc<3)return 2;
    const std::string mode=argv[1],path=argv[2];
    V08AuditFile output;
    if(mode=="append") {
        output.open(path,true);output.write_line("RESTART");return 0;
    }
    if(mode=="restore" || mode=="cache-restore") {
        if(argc!=4)return 2;
        output.open(path);output.copy_from(argv[3]);
        if(mode=="cache-restore")return report_cache(path);
        return 0;
    }
    if(mode=="quota") {
        std::signal(SIGXFSZ,SIG_IGN);
        const rlimit limit{64*1024,64*1024};
        if(::setrlimit(RLIMIT_FSIZE,&limit)!=0)return 3;
    }
    output.open(path);
#ifdef V08_AUDIT_FAULT_WRAPPERS
    if(mode=="cache-probe" || mode=="cache-refusal" || mode=="cache-revisit") {
        fault=mode=="cache-probe"?6:mode=="cache-revisit"?7:5;
        const std::string record(65535,'z');
        for(unsigned int i=0;i<1024;++i)output.write_line(record);
        if(mode=="cache-revisit")std::printf("REVISITED %u\n",ignored_range_revisited);
        return report_cache(path);
    }
#endif
#ifdef V08_AUDIT_FAULT_WRAPPERS
    if(mode=="interrupted" || mode=="partial-failure" || mode=="sync-failure" || mode=="partial-crash") {
        output.write_line("BASE");
        fault=mode=="interrupted"?1:mode=="partial-failure"?2:mode=="sync-failure"?3:4;
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
    if(mode=="acknowledged-crash") {
        for(unsigned int i=0;i<128;++i)output.write_line("COMMITTED:"+std::to_string(i));
        std::puts("ACK 128");std::fflush(stdout);
        char c;return ::read(STDIN_FILENO,&c,1)==1?0:4;
    }
    if(mode=="quota" || mode=="full-disk") {
        // Every acknowledged record was synced. A failing record is preserved
        // as an uncertain tail; there is no retry or record deletion.
        std::string record(4095,'x');
        for(unsigned int i=0;i<100000;++i) {
            char sequence[17];std::snprintf(sequence,sizeof(sequence),"%016u",i);
            record.replace(0,16,sequence);
            output.write_line(record);
            std::printf("ACK %u\n",i);std::fflush(stdout);
        }
        return 5;
    }
    output.write_line("NEW");
}
