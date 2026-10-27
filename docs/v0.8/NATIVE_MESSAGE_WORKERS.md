# Bounded native message processor reuse

The current candidate retains at most 32 fully joined message processors per
process, avoiding repeated construction of their mutexes and completion events.
Each active message has exclusive ownership. The collector joins its original
dedicated OS thread before clearing its payload, listener, key and identity
strings and transferring ownership to the cache. Requests retain ordinary
construction, dedicated threads and deletion.

Creation takes one cached owner and resets its listener, identity, completion
flags and events. Cache contention or exhaustion uses normal construction and
destruction. Identity strings above 1 KiB capacity cause destruction. The cache
has no work queue, does not limit concurrent callbacks and never admits a
cancelled-but-still-running callback for reuse. Oversized payload storage follows
the existing independently bounded IPC storage policy.

Exact preimage guards cover all seven affected native sources and preserve
ordered prompt answers. Context, Executor, shared runtime and private bridge
are rebuilt together. The incoming class listener representation changes
internally; the frozen distribution and source-port recipes remain unchanged.

Compiled ASan/UBSan tests check 10,000 sequential callbacks, 64 simultaneous
callbacks, the 32-object cache bound, 6,000 concurrent callbacks, cancellation,
request isolation, exception completion, listener rebinding and input drift.
Sequential execution still creates 10,000 dedicated OS threads while processor
construction falls from 10,000 to one. Component tests use lightweight transport
and synchronization adapters; whole-runtime hosted acceptance remains required.

## Retained experiments and current limits

Candidate 70205ab reused up to eight message threads. It passed 1,500 foundation
tests, 12/14 core jobs and all five ancillary workflows, but mandatory memory
growth failed: handoff 103.33 MiB and installed IDE 96.14 MiB (64 MiB limit).
Five-minute ASan comparison peaks and growth also exceeded their unchanged
budgets. These results did not support keeping the thread-pool optimization.

Candidate e0841d4 combined that pool with processor reuse. Its allocation
profile reduced growth from 101.16 MiB to 75.95 MiB, still failing 64 MiB.
One mandatory handoff attempt failed before memory measurement: child member
registration took 5.38 seconds, beyond the four-second native admission deadline.
No retry or different deadline is treated as a fix for that startup failure.

The current candidate removes the message thread pool and isolates processor
reuse with the original dedicated threads. The prior candidates and receipts
remain in history. Sanitizers, memory budgets, workload, concurrency, deadlines
and acceptance thresholds are unchanged. No memory or full-v0.8 pass is inferred
from the component reduction. Durable ASRUN/audit storage, complete compatibility,
deployed recovery/security, browser/public GUI and joint stable packaging remain
separate release blockers.

## Collector nodes and notification field reads

Candidate 23dbec3 passed 1,507 foundation tests, 12/14 core jobs and all five
ancillary workflows, including fresh startup stress and terminal handling.
Its mandatory handoff/IDE memory windows still failed at 75.47/83.67 MiB growth;
the allocation diagnostic measured 87.00 MiB. All thresholds remain unchanged.

The follow-up also reuses at most 32 empty collector list nodes. The existing
collector mutex guards both lists; completed processors are joined/disposed
before their node is cleared and spliced into the spare list. Busy nodes remain
owned by the active list. The original start-failure rollback and request path
remain in place. The internal collector layout changes, so all native users
must be rebuilt together by the existing candidate graph.

Read-only notification fields are borrowed from the exclusively owned incoming
message only during the synchronous callback. Missing fields still yield an
empty string; model setters still take their own copies. Error/reason strings
remain mutable copies because the callback trims them. The functional tests
check missing fields, source immutability, retained model values after source
mutation, error trimming and notification types against the original method.

Component ASan/UBSan tests measure 2,500 collector-node allocations falling to
one, preserve the 32-node bound across 64-callback bursts, and require join after
cancellation. For 10,000 long-field notifications, the preceding borrowed-message
method still makes at least 40,000 field-copy allocations; the new method makes
zero after warmup. These allocation counts are not whole-runtime acceptance.
