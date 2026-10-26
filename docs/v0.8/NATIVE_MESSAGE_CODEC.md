# Native IPC allocation correction

Hosted dev59 `5d0d64f` (run `40374299787`) passes 1,267 service tests,
95 overlapping fault tests and 241 portable tests. Twelve of fourteen core
jobs and all five ancillary workflows pass. All 19 artifacts are digest/ZIP
verified and their source inventories match the candidate; the PR merge tree
matches. Both original recovery families complete the 45-second soak and
terminal settlement without OOM. Resource acceptance **still fails**: handoff
reaches 2,147,491,840 bytes with five memory-limit events and 201,719,808 bytes
window growth; installed IDE reaches 2,133,803,008 bytes with 206,489,600 bytes
growth. No limits or sanitizer settings changed. See
[the retained evidence](evidence/native-codec/qualification-summary.json).

Dev60's diagnostic build introduced native Context startup failures in all six
rebuilt cohorts before recovery. That run is failed and supplies no recovery
allocation-site evidence. A compiled shared-library regression separately
reproduces its weak hook collecting no allocation samples. Dev61 replaces weak
symbol overriding with explicit sanitizer hook registration from `main`, before
native threads, and removes executable symbol exporting. Context symbols are
retained for offline address resolution instead. The 61 targeted checks pass,
including the shared-library regression; a local probe linked to the verified
published native runtime loads and records 1,531 samples from 390,000 allocations.
The corrected whole-native startup and recovery still require hosted acceptance.

Dev61 run `40378632943` restores the four non-recovery rebuilt cohorts and
passes 1,269 service tests; twelve of fourteen core jobs pass. Recovery still
fails: handoff records three limit events; installed IDE records one OOM kill.
The host's existing numeric-only log filter did not retain the new stack rows,
so no live allocation-site attribution is claimed from that run. Dev62 extends
the bounded collector with strict numeric/symbol/offset parsing, matches each
profile to an independently observed process, and marks partial top-site groups.
Both static and shared compiled sampler tests now exercise that exact collector.

The diagnostic uses opt-in, fixed-capacity ASan allocation-site sampling to identify
the remaining running-process costs. It samples approximately one allocation
in 256, records six largest sampled stack groups at most every ten seconds,
and suppresses its own symbol-lookup allocations from the measurements.
The 1,024-slot table and 20-frame stacks are bounded; dropped samples are
reported. It changes no allocator policy, authority decision or deadline.
These samples are diagnostic evidence, never an acceptance receipt.

Dev58's two extended recovery cohorts OOM-kill the original Context at the
fixed 2 GiB, zero-swap limit. The resource acceptance remains failed. Live
allocations and resident memory are distinct; rising allocator retention alone
does not establish a live-object leak.

Dev59 removes demonstrated allocation overhead in the native IPC codec. The
original decoder creates a map of byte vectors and copies its fields into a
second property map. The replacement reads bounded fields directly into their
final storage and moves values into place. The encoder reserves the final wire
length once and appends fields without constructing temporary encoded strings.
The original class layout, method signatures, valid wire ordering, last-duplicate
behavior, empty/binary/Unicode values and missing-metadata behavior are retained.
Malformed length headers and payloads fail before metadata changes. Serialization
rejects keys whose length cannot be represented by the original 16-bit wire field.

The checked private builder applies the patch only when the exact frozen
`SPELLipcMessage.C` SHA-256 matches. Changed or repeated applications fail.
The published v0.7 wheel and source recipes remain immutable. This patch is
rebuilt into the private Context and Executor runtime; the frozen host bridge
is unchanged.

The ASan/UBSan compiled regression uses the frozen message class, implementation
and tokenization helper, with unrelated logging/Python dependencies replaced by
fixtures. It compares 256 valid message variations and additional duplicate and
partial-metadata cases, checks truncated/oversized data and counts real allocator
calls during 10,000 representative messages:

| Operation | Before allocated bytes | After allocated bytes | Before allocations | After allocations |
| --- | ---: | ---: | ---: | ---: |
| Decode | 27,330,000 | 12,160,000 | 440,000 | 100,000 |
| Encode | 14,600,000 | 3,520,000 | 200,000 | 10,000 |

A separate local link against the verified published native runtime confirms
the reduction with its real utility dependencies (decode 27,670,000 → 12,400,000
bytes; encode 15,210,000 → 3,760,000 bytes). Those component measurements are not
a pass of full native recovery. Hosted qualification must still complete the
same 45-second soak, original-process liveness, 2 GiB/no-swap, peak/growth and
zero-pressure requirements. No sanitizer options or authority deadlines change.

## Dev62 diagnosis and dev63 candidate

Dev62 `0d282d8` (run `40380435228`) retains live allocation profiles.
Its 1,275 service tests, 95 overlapping fault tests, 241 portable tests and
five ancillary workflows pass. Twelve of fourteen core jobs pass. Handoff
hits the 2 GiB limit with 271 max events and one OOM kill; IDE hits the limit
with one max event. All 19 archives and recorded source hashes are verified.
See [diagnostic evidence](evidence/native-allocation-trace/dev62/qualification-summary.json).
Context reports 4,970,030 allocations totalling 612,644,648 bytes. Sampled
stacks include IPC decode map nodes, incoming dispatch objects and forwarding
string copies. Sampling does not establish a live leak or a complete cost ranking.

Dev63 adds defaulted move operations without changing message layout or copy
semantics. Incoming constructors transfer their owned by-value parameters,
while retaining the independent copy from their caller and reading the IPC key
from the destination after transfer. The patch checks the exact composed
incoming source fingerprint, retaining its existing synchronization and exception
completion fixes. Real composed constructor measurements, linked to the frozen
native library, reduce allocated bytes from 29,280,000 to 12,000,000 and allocations
from 330,000 to 150,000 over 10,000 messages. Both message layouts are 176 bytes.

The private opt-in session now selects a separately built bridge linked to its
candidate native library. Its JSON encoder constructs the result directly,
avoiding initializer-list copies of the fields and metadata. Protocol fields,
whitelist, invalid-UTF-8 replacement, callback order and ACK behavior are preserved.
The default frozen v0.7 bridge is unchanged. Source, binary and field-inventory
hashes are retained by the builder and qualification source inventory.

The 134 targeted tests pass, including compiled binary/Unicode/empty-field wire
compatibility, copy isolation, move reassignment, unchanged layout, allocation
counts, exact composed patches, bridge selection and original lifecycle tests.
The full private bridge compiles against the verified native headers/library.
[Measured component evidence](evidence/native-codec/dev63/allocation-comparison.json)
is separate from the pending hosted recovery verdict.

Allocation stack profiling now requires the separate
`OPENBEXI_V08_ALLOCATION_DIAGNOSTICS=1` opt-in. Normal acceptance retains
`OPENBEXI_V08_RESOURCE_DIAGNOSTICS=1` numeric observation without stack sampling.
The 45-second soak, memory/swap limits, peak/growth budgets, sanitizer options,
process-liveness requirements and all eleven full-release gates are unchanged.
