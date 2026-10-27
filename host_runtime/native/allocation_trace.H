#ifdef OPENBEXI_NATIVE_NO_SANITIZERS
#include <cstdint>
#include <cstdlib>
extern "C" bool v08_allocation_profile_start() noexcept {
    const char* p = std::getenv("OPENBEXI_V08_ALLOCATION_DIAGNOSTICS");
    return !p || p[0] != '1';
}
extern "C" void v08_allocation_profile_dump(uint64_t) noexcept {}
#else
// SPDX-License-Identifier: GPL-3.0-or-later
// Included once in the private IPC translation unit. Diagnostic sampling only.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <sanitizer/asan_interface.h>
#include <unistd.h>
#include <unwind.h>

namespace v08_alloc {
constexpr size_t frames=20, capacity=1024, top=6;
struct Site {
    void* stack[frames]{};
    uint64_t bytes=0, count=0, freed_bytes=0, freed_count=0;
};
// Sampled pointers are retained only as private numeric identities until free.
// Fixed storage, no allocation in either hook. Missed frees are explicit: the
// unmatched totals are upper bounds, never proof of a live allocation leak.
constexpr size_t pointer_capacity=8192;
struct Pointer { const volatile void* address=nullptr; size_t site=0, size=0; uint64_t generation=0; };
static Pointer pointers[pointer_capacity];
static std::atomic<uint64_t> free_calls{0}, free_lock_misses{0}, pointer_full{0};
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
struct Walk { void** stack; size_t used=0; };
static _Unwind_Reason_Code frame(_Unwind_Context* context,void* argument) {
    auto& walk=*static_cast<Walk*>(argument);
    if(walk.used==frames)return _URC_END_OF_STACK;
    const auto address=_Unwind_GetIP(context);
    if(address)walk.stack[walk.used++]=reinterpret_cast<void*>(address);
    return _URC_NO_REASON;
}
}

// Register from main, after sanitizer initialization and before native threads.
// Avoid changing weak-symbol resolution or exporting executable symbols.
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*, size_t), void (*)(const volatile void*));
static void v08_capture_allocation(const volatile void* pointer, size_t size)
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
    void* stack[frames]{};
    // The sanitizer's fast allocation stack stops at distribution libraries
    // built without frame pointers. DWARF unwind this *sampled* call to retain
    // the actual SPELL caller. Suppress unwind-internal reentrant allocations;
    // no sanitizer option or mandatory execution profile is changed.
    reporting=true;
    Walk walk{stack};_Unwind_Backtrace(frame,&walk);
    reporting=false;
    uint64_t hash=0;
    for (auto frame:stack) hash=mix(hash^reinterpret_cast<uintptr_t>(frame));
    bool stored=false;
    for (size_t offset=0;offset<capacity;++offset) {
        auto& site=sites[(hash+offset)%capacity];
        if (!site.count || std::memcmp(site.stack,stack,sizeof(stack))==0) {
            if (!site.count) std::memcpy(site.stack,stack,sizeof(stack));
            site.bytes+=size; ++site.count; stored=true;
            const size_t first=mix(reinterpret_cast<uintptr_t>(pointer))%pointer_capacity;
            bool tracked=false;
            for(size_t n=0;n<8;++n) {
                auto& slot=pointers[(first+n)%pointer_capacity];
                if(!slot.address) {
                    slot={pointer, (hash+offset)%capacity, size,
                          free_lock_misses.load(std::memory_order_relaxed)};
                    tracked=true; break;
                }
            }
            if(!tracked)pointer_full.fetch_add(1,std::memory_order_relaxed);
            break;
        }
    }
    if (!stored) skipped.fetch_add(1,std::memory_order_relaxed);
    busy.clear(std::memory_order_release);
}

static void v08_observe_free(const volatile void* pointer) {
    using namespace v08_alloc;
    if(!enabled.load(std::memory_order_relaxed) || reporting || !pointer)return;
    free_calls.fetch_add(1,std::memory_order_relaxed);
    if(busy.test_and_set(std::memory_order_acquire)) {
        free_lock_misses.fetch_add(1,std::memory_order_relaxed);return;
    }
    const size_t first=mix(reinterpret_cast<uintptr_t>(pointer))%pointer_capacity;
    // Eight probes bound work per free, including collisions and empty holes.
    for(size_t n=0;n<8;++n) {
        auto& slot=pointers[(first+n)%pointer_capacity];
        if(slot.address==pointer) {
            // A dropped free can precede pointer reuse. Invalidate all older
            // generations conservatively instead of attributing a later free
            // to a different allocation at the same address.
            if(slot.generation==free_lock_misses.load(std::memory_order_relaxed)) {
                auto& site=sites[slot.site];
                ++site.freed_count;site.freed_bytes+=slot.size;
            }
            slot={};break;
        }
    }
    busy.clear(std::memory_order_release);
}

extern "C" bool v08_allocation_profile_start() noexcept
{
    // Main-thread-only: the hook installer must run before native threads.
    const char* setting=std::getenv("OPENBEXI_V08_ALLOCATION_DIAGNOSTICS");
    if (!setting || std::strcmp(setting,"1")!=0) return true;
    const bool installed=__sanitizer_install_malloc_and_free_hooks(v08_capture_allocation,v08_observe_free)>0;
    v08_alloc::enabled.store(installed,std::memory_order_relaxed);
#ifdef OPENBEXI_V08_MESSAGE_STORAGE
    if(installed)v08_storage_profile_begin();
#endif
    return installed;
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
            // Rank by repeated sampled allocation sites, not one-off large
            // CPython startup buffers. All bytes and sample counts remain raw.
            if (site.count<=selected[i].count) continue;
            for (size_t j=top-1;j>i;--j) selected[j]=selected[j-1];
            selected[i]=site; break;
        }
    }
    busy.clear(std::memory_order_release);
    // Symbol lookup is outside the hook and lock. Suppress its own allocations
    // from the measurements, without changing allocator behavior.
    reporting=true;
#ifdef OPENBEXI_V08_MESSAGE_STORAGE
    v08_storage_profile_dump(tick);
#endif
    char line[4096];
    int count=std::snprintf(line,sizeof(line),
        "V08_ALLOC pid=%ld tick=%llu calls=%llu bytes=%llu samples=%llu skipped=%llu frees=%llu free_misses=%llu pointer_full=%llu\n",
        static_cast<long>(getpid()),static_cast<unsigned long long>(tick),
        static_cast<unsigned long long>(calls.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(bytes.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(sampled),
        static_cast<unsigned long long>(skipped.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(free_calls.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(free_lock_misses.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(pointer_full.load(std::memory_order_relaxed)));
    if (count>0 && static_cast<size_t>(count)<sizeof(line)) {
        const auto ignored=write(STDERR_FILENO,line,count);(void)ignored;
    }
    for (size_t rank=0;rank<top;++rank) {
        const auto& site=selected[rank]; if (!site.count) continue;
        count=std::snprintf(line,sizeof(line),"V08_ALLOC_SITE pid=%ld rank=%zu samples=%llu bytes=%llu freed_samples=%llu freed_bytes=%llu",
            static_cast<long>(getpid()),rank,static_cast<unsigned long long>(site.count),
            static_cast<unsigned long long>(site.bytes),
            static_cast<unsigned long long>(site.freed_count),
            static_cast<unsigned long long>(site.freed_bytes));
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

#endif
