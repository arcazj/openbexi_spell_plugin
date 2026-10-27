# Bounded storage for newly constructed native messages

## Recycle the explicit incoming-message completion path

The rebuilt `e0f3b2e` diagnostic identifies an actual empty-cache problem in
Context. Its last snapshot records 488,760 empty-node misses versus 4,477 lock
misses, with zero field-count, capacity or full-cache return rejections. Executor
node reuse is already nearly complete. All 132 source entries and the archive
digest are verified in [the source-bound finding](evidence/fresh-message-storage/message-clear-root-cause.json),
which also retains counter deltas within the exact soak and native method hashes.

`SPELLipcIncomingBase::finish()` explicitly calls `m_message.clear()` before the
message destructor. That method destroyed the field nodes directly, leaving an
empty message for the destructor's recycling hook. The correction offers those
nodes to the same bounded cache before the original clear operation. A refused
cache return still clears normally. The exact original clear body is SHA-256
guarded; its field clearing, ID/sender/receiver clearing and preservation of type,
sequence, key and compression metadata are unchanged.

The compiled completion-path benchmark allocates 90,000 times / 8,640,000 bytes
on both the frozen runtime and parent `e0f3b2e`, and zero after this correction
across 10,000 completions. All 143 storage, codec, stream and comparison-profile
checks pass under the existing native sanitizer settings. Tests cover repeated
clear, independent copies, oversized messages and subsequent reuse. The initial
test-fixture compression assumption and its correction are retained separately.
[Validation](evidence/fresh-message-storage/message-clear-validation.json) and
[benchmark](evidence/fresh-message-storage/message-clear-benchmark.json) do not
qualify whole-runtime memory. Rebuilt mandatory recovery and the cache diagnostic
must verify this correction before any resource blocker can be closed.

## Cache decision diagnostics

Candidate `0bc731f` passes 1,476 foundation tests, twelve of fourteen core jobs
and all five ancillary workflows. Both original-family recovery jobs still fail
the unchanged 64 MiB growth limit: 104.37 MiB for handoff and 95.60 MiB for IDE.
Their peaks are 1,462.21/1,436.52 MiB. Both preserve eight processes and progress
through the full 45-second soak. Archive digests and all 132 source inputs per
recovery archive are verified in [the hosted receipt](evidence/fresh-message-storage/fragmented-hosted.json).
The mixed-traffic regression is fixed, but whole-process resource acceptance is
not fixed. The actual Context still allocates in forwarding and queued copies.

The existing opt-in allocation diagnostic now also records fixed numeric cache
decisions: hits, empty-cache and contention misses, ordinary copy allocations,
and returns rejected by field count, retained capacity, contention or a full
cache. It retains no field names or values. One bounded line accompanies each
existing ten-second allocation sample; the host accepts at most 32 process
records and requires original process identity. The diagnostic workflow requires
observations from both Context and Executor. These counters do not change cache
policy, runtime authority, allocator settings or memory acceptance.

All 146 distinct focused checks pass, including compiled diagnostics-off/on,
counter accounting, bounded parsing, allocation sampling and all comparison
source guards. Thirteen storage checks are repeated on the final atomic opt-in
flag. [Validation](evidence/fresh-message-storage/cache-diagnostics-validation.json)
records that overlap; a hosted diagnostic is needed to explain the real misses.

The older same-optimization-level ASan/UBSan comparisons also complete both
five-minute soaks with eight original processes, but fail peak and growth limits.
All 135 source entries per overlaid build are independently reconstructed and
verified in [the comparison receipt](evidence/fresh-message-storage/asan-o2-baseline-results.json).
Optimization flags alone do not resolve that baseline's resource failure.

## Follow-up: copies reuse partially consumed cached maps

Candidate `0eb29d8` passes all 1,475 hosted foundation tests, but both mandatory
recovery runs still fail memory growth: 105.31 MiB for handoff and 115.75 MiB for
installed IDE. Peaks are 1,451.96 and 1,460.34 MiB; both retain eight original
processes through the full 45-second soak. All 132 source entries in each archive
match the candidate. [The failed results](evidence/fresh-message-storage/notification-hosted.json)
remain separate from component allocation improvements.

The rebuilt diagnostic confirms that the synchronous notification copy is gone.
The frequent remaining copy sites are client forwarding and incoming-message
queue ownership. [The exact-build call paths](evidence/fresh-message-storage/fragmented-call-sites.json)
identify those sites without borrowing across their ownership boundaries.

A compiled mixed-traffic reproducer exposes a cache fragmentation problem:
fresh acknowledgements consume nodes from cached maps, and later full-message
copies allocate missing nodes despite reusable nodes remaining in other maps.
Copies now use the same exclusive node extraction as fresh producers when a
whole matching map is unavailable. The existing 32-map/64-field/64-KiB limits,
try-lock fallback, class layout, and message ownership are unchanged.

Across 10,000 mixed forwarding/acknowledgement/queued-copy cycles, the frozen
implementation allocates 220,000 times, `0eb29d8` allocates 40,000 times, and
this correction allocates zero times after warm-up. Each message remains 176
bytes on this toolchain. [Benchmark records](evidence/fresh-message-storage/fragmented-benchmark.json)
are component evidence; a new hosted rebuild must establish resource acceptance.
All 40 distinct storage, codec and stream checks pass under ASan/UBSan.
The initial missing-header setup errors and corrected run are retained in
[the validation receipt](evidence/fresh-message-storage/fragmented-validation.json).

The earlier `a0a1686` encrypted-swap setup correction is now exercised remotely.
Both five-minute comparisons execute, verify all 135 overlaid source entries,
and restore the original unused host swap. Both still fail combined memory
growth (601.01/629.78 MiB for handoff/IDE), with no swap pages actually used.
[The retained records](evidence/fresh-message-storage/swap-baseline-results.json)
clear the setup-only blocker, not the mandatory no-swap or release gates.

## Follow-up: synchronous Context notification copy

The first candidate `2e84858` completes hosted foundation with 1,472 tests,
zero failures/errors/skips. Its two source-verified recovery runs retain eight
processes and complete the unchanged 45-second soak. Peak/growth are
1,452.07/82.93 MiB (handoff) and 1,446.32/101.77 MiB (installed IDE). These are
improvements over the baseline measurements below, but both still fail the
64 MiB growth limit. [Exact results](evidence/fresh-message-storage/first-candidate-hosted.json)
retain both failures rather than promoting the component benchmark.

Resolving the baseline Context profile offsets against the exact build's
recorded symbol ranges identifies a redundant copy inside
`SPELLexecutor::executorNotification`. Its unchanged body only reads the
incoming message and synchronously updates the execution model. The follow-up
borrows that const message for this one callback; the incoming task continues
to own it. No queue, thread, callback signature, message mutator or asynchronous
lifetime is changed. The complete original callback body is SHA-256 guarded.
[Resolved allocation paths](evidence/fresh-message-storage/context-call-sites.json)
retain the source and binary identities used for this attribution.

The exact frozen and candidate callback bodies are compiled against the real
message class with model/context collaborators replaced by fixtures. Tests
exercise repeated and changed stages, status/error paths, CALL/RETURN,
asynchronous notification types, unknown types, unchanged caller messages,
and the steady-state allocation benchmark. All 145 focused follow-up checks
pass without failures/errors/skips. The 10,000-callback benchmark falls from
90,000 allocations / 7,990,000 bytes to zero after warm-up. Whole-runtime acceptance still
requires the follow-up hosted rebuild.

## Initial baseline

The source-bound baseline is `a0a1686baf5b5ab65698eb030005de3bcbd42a49`.
Core run `40449908895` passes 12 of 14 jobs. Both recovery jobs still fail
the unchanged 64 MiB growth criterion despite retaining all eight processes
and completing their 45-second soaks.

| Baseline | Peak MiB | Window growth MiB |
| --- | ---: | ---: |
| Handoff | 1498.88 | 129.35 |
| Installed IDE | 1494.69 | 119.82 |

Both archive digests and all 132 recorded source hashes per recovery archive
match the baseline. First/last ten-second windows show approximately 126.15
and 116.50 MiB anonymous growth, but only 1.50/1.51 MiB file-backed growth.
File and shared-memory accounting overlap. The prior log-retention correction
does not resolve this anonymous-memory growth. The independent allocation
diagnostic (artifact `12710630504`, digest
`46b2738dd49135f20de387dda65f68cdb0c8d21ec3edea60f789acf39d624fde`)
also matches all 132 source inputs and shows `SPELLipcMessage::set` called
from `SPELLserverCif::prepareMessage` / `specificNotifyLine` among repeated
Executor allocation sites. This supports targeting construction, not a claim
that it accounts for every byte of whole-family growth.

## Change

Previously, bounded map storage was reused only when copying a message.
Fresh messages assembled with `set()` allocated new nodes for every field.
The setter now transfers one cleared, exclusively owned map node from the
existing process-local cache. Exact keys are preferred; otherwise a cached
node is rekeyed after it leaves the cache lock. A field becomes visible only
when the producer sets it. Existing values, binary keys/values, empty values,
ordering and independent message ownership retain their original semantics.

The cache remains capped at 32 maps, 64 fields per map and 64 KiB of retained
string capacity per map. Empty cache slots are compacted. Contention or an
empty cache uses ordinary allocation. No class layout, wire format, thread
dispatch, logging, authority, deadline, workload, sanitizer setting or resource
acceptance threshold changes. This is bounded storage reuse, not disk swap.

The experimental builder fingerprint is updated to the exact new composition;
its source guards remain strict. The compiled storage harness is now included
in the service qualification source inventory.

## Validation and remaining work

The sanitizer-backed frozen/candidate benchmark constructs 10,000 fresh
eight-field messages with changing key shapes/order. After warm-up, allocation
counts decrease from 80,000 / 7,680,000 bytes to zero. Both classes remain
176 bytes on this toolchain. This component result is not an RSS/leak verdict.
The tests also cover copying, concurrent fresh construction, overwrite,
binary/Unicode/empty fields, decode/encode, cache saturation and capacity bounds.
223 distinct checks pass across storage, codec, stream, trace, log retention,
resource and comparison-profile tests. The trace harness uses CPython 3.13.16.
Nine unrelated native admission cases cannot create Unix sockets in this local
environment (EPERM) and require the hosted run; no test skip was introduced.
Exact local test receipts and incomplete attempts are retained alongside
[the baseline](evidence/fresh-message-storage/baseline.json).

A separate baseline optimized-IDE comparison failed before child-running with
seven uncertain driver effects and recorded `effect_deadline_expired` causes.
It never reached its memory soak and cannot qualify memory or recovery.
[The failed receipt](evidence/fresh-message-storage/optimized-ide-startup-failure.json)
is retained; this message-storage change does not establish its root cause.

Mandatory native handoff and installed-IDE recovery must be rebuilt on this
new source. The required profile remains 2 GiB RAM, no swap, at most 1,792 MiB
peak and at most 64 MiB window growth. Both hour-long comparisons and repaired
swap comparisons also remain separate evidence. All eleven full-release gates
remain unqualified; no merge, stable tag or release is justified by this change.
