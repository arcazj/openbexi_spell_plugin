// SPDX-License-Identifier: GPL-3.0-or-later
// Included once in the private IPC translation unit. Diagnostic sampling only.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <sanitizer/asan_interface.h>
#include <unistd.h>

namespace v08_alloc {
constexpr size_t frames=20, capacity=1024, top=6;
struct Site { void* stack[frames]{}; uint64_t bytes=0, count=0; };
static Site sites[capacity];
static std::atomic<bool> enabled{false};
static std::atomic<uint64_t> calls{0}, bytes{0}, skipped{0};
static std::atomic_flag busy=ATOMIC_FLAG_INIT;
static thread_local bool reporting=false;
static uint64_t mix(uint64_t value) {
    value=(value^(value>>30))*UINT64_C(0xbf58476d1ce4e5b9);
    value=(value^(value>>27))*UINT64_C(0x94d049bb133111eb);
    return value^(value>>31);
}
}

// A strong test hook may replace this weak process-wide ASan callback.
extern "C" __attribute__((weak)) void __sanitizer_malloc_hook(const volatile void* pointer, size_t size)
{
    using namespace v08_alloc;
    if (!enabled.load(std::memory_order_relaxed) || reporting) return;
    const auto serial=calls.fetch_add(1,std::memory_order_relaxed)+1;
    bytes.fetch_add(size,std::memory_order_relaxed);
    // Mix the allocation ordinal to avoid sampling every identical phase of a
    // repeating message. Store only approximately one in 256 allocations.
    if ((mix(serial)&255)!=0) return;
    if (busy.test_and_set(std::memory_order_acquire)) {
        skipped.fetch_add(1,std::memory_order_relaxed); return;
    }
    void* stack[frames]{}; int thread=0;
    __asan_get_alloc_stack(const_cast<void*>(pointer),stack,frames,&thread);
    uint64_t hash=0;
    for (auto frame:stack) hash=mix(hash^reinterpret_cast<uintptr_t>(frame));
    bool stored=false;
    for (size_t offset=0;offset<capacity;++offset) {
        auto& site=sites[(hash+offset)%capacity];
        if (!site.count || std::memcmp(site.stack,stack,sizeof(stack))==0) {
            if (!site.count) std::memcpy(site.stack,stack,sizeof(stack));
            site.bytes+=size; ++site.count; stored=true; break;
        }
    }
    if (!stored) skipped.fetch_add(1,std::memory_order_relaxed);
    busy.clear(std::memory_order_release);
}

extern "C" void v08_allocation_profile_enable() noexcept
{
    v08_alloc::enabled.store(true,std::memory_order_relaxed);
}

extern "C" void v08_allocation_profile_dump(uint64_t tick) noexcept
{
    using namespace v08_alloc;
    if (!enabled.load(std::memory_order_relaxed) || reporting) return;
    static std::atomic<uint64_t> previous{0};
    auto old=previous.load(std::memory_order_relaxed);
    if (tick<old || tick-old<UINT64_C(10000000000)
        || !previous.compare_exchange_strong(old,tick,std::memory_order_relaxed)) return;
    if (busy.test_and_set(std::memory_order_acquire)) return;
    Site selected[top]{};
    uint64_t sampled=0;
    for (const auto& site:sites) {
        sampled+=site.count;
        for (size_t i=0;i<top;++i) {
            if (site.bytes<=selected[i].bytes) continue;
            for (size_t j=top-1;j>i;--j) selected[j]=selected[j-1];
            selected[i]=site; break;
        }
    }
    busy.clear(std::memory_order_release);
    // Symbol lookup is outside the hook and lock. Suppress its own allocations
    // from the measurements, without changing allocator behavior.
    reporting=true;
    char line[4096];
    int count=std::snprintf(line,sizeof(line),
        "V08_ALLOC pid=%ld tick=%llu calls=%llu bytes=%llu samples=%llu skipped=%llu\n",
        static_cast<long>(getpid()),static_cast<unsigned long long>(tick),
        static_cast<unsigned long long>(calls.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(bytes.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(sampled),
        static_cast<unsigned long long>(skipped.load(std::memory_order_relaxed)));
    if (count>0 && static_cast<size_t>(count)<sizeof(line)) {
        const auto ignored=write(STDERR_FILENO,line,count);(void)ignored;
    }
    for (size_t rank=0;rank<top;++rank) {
        const auto& site=selected[rank]; if (!site.count) continue;
        count=std::snprintf(line,sizeof(line),"V08_ALLOC_SITE pid=%ld rank=%zu samples=%llu bytes=%llu",
            static_cast<long>(getpid()),rank,static_cast<unsigned long long>(site.count),
            static_cast<unsigned long long>(site.bytes));
        for (auto frame:site.stack) {
            if (!frame || count<0 || static_cast<size_t>(count)>=sizeof(line)-300) break;
            Dl_info info{};dladdr(frame,&info);
            const char* file=info.dli_fname?std::strrchr(info.dli_fname,'/'):nullptr;
            const int added=std::snprintf(line+count,sizeof(line)-count," | %.60s+%zx:%.100s",
                file?file+1:(info.dli_fname?info.dli_fname:"?"),
                reinterpret_cast<uintptr_t>(frame)-reinterpret_cast<uintptr_t>(info.dli_fbase),
                info.dli_sname?info.dli_sname:"?");
            if (added<0 || static_cast<size_t>(added)>=sizeof(line)-count) break;
            count+=added;
        }
        if (count>0 && static_cast<size_t>(count)<sizeof(line)-1) {
            line[count++]='\n';const auto ignored=write(STDERR_FILENO,line,count);(void)ignored;
        }
    }
    reporting=false;
}
