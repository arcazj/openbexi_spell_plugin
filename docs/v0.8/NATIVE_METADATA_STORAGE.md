# Native metadata and line-notification storage

## Scope and integration

This candidate extends exact baseline `0cb677a514bd4f04bab50f515765f615b21f3391`.
It preserves dev68's writer-owned wire buffers, borrowed packet views, read-only
notification callbacks and owned line-send overload. It also preserves the
exact-key cache and rotating eviction correction, including their saturated-cache
regressions. The paired IDE remains `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`.

The native copy cache now reuses owned ID/sender/receiver strings alongside field
maps. Live messages never share field storage. The same nonblocking mutex,
32-slot, 64-field and 64 KiB-per-entry capacity limits remain. Metadata counts
inside the capacity bound. Empty self-assignment cannot acquire cached data, and
oversized metadata displaced from an empty target is released from unused slots.

The checked original line-notification method uses bounded per-thread storage
only for its normal one-field prototype. Every computed field is overwritten;
all prototype metadata is reset before each send because the native owned-send
path mutates sequence, key and addressing. Changed prototypes use ordinary
copies, nested callbacks use independent storage, and oversized fields release
the cache. Timestamp/sequence updates, readiness behavior and transport-error
pause are unchanged. One redundant read-only Context notification copy is removed.

The line overlay is applied after the frozen prompt/terminal guards and before
the existing owned-send overlay. The full checked native source composition
succeeds with both prompt and terminal hooks enabled.

## Executed local evidence

All **96 focused tests pass** on local Python 3.13.5, including the compiled
ASan/UBSan message/line tests, existing codec and stream tests, compression,
partial writes, malformed packets, allocation sampling, spawn, transport and
resource-oracle checks. Pinned Ruff 0.14.1 lint and formatting pass. All six
uploaded implementation/test blobs match the exact local tested file hashes;
two builder comments were clarified after the test without executable changes.

Measurements use 10,000 benchmark iterations and the frozen native methods as
an independent oracle, with unrelated clock, scheduler and socket fixtures:

| Component | Frozen allocated bytes | Candidate allocated bytes |
| --- | ---: | ---: |
| Three message copies, real notification ID and long metadata | 34,800,000 | 0 after warm-up |
| Interleaved long-metadata message shapes | 29,800,000 | 0 after warm-up |
| Repeated real-notification input decoding | 37,880,000 | 0 after warm-up |
| Native line-notification preparation and send | 22,008,902 | 2,050,000 |
| Four exact field inventories, including saturated startup cache | 24,960,000 | 0 after warm-up |

The message layout remains 176 bytes. The line comparison preserves all 10,002
deliveries and the full captured metadata/field digest 15621954683225311635.
Tests cover binary/Unicode/empty fields, changing prototypes, native metadata
mutation, nested callbacks, transport failure, eight concurrent threads,
oversized fields/metadata, independent copies and empty self-assignment.

## Previous failed evidence remains failed

The property-only cache did not meet resource acceptance. Its installed-IDE
run completed the original soak but grew 223,346,688 bytes. The exact-shape
handoff correction subsequently grew 189,014,016 bytes. The dev68 stream-only
handoff at `621cbe79c47b419996f2b97ad9e71e60f9b4e5e6` completed 45.428 seconds
but still grew 130,494,464 bytes. Its peak was 1,581,809,664 bytes.

The latter archive is run `40417737537`, artifact `12695769619`, SHA256
`1cf79104a36a3ec9272640bb1343e1e1d3dd8ad8661f11897aeb5fdceb822ab5`;
its digest and ZIP integrity were verified before inspection. These component
improvements and prior failures do not establish this candidate's hosted verdict.

## Required acceptance

Both non-profiled native handoff and installed-IDE recovery must preserve all
eight original processes, advance every progress interval, complete the unchanged
45-second soak, and pass 1,792 MiB peak / 64 MiB median-window growth within
2 GiB resident, zero swap and zero pressure/OOM events. Sanitizer settings,
workload, deadlines and authority checks are unchanged. No full-release gate
is promoted and no stable release or production migration is performed.
