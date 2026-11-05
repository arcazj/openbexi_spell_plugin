#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

/* Real syscalls always run. Logging is buffered by the OS, never synced by the
 * observer. Preserve errno and return values, including failures. */
static int output = -1;
static unsigned long long now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (unsigned long long)t.tv_sec * 1000000000ULL + t.tv_nsec;
}
__attribute__((constructor)) static void initialize(void) {
    const char *directory = getenv("OPENBEXI_DEADLINE_TRACE");
    if (directory) {
        char path[4096];
        snprintf(path, sizeof(path), "%s/io-%d.jsonl", directory, getpid());
        output = open(path, O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0600);
    }
}
static void record(const char *operation, int fd, unsigned long long start,
                   unsigned long long duration, long result, int error) {
    if (output >= 0) {
        char link[64], path[4096], line[4608];
        snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
        ssize_t size = readlink(link, path, sizeof(path)-1);
        if (size < 0) size = 0;
        path[size] = 0;
        int length = snprintf(line, sizeof(line),
            "{\"kind\":\"io\",\"label\":\"%s\",\"pid\":%d,\"tid\":%ld,"
            "\"start_ns\":%llu,\"duration_ns\":%llu,\"result\":%ld,\"errno\":%d,\"path\":\"%s\"}\n",
            operation, getpid(), syscall(SYS_gettid), start, duration, result, error, path);
        if (length > 0 && length < (int)sizeof(line)) syscall(SYS_write, output, line, length);
    }
}
int fdatasync(int fd) {
    unsigned long long start = now();
    int result = syscall(SYS_fdatasync, fd), error = errno;
    record("fdatasync", fd, start, now()-start, result, error);
    errno = error;
    return result;
}
int fsync(int fd) {
    unsigned long long start = now();
    int result = syscall(SYS_fsync, fd), error = errno;
    record("fsync", fd, start, now()-start, result, error);
    errno = error;
    return result;
}
ssize_t pwrite64(int fd, const void *buffer, size_t count, off64_t offset) {
    unsigned long long start = now();
    ssize_t result = syscall(SYS_pwrite64, fd, buffer, count, offset);
    int error = errno;
    record("pwrite64", fd, start, now()-start, result, error);
    errno = error;
    return result;
}
