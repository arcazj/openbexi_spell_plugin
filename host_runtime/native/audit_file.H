// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_AUDIT_FILE_H
#define OPENBEXI_V08_AUDIT_FILE_H
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <string>
#include <string_view>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <unistd.h>

// No asynchronous queue and no retained record buffer. Each successful write
// has reached fdatasync. A failure terminates this participant before another
// record/effect can be reported as successful. No record is retried after an
// uncertain write or sync result. Error messages contain fixed labels only.
class V08AuditFile {
    int directory=-1, file=-1;
    off_t advised=0;
    long page_size=0;
    std::string name;
    std::recursive_mutex mutex;
    [[noreturn]] static void failed(const char* stage, int code=errno) noexcept {
        char message[128];
        const int size=std::snprintf(message,sizeof(message),
            "V08_AUDIT_FAILURE stage=%s errno=%d\n",stage,code);
        if(size>0 && static_cast<size_t>(size)<sizeof(message)) {
            const auto ignored=::write(STDERR_FILENO,message,static_cast<size_t>(size));
            (void)ignored;
        }
        _exit(74);
    }
    static void sync_directory(int fd) {
        if(::fsync(fd)!=0)failed("directory_sync");
    }
    void raw_write(std::string_view bytes) {
        while(!bytes.empty()) {
            const auto size=::write(file,bytes.data(),bytes.size());
            if(size<0 && errno==EINTR)continue;
            if(size<=0)failed("write",size<0?errno:EIO);
            bytes.remove_prefix(static_cast<size_t>(size));
        }
    }
    void release_synced_pages(bool final=false) {
        // Audit records remain on the same durable volume. Bound the writer's
        // clean page cache as well as its userspace buffer: the measured hour
        // previously retained roughly one page-cache byte per audit byte.
        // Never advise dirty/uncertain data or alter cgroup accounting. Partial
        // pages stay cached; a reader may fault committed pages back from disk.
        struct stat contents{};
        if(::fstat(file,&contents)!=0)failed("cache_stat");
        const off_t complete=contents.st_size-(contents.st_size%page_size);
        if(complete<=0 || (!final && complete-advised<65536))return;
        // Successful advice is not an eviction receipt. Earlier completed
        // pages can remain resident or be refaulted. Revisit the synced prefix
        // instead of treating a monotonic advisory cursor as proof of release.
        const int result=::posix_fadvise(file,0,complete,POSIX_FADV_DONTNEED);
        // A platform refusing the bounded-cache policy cannot silently claim
        // success. fadvise returns an error code, rather than setting errno.
        if(result!=0)failed("cache_advice",result);
        advised=complete;
    }
    void sync_record(const char* stage) {
        if(::fdatasync(file)!=0)failed(stage);
        release_synced_pages();
    }
    void verify(int fd) {
        struct stat info{};
        if(::fstat(fd,&info)!=0)failed("file_stat");
        if(!S_ISREG(info.st_mode) || info.st_uid!=::geteuid() ||
           (info.st_mode&0077)!=0)failed("file_policy",EPERM);
        if(::flock(fd,LOCK_EX|LOCK_NB)!=0)failed("writer_lock");
    }
    void archive_existing() {
        const int old=::openat(directory,name.c_str(),O_RDWR|O_CLOEXEC|O_NOFOLLOW);
        if(old<0) {
            if(errno==ENOENT)return;
            failed("archive_open");
        }
        verify(old);
        if(::fdatasync(old)!=0)failed("archive_sync");
        // linkat is exclusive: never overwrite a previous generation. A crash
        // between link and unlink leaves two durable names for the old inode.
        bool linked=false;
        for(unsigned int generation=0;generation<1024;++generation) {
            const std::string saved=name+".archive."+std::to_string(generation);
            if(::linkat(directory,name.c_str(),directory,saved.c_str(),0)==0) {
                linked=true;break;
            }
            if(errno!=EEXIST)failed("archive_link");
        }
        if(!linked)failed("archive_capacity",ENOSPC);
        sync_directory(directory);
        if(::unlinkat(directory,name.c_str(),0)!=0)failed("archive_unlink");
        sync_directory(directory);
        if(::close(old)!=0)failed("archive_close");
    }
public:
    static std::string location(const std::string& previous) {
        const char* root=std::getenv("OPENBEXI_V08_AUDIT_ROOT");
        if(!root || root[0]!='/' || !root[1])failed("missing_durable_root",EINVAL);
        const auto slash=previous.rfind('/');
        return std::string(root)+"/"+previous.substr(slash==std::string::npos?0:slash+1);
    }
    V08AuditFile()=default;
    V08AuditFile(const V08AuditFile&)=delete;
    V08AuditFile& operator=(const V08AuditFile&)=delete;
    ~V08AuditFile(){close();}
    void open(const std::string& path, bool append=false) {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        close();
        const auto slash=path.rfind('/');
        if(slash==std::string::npos || slash==0 || slash+1==path.size())
            failed("path_policy",EINVAL);
        name=path.substr(slash+1);
        if(name=="." || name=="..")failed("path_policy",EINVAL);
        directory=::open(path.substr(0,slash).c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);
        if(directory<0)failed("directory_open");
        struct stat info{};struct statfs filesystem{};
        if(::fstat(directory,&info)!=0 || ::fstatfs(directory,&filesystem)!=0)
            failed("directory_stat");
        // tmpfs/ramfs have no durable backing. Named/bind disk volumes retain
        // page-cache charges in the writer's cgroup; no accounting subtraction.
        if(info.st_uid!=::geteuid() || (info.st_mode&0077)!=0 ||
           filesystem.f_type==0x01021994 || filesystem.f_type==0x858458f6)
            failed("directory_policy",EPERM);
        if(!append)archive_existing();
        file=::openat(directory,name.c_str(),O_RDWR|O_APPEND|O_CLOEXEC|O_NOFOLLOW|
            (append?0:O_CREAT|O_EXCL),0600);
        if(file<0)failed("file_open");
        verify(file);
        page_size=::sysconf(_SC_PAGESIZE);
        if(page_size<=0)failed("page_size",EINVAL);
        advised=0;
        struct stat contents{};
        if(::fstat(file,&contents)!=0)failed("file_stat");
        if(append && contents.st_size>0) {
            char last=0;
            if(::pread(file,&last,1,contents.st_size-1)!=1 || last!='\n')
                failed("incomplete_tail",EILSEQ);
        }
        sync_directory(directory);
    }
    void write(std::string_view bytes) {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        if(file<0)failed("closed_writer",EBADF);
        raw_write(bytes);
        sync_record("record_sync");
    }
    void write_line(std::string_view bytes) {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        if(file<0)failed("closed_writer",EBADF);
        raw_write(bytes);raw_write("\n");
        sync_record("record_sync");
    }
    void write_parts(std::string_view prefix,std::string_view payload) {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        if(file<0)failed("closed_writer",EBADF);
        raw_write(prefix);raw_write(payload);raw_write("\n");
        sync_record("record_sync");
    }
    void copy_from(const std::string& source) {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        const int input=::open(source.c_str(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
        if(input<0)failed("restore_open");
        struct stat info{};
        if(::fstat(input,&info)!=0 || !S_ISREG(info.st_mode))failed("restore_policy",EINVAL);
        if(::flock(input,LOCK_SH|LOCK_NB)!=0)failed("restore_lock");
        // Source is a retained operator snapshot, never the current output.
        struct stat output{};
        if(::fstat(file,&output)!=0 ||
           (info.st_dev==output.st_dev && info.st_ino==output.st_ino))
            failed("restore_identity",EINVAL);
        char buffer[4096];
        off_t copied=0, input_released=0;
        while(copied<info.st_size) {
            const auto remaining=info.st_size-copied;
            const auto requested=remaining<static_cast<off_t>(sizeof(buffer))?
                static_cast<size_t>(remaining):sizeof(buffer);
            const auto count=::read(input,buffer,requested);
            if(count<0 && errno==EINTR)continue;
            if(count<0)failed("restore_read");
            if(count==0)failed("restore_changed",EIO);
            raw_write(std::string_view(buffer,static_cast<size_t>(count)));
            copied+=count;
            // Restore has a fixed 4 KiB copy buffer. Sync output before asking
            // to release its completed pages; stop retaining consumed input
            // pages too. Input advice cannot discard dirty data or file bytes.
            const off_t consumed=copied-(copied%page_size);
            if(consumed-input_released>=65536) {
                sync_record("restore_sync");
                const int result=::posix_fadvise(input,0,consumed,POSIX_FADV_DONTNEED);
                if(result!=0)failed("restore_cache_advice",result);
                input_released=consumed;
            }
        }
        struct stat after{};
        if(::fstat(input,&after)!=0)failed("restore_recheck");
        if(after.st_size!=info.st_size || after.st_mtim.tv_sec!=info.st_mtim.tv_sec ||
           after.st_mtim.tv_nsec!=info.st_mtim.tv_nsec || after.st_ctim.tv_sec!=info.st_ctim.tv_sec ||
           after.st_ctim.tv_nsec!=info.st_ctim.tv_nsec)failed("restore_changed",EIO);
        if(::close(input)!=0)failed("restore_close");
        sync_record("restore_sync");
        if(::fstat(file,&output)!=0)failed("restore_stat");
        if(output.st_size) {
            char last=0;
            if(::pread(file,&last,1,output.st_size-1)!=1 || last!='\n')
                failed("incomplete_restore",EILSEQ);
        }
    }
    void close() {
        std::lock_guard<std::recursive_mutex> lock(mutex);
        if(file>=0) {
            if(::fdatasync(file)!=0)failed("close_sync");
            release_synced_pages(true);
            if(::close(file)!=0)failed("file_close");
            file=-1;
        }
        if(directory>=0) {
            if(::close(directory)!=0)failed("directory_close");
            directory=-1;
        }
    }
};
#endif
