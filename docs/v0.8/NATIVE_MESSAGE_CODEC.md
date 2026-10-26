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
