# Bounded storage for newly constructed native messages

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
