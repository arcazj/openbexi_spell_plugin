# Reusable native message workers

Incoming one-way/notification handlers previously created an OS thread for every
message, even when no callback overlapped the preceding message. Resource traces
showed approximately stable live allocation totals and thread counts alongside
growing anonymous memory. This candidate removes repeated thread creation from
that path using up to eight lazy, reusable workers per native process.

There is no pending work queue or new concurrency ceiling. If all workers are busy,
or a reusable thread cannot start, the existing dedicated-thread path is used.
Requests retain their original dedicated threads. Each active message exclusively owns its
processor, payload, completion guard and listener reference. The existing trash
collector admits work and owns its processor until join returns. A pooled join
waits until the complete callback has returned, including after cancellation;
its ticket cannot be confused with a later job on the same slot. Idle workers
retain no message, ticket, payload or listener reference. Shutdown drains work.

The Incoming classes now dispatch start/join virtually and IncomingMessage owns
one completion ticket. This is an internal ABI change: Context, Executor, shared
native runtime and private bridge must be rebuilt together by the existing
candidate build graph. No prebuilt native library may be mixed into that graph.
The frozen distribution and source-port recipes are not changed.

Local ASan/UBSan checks compile the real incoming classes, port completion guards,
and candidate pool, with small transport/synchronization adapters. Linux thread
IDs confirm 10,000 sequential callbacks create 10,000 OS threads before this
change and one afterward. Additional checks cover 24 simultaneously blocked
callbacks (forcing dedicated fallback), 6,000 concurrent callbacks, cancellation,
request isolation, exception completion, shutdown, and exact-preimage guards.
These are component results, not full native or release qualification.

The preceding 1612600 five-minute comparisons preserve all eight processes and
progress throughout, but are not release receipts:

| Profile | Peak MiB | Growth MiB | Result |
| --- | ---: | ---: | --- |
| ASan handoff | 1857.01 | 542.21 | Fails peak and growth |
| ASan installed IDE | 1839.68 | 544.45 | Fails peak and growth |
| Optimized handoff | 147.89 | 12.99 | Passes diagnostic comparison |
| Optimized installed IDE | 148.93 | 14.35 | Passes diagnostic comparison |

The optimized profiles retain about 11 MiB of ASRUN files after five minutes;
long-duration ASRUN/audit storage remains a separate issue. All artifact ZIP
hashes and CRCs for these four comparisons were verified locally. Their run is
[40523171304](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40523171304).

Fresh mandatory hosted recovery, startup, prompt and terminal qualification is
required for this candidate. Sanitizers, memory limits, workload, deadlines and
acceptance thresholds are unchanged. Full v0.8 remains unqualified.

## Completed processor reuse

The worker-only candidate 70205ab passed 12/14 core jobs in run
[40529312300](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40529312300).
Both mandatory resource windows failed: handoff grew 103.33 MiB and installed
IDE grew 96.14 MiB (64 MiB limit). Thread reuse alone is not a memory fix.

The follow-up retains at most 32 fully joined message processors per process.
The collector transfers ownership to this cache only after join. Cached objects
clear their payload, listener, key and identity strings; identities above 1 KiB
capacity cause ordinary destruction. Creation removes one exclusive owner,
rebinds the listener/identity and resets completion flags, events and ticket.
Cache contention or exhaustion falls back to normal construction/destruction;
requests retain normal construction, dedicated threads and deletion.

The cache avoids repeated construction of each processor's native mutexes and
events. Local tests count constructor calls as well as actual OS thread IDs,
exercise 64 concurrent callbacks and the 32-object bound, alternate listeners,
and reject oversized identities. Exact guards cover all seven affected source
files, including the existing ordered prompt-answer composition. The thread
class gains protected identity reset helpers without changing its data layout.
Whole-runtime ASan/UBSan and resource receipts are still required. No sanitizer,
workload, admission limit, deadline or acceptance threshold is relaxed.
