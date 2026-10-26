// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_RESOURCE_TRACE_H
#define OPENBEXI_V08_RESOURCE_TRACE_H
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <time.h>
#include <unistd.h>

// GCC's linked libasan exports the compiler-rt allocator interface, although
// GCC does not install allocator_interface.h. These are the public signatures.
extern "C" size_t __sanitizer_get_current_allocated_bytes(void);
extern "C" size_t __sanitizer_get_heap_size(void);
extern "C" size_t __sanitizer_get_free_bytes(void);
extern "C" size_t __sanitizer_get_unmapped_bytes(void);
extern "C" void v08_allocation_profile_enable() noexcept;
extern "C" void v08_allocation_profile_dump(uint64_t) noexcept;

// Opt-in observation only. No trim, allocator flags, signal handler,
// authority decision, retry or runtime deadline is changed. Role 1 denotes an
// IPC participant; the host independently records its executable and identity.
// At most 120 records per process, shared by all IPC input threads.
static void v08_resource_trace(unsigned int role) noexcept
{
    static const bool enabled = [] {
        const char* value = std::getenv("OPENBEXI_V08_RESOURCE_DIAGNOSTICS");
        return value && std::strcmp(value, "1") == 0;
    }();
    if (!enabled || role != 1) return;
    v08_allocation_profile_enable();
    static std::atomic<uint64_t> previous{0};
    static std::atomic<unsigned int> count{0};
    if (count.load(std::memory_order_relaxed) >= 120) return;
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return;
    const uint64_t tick = static_cast<uint64_t>(now.tv_sec) * UINT64_C(1000000000)
        + static_cast<uint64_t>(now.tv_nsec);
    auto old = previous.load(std::memory_order_relaxed);
    if (tick < old || tick - old < UINT64_C(2000000000)
        || !previous.compare_exchange_strong(old, tick, std::memory_order_relaxed)) return;
    if (count.fetch_add(1, std::memory_order_relaxed) >= 120) return;
    char record[384];
    const int size = std::snprintf(record, sizeof(record),
        "V08_MEMORY {\"pid\":%ld,\"role\":%u,\"monotonic_ns\":%llu,"
        "\"allocated_bytes\":%zu,\"heap_bytes\":%zu,\"free_bytes\":%zu,\"unmapped_bytes\":%zu}\n",
        static_cast<long>(getpid()), role, static_cast<unsigned long long>(tick),
        __sanitizer_get_current_allocated_bytes(), __sanitizer_get_heap_size(),
        __sanitizer_get_free_bytes(), __sanitizer_get_unmapped_bytes());
    if (size > 0 && static_cast<size_t>(size) < sizeof(record)) {
        const auto ignored = write(STDERR_FILENO, record, static_cast<size_t>(size));
        (void)ignored;
    }
    v08_allocation_profile_dump(tick);
}
#endif
