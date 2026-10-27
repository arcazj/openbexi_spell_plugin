# Dev73 measured corrections, full release unqualified

Verified predecessor executable: `6dd82189a4cdc4f021af3a357ccf747a0b459f98`;
documentation successor: `e4e707d98c6f00659a2f968a0682449465fe7f0a`;
paired IDE: `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`.
Dev73 changes require fresh hosted native, installed-IDE, audit and lifecycle
qualification. Local components cannot promote a full-release gate.

## Measured LINE allocation

The predecessor's actual native frequency profile, artifact 12773129577,
identifies repeated `std::string` append allocations in `SPELLasRun::writeLine`.
It verifies all 139 inputs and 23 raw audit files. The original method creates a
temporary `LINE` plus stack string before synchronous durable output.

The correction writes the same bytes through the existing two-part writer,
using the existing mutex and owned timestamp/sequence buffer. Sequence advances
only after the same successful durable write. The private `toAsRun` helper is
nonvirtual; unrelated record methods are unchanged.

Compiled actual before/after methods execute all 10,000 measured LINE calls.
Allocations fall from 10,000 / 380,000 bytes to one / 31 bytes. Allocator heap
growth is 786,432 / zero bytes. The retained 31 bytes belong to the bounded
prefix buffer and remain included in memory observations. The fixture uses a
fixed timestamp to isolate payload allocation; separate formatter tests cover
70 timestamp cases. It is not a whole-family memory result.

Both raw output files are identical, SHA-256
`5d7a06a01e24b8237add23e22406573387d184868827d410de00b03c9352c577`:
10,000 measured records, four empty/Unicode/oversized/follow-up records and the
initial INIT record. All 10,005 sequences and complete bytes remain retained.
Concurrent record/reset/generation, failure and restart controls also execute.

## Demonstrated callback exit hang

At the predecessor header SHA-256
`27cc65d2966eceb22ffa30ca35584ab3004a0c621501f3fe826cb03924e008fe`,
a callback entering `pthread_exit` runs its cleanup. The dedicated-thread
control joins and exits zero in approximately 5 ms; the reused-worker control
hangs until the component's three-second external deadline. Its pool ticket is
never completed because the normal-return path is bypassed.

A worker lifetime guard now settles the ticket after callback frames unwind,
then retires that exited slot. It cannot be selected as an idle worker.
Subsequent work retains the original dedicated fallback, preserving concurrency.
At most five retired thread handles remain owned and are joined at shutdown;
no callback object or ticket is retained after completion. No authority hold is
released by this bookkeeping.

The corrected reproduction joins and exits zero in approximately 5 ms. Four
components compile actual native MESSAGE/REQUEST lifecycle methods and exercise
both `pthread_exit` and `pthread_cancel`: twelve callbacks per case exceed all
five reusable slots, preserve cleanup/finished state and exit after shutdown.
Synchronization/transport adapters remain component fixtures. This establishes
the new defect and correction, not the cause of the historical 90-second hang.

## Revisit successful cache advice

The unchanged earlier writer produces two retained local failures: 3,840 cached
pages during writing and 7,169 during restore, above the existing 64 KiB oracle.
A separate original-policy restore observes 5,889 cached pages. All raw 64 MiB
files remain complete. The exact kernel cause, including retained versus
refaulted pages, has not been established.

Successful `POSIX_FADV_DONTNEED` is advisory, but the previous cursor permanently
excluded earlier completed ranges after one successful call. A controlled
comparison additionally advises the completed prefix: four treatment attempts
observe one cached page each, with identical full-file hashes. A deterministic
successful no-op for the first four advice calls leaves 64 cached pages under
the predecessor and proves that those ranges are never revisited.

The writer now re-advises the synced prefix in the existing 64 KiB cadence and
at close; restore similarly revisits consumed input. Nothing is deleted,
subtracted, moved to another cgroup or acknowledged before synchronization.
Explicit advice errors still exit 74. The original cache bounds, byte/order
checks and the new successful-no-op regression pass in the final local run.
Advice remains advisory; actual whole-cgroup results remain mandatory.

## Remaining evidence

All 163 final affected local components pass. Earlier compilation, preimage
and cache failures remain retained. Both predecessor sanitizer hours fail:
IDE observes 991.929476709 seconds and one sampled OOM kill; handoff observes
2,335.159192092 seconds with zero OOM/kill counters in the last sample, followed
by later Docker `OOMKilled=true`. Neither is a one-hour pass.

Diagnostic `e5565ef2` verifies 169 resource observations and 501 allocation
profiles. Numeric last-source-line tags identify root/child fixture file-write
lines for 47 / 58 sampled 4 KiB allocations, all freed. Untraced background
threads retain zero tags. Sampling is bounded and does not attribute every
growing byte or prove leak absence. The unchanged workload is preserved.

See [source-bound local receipt](evidence/measured-audit-callback-corrections-20261027.json).
All eleven full-release groups remain false. Public/native/driver/763,
IDE/browser/WSS/Git, full deployed workloads/recovery, security and stable joint
packaging/final installation remain unfinished. No stable merge, tag, release
or production migration has occurred.
