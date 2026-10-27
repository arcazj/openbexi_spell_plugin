// SPDX-License-Identifier: GPL-3.0-or-later
// Compiles the actual before/after native methods against the durable writer.
#include "audit_file.H"
#include <atomic>
#include <cstdio>
#include <string>

// GCC exports these runtime interfaces without the optional LLVM header.
extern "C" size_t __sanitizer_get_current_allocated_bytes();
extern "C" size_t __sanitizer_get_heap_size();

#define STR(x) std::string(x)
#define ISTR(x) std::to_string(x)
struct SPELLutils {
    static void timestamp(std::string& output) { output="STAMP"; }
};
class SPELLasRun {
    V08AuditFile m_file;
    std::recursive_mutex m_v08RecordMutex;
    std::string m_v08Record;
    unsigned long m_sequence=0;
public:
    explicit SPELLasRun(const std::string& path) {
        m_file.open(path); toAsRun("INIT",true);
    }
    void toAsRun(const std::string&,bool);
    void writeLine(const std::string&);
    unsigned long sequence() const { return m_sequence; }
    size_t capacity() const { return m_v08Record.capacity(); }
};
#include "asrun-line.inc"

static std::atomic<bool> observing{false};
static std::atomic<unsigned long> calls{0},bytes{0};
static void allocated(const volatile void*,size_t size) {
    if(observing.load(std::memory_order_relaxed)) {
        calls.fetch_add(1,std::memory_order_relaxed);
        bytes.fetch_add(size,std::memory_order_relaxed);
    }
}
static void freed(const volatile void*) {}
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*,size_t),void (*)(const volatile void*));

int main(int argc,char** argv) {
    if(argc!=2 || !__sanitizer_install_malloc_and_free_hooks(allocated,freed))return 2;
    SPELLasRun output(argv[1]);
    const std::string stack="handoff.py:44:original-progress";
    const auto live_before=__sanitizer_get_current_allocated_bytes();
    const auto heap_before=__sanitizer_get_heap_size();
    observing.store(true,std::memory_order_relaxed);
    for(unsigned n=0;n<10000;++n)output.writeLine(stack);
    observing.store(false,std::memory_order_relaxed);
    const auto live_after=__sanitizer_get_current_allocated_bytes();
    const auto heap_after=__sanitizer_get_heap_size();
    const auto prefix_capacity=output.capacity();
    // Preserve empty, Unicode and large payloads, then reuse a small record.
    output.writeLine(""); output.writeLine("UTF8-\xc3\xa9-\xe2\x98\x83");
    output.writeLine(std::string(8193,'x')); output.writeLine("AFTER_OVERSIZED");
    std::printf("{\"acknowledged_records\":10004,\"all_sequences_advanced\":%s,"
                "\"measured_allocations\":%lu,\"measured_bytes\":%lu,"
                "\"live_before\":%zu,\"live_after\":%zu,"
                "\"heap_before\":%zu,\"heap_after\":%zu,"
                "\"retained_prefix_capacity\":%zu}\n",
                output.sequence()==10005?"true":"false",calls.load(),bytes.load(),
                live_before,live_after,heap_before,heap_after,prefix_capacity);
}
