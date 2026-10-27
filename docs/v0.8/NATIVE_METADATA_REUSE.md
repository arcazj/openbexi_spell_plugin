# Native message metadata reuse and routing

The previous candidate `3823fe0` passes 1,485 foundation checks with no failures,
errors or skips. Both mandatory original-family recovery runs complete their
45-second soaks and preserve eight processes, but still fail memory growth.
The verified archives and all 132 source entries per recovery profile are in
[the prior-candidate receipt](evidence/native-metadata/prior-candidate.json).
The thread-label component optimization does not resolve that failure.

The follow-up retains bounded owned string capacity for message ID, sender and
receiver, in addition to the existing property-node reuse. Up to 32 metadata
slots retain at most 64 KiB of total string capacity each. Empty inline strings
are not cached. Values are cleared before returning storage. A constructor
exclusively removes a slot before assigning its original metadata. Cache
contention, exhaustion and oversized metadata use ordinary string allocation
and destruction. The metadata cache has its own mutex and does not block on
contention. It retains no references to live messages or caller-owned storage.

The Context notification filter also uses an inline equality predicate instead
of copying the message ID for each of its three comparisons. No ID reference
escapes. Prompt/controller/observer routing, callback order and exception
propagation are unchanged. The complete upstream method and message source
remain guarded by exact preimage hashes.

Compiled original/candidate tests use the real message class under ASan/UBSan:

| 10,000 iterations | Original allocations / bytes | Candidate allocations / bytes |
| --- | ---: | ---: |
| Copy and clear long message metadata | 30,000 / 930,000 | 0 / 0 |
| Context notification routing filter | 30,000 / 510,000 | 0 / 0 |

Class size remains 176 bytes on the measured toolchain. Checks cover all five
constructors, copies, moves, assignments, clear/reuse, binary metadata, cache
saturation, oversized fields, concurrent message traffic, routing exclusions
and callback exceptions. These are component results; mandatory whole-runtime
resource acceptance must be rebuilt for this follow-up.

The new file inventory from the preceding diagnostic attributes the majority
of short-soak temporary-file growth to AsRun audit files. This is consistent
with, but does not yet prove, the earlier one-hour attribution. Audit records
are not truncated, deleted or excluded from resource acceptance. The independent
anonymous-memory growth and durable audit storage remain open.

Workloads, sanitizer settings, deadlines, no-swap policy and the 1,792 MiB peak /
64 MiB growth limits are unchanged. Full release remains HOLD.
