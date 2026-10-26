// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_STARTUP_TRACE_H
#define OPENBEXI_V08_STARTUP_TRACE_H
#include <cstdint>
#include <cstdio>
#include <string>
#include <time.h>
#include <unistd.h>

// Read-only diagnostics, never an admission or a reason to replay a launch.
// Fixed call-site stage names and an opaque member correlation key keep source
// paths, arguments, credentials and capabilities out of this record. One small
// write preserves individual records across the Context's startup threads.
static void v08_start_trace(const std::string& instance, const char* stage) noexcept
{
    uint64_t member = UINT64_C(14695981039346656037);
    for (const unsigned char value : instance) {
        member ^= value;
        member *= UINT64_C(1099511628211);
    }
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return;
    char record[256];
    const int size = std::snprintf(record, sizeof(record),
        "V08_START {\"member\":\"%016llx\",\"pid\":%ld,\"stage\":\"%s\",\"monotonic_ns\":%llu}\n",
        static_cast<unsigned long long>(member), static_cast<long>(getpid()), stage,
        static_cast<unsigned long long>(now.tv_sec) * UINT64_C(1000000000)
            + static_cast<unsigned long long>(now.tv_nsec));
    if (size > 0 && static_cast<size_t>(size) < sizeof(record)) {
        const auto ignored = write(STDERR_FILENO, record, static_cast<size_t>(size));
        (void)ignored;
    }
}
#endif
