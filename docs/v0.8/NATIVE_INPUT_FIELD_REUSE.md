# Native input field reuse

The decoder retained fields present in consecutive packets, but destroyed nodes
when LINE and ACK layouts alternated. This bypassed the bounded message-storage
cache and recreated the same nodes and value buffers on the next packet.

The candidate first extracts fields absent from the validated packet, clears
their values into the existing bounded cache, and takes exclusively owned nodes
when a new field appears. Live messages never share a map or string. The cache
still has 32 slots, at most 64 fields and 64 KiB of string capacity per slot;
contention, exhaustion and oversized fields use ordinary ownership/destruction.
There is no new cache, thread, class-layout change or borrowed wire-data lifetime.

The complete packet is length-validated before field extraction. Last duplicate
wins, partial metadata, embedded NUL/Unicode fields and malformed-packet cleanup
remain covered against the frozen original implementation. Eight concurrent
workers also decode alternating layouts while independent message copies remain
live. ASan and UBSan remain enabled.

With the same compiled harness, 10,000 LINE/ACK cycles allocate 200,000 times
(16,100,000 bytes) in the preceding `bea8f4f` decoder and zero times after bounded
warm-up in this candidate. This is component evidence, not whole-runtime resource
acceptance. See [measurement](evidence/native-input/component-allocation.json).
The final local check set passes 172 distinct codec, storage, resource-probe,
native-profile and experiment-composition tests, including the concurrent
decode/copy exercise. Formatting and diff checks pass.

## Preceding hosted qualification

Candidate `bea8f4f`, core run `40520985313`, passes 1,489 foundation tests without
failures, errors or skips, 11 of 14 core jobs and all five ancillary workflows.
All 15 core/diagnostic artifact ZIP digests and CRCs are verified, as are every
recorded source inventory. The candidate and tested merge have identical trees.

| Profile | Peak MiB | Growth MiB | Result |
| --- | ---: | ---: | --- |
| Handoff | 1,382.29 | 84.18 | Growth exceeds 64 MiB |
| Installed IDE | 1,386.43 | 89.21 | Growth exceeds 64 MiB |

Both recovery soaks preserve eight original processes for at least 45 seconds,
with every progress interval advancing. The mandatory peak budget is 1,792 MiB,
resident limit 2 GiB and swap allowance zero. These limits are unchanged.

The separate terminal job fails before native-child-running: workers 7 and 8
receive denied REQ_EXEC_INFO replies after the native admission deadline.
Member-registration RPCs take 3,188 and 3,049 ms; subsequent GUI replies are lost.
This identifies a delay and queueing symptom, not its root cause or a terminal
operation regression. Worker 8 exits with code 1 and no OOM kill. The passing
startup-stress job does not erase this failed attempt. No retries or deadlines
were changed. See [verified receipt](evidence/native-input/prior-candidate.json).

Fresh whole-runtime qualification is required for this decoder change. The
startup deadline fault, long-run audit/file growth and all broader release gates
remain open. No release, tag, merge or publication is authorized by these results.
