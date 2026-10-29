<!-- BEGIN CURRENT DEV81 RECONCILIATION -->
# Current dev80 resource outcomes and local dev81 changes

Remote hosted SPELL is `4c55321bad3a66118e087f1b8b9d7b9f55028065`
(`0.8.0.dev80`), tested PR merge `a98091b8a4cb1c6bc1c4c41f427da6cb06477425`,
with identical tree `b07ce296c6a1146753f19c34f63da0ebca5342bb`.
The paired IDE remains `b1472b4d5a515b9082db139fb8e16b63677a052e`
(`1.2.1.dev7`), tree `8fb91191ead6c4fa60089763c08fc8f3959a20c3`, tested merge
`cb49a0cdcabe7008d3d475c3af74b32c4e3b2d58` with the same IDE tree.

The local, unpublished dev81 candidate is `253d9e726c7c8a7ffe20ea201094bd9755d47089`,
tree `15498fc275c5e047570b8678f9e5b9a82fe6cbff`. Its selected 14-file regression run
is bound to `699c6a5e88940d5e06d62a63e3724139616b8866`, tree
`ebb2e6e198f75c4666af8f169678621f0fa6bff3`: **306 passed, zero failures, errors or
skips, 145.34 seconds**. The later two-line worker comment change is AST-identical;
bytecode identity is not claimed. The 306-case run was not rerun at that later
comment-only commit; the separate 418-case diagnostic at253 is recorded in the
current receipt with its own result and source binding.
These selected tests are neither the complete foundation suite nor native/IDE
workload acceptance. Original lint, formatting (149 files) and typing (23 source
files) checks pass at local253. The first wrong-resolved-interpreter attempt
failed on missing tool modules and remains preserved separately.
[Source-bound reconciliation](evidence/qualification-dev81-local-20261028.json) records the exact
identities, raw receipts, hashes, unsuccessful attempts and scope boundaries.
A subsequent documentation-only branch head or synthetic PR merge is not new
executed evidence; each result remains bound to its recorded test subject.
A fresh read-only remote reconciliation at 23:40:23 UTC retained both open draft
PRs and the source/merge identities above, SPELL base `466b7bf5…`, IDE base
`c5edbdae…`, and diagnostic branch `dc76fcc1…`. The v0.8 tag and release endpoints
returned 404; both repositories had zero queued or in-progress hosted runs at
that observation. These facts do not exclude subsequent delayed write effects.

| Scenario | Profile / requested duration | Result | Original soak seconds | Growth bytes | Ordered samples | Audit files / bytes | Artifact |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| handoff | allocation-observer diagnostic / 45 s | PASS | 45.485619880 | 37,875,712 | 48 | 23 / 1,909,468 | 12853395374 |
| handoff | original sanitizer/no-swap / 45 s | PASS | 45.616020781 | 40,593,408 | 47 | 23 / 2,450,192 | 12852198417 |
| ide | original sanitizer/no-swap / 45 s | PASS | 45.550360855 | 40,472,576 | 48 | 27 / 2,417,120 | 12851769656 |
| handoff | asan-noswap / 300 s | FAIL | 302.421926704 | 333,787,136 | 171 | 23 / 10,911,020 | 12855837576 |
| ide | asan-noswap / 300 s | FAIL | 303.657502183 | 327,299,072 | 169 | 27 / 10,394,320 | 12854724702 |
| handoff | asan-o2-noswap / 300 s | FAIL | 302.872318874 | 256,098,304 | 171 | 23 / 7,457,459 | 12857756371 |
| ide | asan-o2-noswap / 300 s | FAIL | 303.222662301 | 328,704,000 | 171 | 27 / 10,316,275 | 12858091541 |
| handoff | asan-swap / 300 s | FAIL | 303.123112668 | 296,574,976 | 170 | 23 / 9,125,957 | 12855594384 |
| ide | asan-swap / 300 s | FAIL | 302.862476619 | 245,125,120 | 170 | 27 / 7,019,141 | 12857466926 |
| ide | optimized-noswap / 300 s | PASS | 303.473481577 | 3,379,200 | 173 | 27 / 10,698,664 | 12856497153 |
| handoff | asan-noswap / 3600 s | FAIL | 3603.335168907 | 1,076,039,680 | 1717 | 23 / 115,443,210 | 12855809168 |
| ide | asan-noswap / 3600 s | FAIL | 3600.589913021 | 1,079,748,608 | 1737 | 27 / 120,028,422 | 12855154534 |
| handoff | optimized-noswap / 3600 s | PASS | 3602.321767715 | 5,296,128 | 1764 | 23 / 118,874,232 | 12859190925 |
| ide | optimized-noswap / 3600 s | PASS | 3603.986820283 | 7,610,368 | 1783 | 27 / 119,714,098 | 12859190975 |

Both original dev80 sanitizer/no-swap hours failed growth and resident/combined
peak budgets: handoff 1,076,039,680 bytes over 3,603.335168907 seconds, IDE
1,079,748,608 bytes over 3,600.589913021 seconds. Original audit archives retain
23 files / 115,443,210 bytes and 27 files / 120,028,422 bytes respectively.
All six optional sanitizer 300-second comparisons also failed. Optimized,
swap-enabled and diagnostic results do not replace mandatory acceptance.

The completed dev77 optional matrix is no longer pending: both optimized
300-second scenarios and both optimized hours passed; all six sanitizer
300-second scenarios failed. Every completed artifact and exact overlay was
independently checked. The dev77 original hours remain failed with the recorded
Context exits, later Docker state and failed kernel queries preserved. No later
pass or separate defect establishes those historical exit causes.

The exact dev80 native full-disk artifact `12851393538` passed its bounded
fault scenario: actual native errno 28 during write, explicit worker exit 1,
no false completion, two retained holds and original owner epoch retained.
The 963-byte acknowledged audit prefix was preserved; the later 8,192-byte
record with an incomplete tail remains explicitly retained. The 21 audit
components also pass. These are durable audit/fault components, not whole
deployment restore, old-authority fencing, recovered execution authority or
long-duration capacity qualification. They do not explain the historical first
control-report denial before ENOSPC injection.

Both optimized dev80 hour jobs have completed; their independently verified outcomes are recorded in the source-bound receipt and remain diagnostic-only.

The bridge field-transfer correction borrows the request's field subtree only
during synchronous transfer into independently owned native message strings.
Actual frozen-native-message ASan/UBSan component coverage passed all 33 checks,
including 12 input/error/ownership shapes. Over 10,000 iterations, short fields
fell from 90,000 allocations / 4,800,000 bytes to zero; long fields from 110,000 /
10,640,000 to 20,000 / 3,560,000; absent fields from 10,000 / 480,000 to zero.
Output digests matched. The seven retained-binary rechecks reproduce those
measurements and overlap the original coverage. This measured component change
does not establish the cause or removal of whole-hour family growth.

Prior Executor evidence binds selected BufferedWriter allocations to the
unchanged fixture's progress-file writes and observes those selected samples
subsequently freed; measured primary-allocator resident retention is distinct
from live allocations. Context Python and other anonymous growth remain
incompletely attributed. Native/Python/map/cgroup windows are not simultaneous;
quarantine, primary mappings and RSS overlap and cannot be summed as separate
categories. Durable audit bytes remain separate from filesystem cache.

FakeStack run `40771852756` failed both original 300-second checks. The reader
prerequisite passed in both exact images, but actual Context coverage was zero:
discovery ran before the first original Context resource row. A two-path observer
repair has 30 local passes and binds discovery to the first complete original
PID/namespace-PID/start-tick record; its hosted rerun has not started. Its local
tree is `4d07383d9ca9fc27fd9acc00fe25d65858b3ad52`; remote diagnostic head remains
`dc76fcc1ef7150c4ea68636ecd76fd4e97ed705c` at the retained 22:47 UTC read.

The historical bridge string-mutation sample's module return offset 722242 is
inside `main` at offset 5692. The recorded executable SHA is
`f538da0c7039ce9a06c4ddd9b7e56f5239a6602193b68dd5dfda8a5aac689db6`.
A direct search of 964 retained ZIPs found six different bridge binaries and no
exact match; no exact source line is established. Nested archives and absent
hosted images are outside that search. No input-line buffer rewrite was made.

The original 45-second and sustained workloads retain ASan/UBSan, no-swap
mandatory settings, all ordered samples, original audit records, declared
concurrency and deadlines, the 67,108,864-byte growth limit and existing peak
budgets. No fixture rewrite, sample exclusion, relocation of measured usage,
sanitizer purge, forced cleanup or audit deletion establishes a valid pass.
The optimized handoff pre-soak SYS=2 rejection is a separate functional failure.
The first historical native ENOSPC control-report denial remains unexplained;
later native ENOSPC/restart passes do not establish whole-deployment restore,
old-authority fencing, recovered execution authority or long-duration capacity.

All eleven mandatory full-release gate groups remain **unqualified**, the public
runtime remains disabled, and no stable merge, annotated v0.8 tag or GitHub release
is claimed. Existing owner authorization permits publication once every mandatory
criterion passes at the exact final joint identities; production migration remains
unauthorized.

GitHub source-tree write connector requests stalled and the separate CLI push lacked
authenticated Git credentials. That access failure prevents publication and hosted
requalification of the ready local changes. It is separate from the unavailable
production-like qualification cluster with enforced NetworkPolicy and the
independent implemented-system security reviewer. None of those external blockers
excuses the failed memory/foundation results or unfinished native, browser,
deployment, audit-restore and packaging work.

A separate 25-second PR metadata attempt timed out; the 23:05 UTC independent
read retained the old body and remote dev80 head. A separate 25-second contents-API
observer-file attempt also returned no result; the 23:07 UTC branch read retained
diagnostic `dc76fcc1…`. Delayed effects are not ruled out and require a fresh
remote read before resuming. These are connector/credential execution failures,
not permission or automatic-approval rejections. A newer independent read at
23:25:22 UTC again retains diagnostic `dc76fcc1…`, product `4c55321b…` and the
unchanged PR body; that observation does not rule out a later effect.

The final 23:40:23 UTC read again retained both draft PR heads and merge
identities, diagnostic `dc76fcc1…`, and both intended base branches. No queued or
in-progress hosted runs were present in either repository. Stable v0.8 tag and
release lookups both returned 404. No delayed effect was observed at that time;
the failed write attempts remain preserved and future effects are not excluded.

## Preserved historical resource checkpoints

Earlier current/pending statements below are historical snapshots, not current
qualification assertions. All original limits and failed attempts remain binding.

<!-- END CURRENT DEV81 RECONCILIATION -->

# Dev77 executed qualification — release blocked

SPELL `c9ec5c5ec8338fe1530bc57ebb30fbb6ba410034` (0.8.0.dev77), tested PR merge
`de3187504b8225e842a69ee3b9947068ace55347`, identical tree
`990a63c38bb71778e4dfaffd417e4000e7b3dc74`; paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` (1.2.1.dev5).

All 14 bounded core jobs pass, including 1,623 foundation tests and 95 overlapping
fault checks. The 241 portable checks and all nine lifecycle repetition jobs pass.
The measured bridge-node correction has 147 distinct local regression passes:
10,000 alternating frozen-message event/reply cycles fall from 220,000 allocations
and 13,340,000 bytes to zero after component warm-up, with identical output bytes.
The original workload excludes no samples or audit records and retains its
sanitizers, concurrency, deadlines, accounting and acceptance limits.

Original mandatory ASan/UBSan/no-swap 45-second acceptance passes: handoff
45,858,816 bytes (43.73 MiB), installed IDE 41,689,088 bytes (39.76 MiB), against
the unchanged 64 MiB growth limit. These bounded passes do not establish
sustained stability. Both original sanitizer hours FAIL in run40663274512.
Handoff artifact12808681280 retains1,528 ordered samples over3,265.006890096s;
IDE artifact12808675802 retains1,560 over3,272.245384271s. Original Context
hostPID17851/ns37 and23753/ns37 respectively have exited pidfds. Handoff has
no sampled OOM kill; IDE samples OOMkill=1. Later Docker state records
OOMKilled=true in both. Both kernel queries failed with RuntimeError. No direct
kernel victim record is available; Context/OOM association remains an inference.
The complete allocation/exit cause and historical worker-exit causes remain open.

The first actual native full-disk attempt, artifact12804773176, FAILS BEFORE
INJECTION: worker1 receives context_request_denied from control-report. Its
original HTTP status/code was not retained. The coincident Context startup
SSLEOF is not a demonstrated cause. The unchanged rerun, artifact12809730299,
passes actual native errno28, explicit failure exit1, no false completion and
retained holds, original epoch and audit prefixes. The21 audit components pass.
Three diagnostic runs with the observer inside actual Context containers pass,
with positive coverage in all15 containers and only expected auxiliary denials;
the unexpected control-report denial was not reproduced. Two earlier host-only
observers were ineffective (zero target replies), and are preserved as failed
observation methods. Later passes do not explain the first failure.

Both failed original hours retain complete ordered audits:23 files/101,388,487
bytes and27/105,896,851 bytes. Source overlays and all raw records verify.
Audit component and ENOSPC passes do not establish whole-deployment restore,
execution-authority recovery or long-term deployment capacity.

Read-only Python/ASan diagnosticcc28549d, run40670896442, reproduces the exact
combined overlay and143 source bindings per scenario. Both collection jobs pass;
both underlying300-second memory checks FAIL continued growth. The two original
Executors each stay at14 pymalloc arenas, with less than0.5MiB additional live
small-block storage each. Global ASan quarantine and primary/shadow resident
regions grow; other anonymous mappings and Context Python accounting remain
unattributed. Counters have separate explicit times and cannot be added as a
coeval resident-memory ledger. No GC, allocator trim, sanitizer purge or limits
change was used. These diagnostics cannot substitute for mandatory acceptance.

All completed dev76 and evidence-only c451 comparison outcomes have independently
reproduced overlays: optimized300/3600-second scenarios pass; all six sanitizer
comparisons fail in each matrix. Both dev76 accounting hours fail, and both c451
original hours fail. The c451 handoff family has all eight original pidfds exited
after counter observation loses its bound live container; IDE has Context exited.
Later full foundation observer passes do not explain dev76's first burst failures
and600-second timeout. The dev77 optional matrix is still running at this snapshot;
completed sanitizer300 scenarios fail and optimized300 scenarios pass. Remaining
outcomes require collection and independent verification before use.

The complete qualification source archive matches all2,387 Git blobs, modes and
members of tree990a.31 regular archives verify3,172 overlapping recorded source
bindings and563 raw audit files; the unchanged ENOSPC rerun adds75/24. Ancillary
archives without recorded source bindings are digest-checked only. Installed IDE
client/panel/app bindings match pinnedc5; public launch and full IDE acceptance
remain unqualified. All763 current native requirements remain unqualified:
555 immutable input bindings yield546match/9drift,47historical reports unchanged,
and57 historical capture hashes remain unresolved.

All eleven full-release groups remain open. Missing implementation/acceptance
includes sustained native memory/liveness, full native/driver semantics, public
launch/debugger, browser/WSS/Git collaboration, complete Compose/Kubernetes fault,
restore/execution-authority recovery, upgrade/rollback, security disposition and
final stable joint clean-install E2E. The enforced-network-policy production-like
qualification cluster and independent implemented-system security reviewer remain
distinct external resources. Refreshed packaging boot probes inspect older8184/
IDEc5 and retain findings and missing Qt notices; no refresh is promoted.
No stable merge, annotated v0.8 tag, GitHub release or production migration occurred.

[Current source-bound receipt](evidence/qualification-c9ec5c5e-20261028.json).
The following candidate checkpoints are preserved as history.

---

# Dev77 measured bridge ownership correction — fresh acceptance pending

This candidate reuses exclusively owned JSON field and event/reply header nodes
which the exact prior bridge trace shows being repeatedly recreated. Absent
fields remain detached from the rendered object; only current whitelisted fields
are reinserted and overwritten. The inactive field cache retains at most 64 nodes,
each with value capacity at most 4 KiB and key capacity at most 128 bytes. Large
and excess nodes follow normal destruction. The existing output mutex, JSON
serializer, ordering/escaping, acknowledgements and large-buffer release remain.

147 distinct local component tests pass. In the real frozen-message component,
10,000 alternating event/reply cycles measure 220,000 allocations/13,340,000 bytes
with the exact dev76 encoder and zero after warm-up with this correction. Output
digests match. Tests cover every whitelisted field, absent/stale and excess fields,
Unicode/NUL/invalid UTF-8, 4 KiB boundaries, 2 MiB payloads, callback exit/cancellation,
audit and diagnostic overlays. Warm-up applies only to this component benchmark;
no mandatory native samples, fixtures, limits or audit records are excluded.

These measurements do not establish a whole-family improvement or the cause of
all earlier exits. Fresh exact-source core/native/installed-IDE/lifecycle/audit and
original sanitizer-hour acceptance is required. All eleven full-release groups
remain open. The following dev76 checkpoint is historical hosted evidence.

[Current local source-bound receipt](evidence/owned-bridge-fields-20261028.json).

---

# Dev76 executed qualification checkpoint — release remains blocked

SPELL `3b18313899ebe07d84b8e98b86c8f9b5020c3263` (0.8.0.dev76), tested merge
`65c7a6f8285e102ccda375a747c1a780b4ac1b93`, identical tree
`914a214fe00aa31a5e7774a1fff604d1a5395d09`; paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` (1.2.1.dev5).

All 14 bounded core jobs report success after an unchanged foundation rerun of
1,621 tests, with 95 overlapping fault checks, 241 portable tests and all nine
lifecycle repetition jobs passing. The first foundation attempt failed two
10-request driver-burst cases, then hit its original 600-second suite deadline
after 1,085 observed passes. It emitted no final failure traceback or JUnit.
The rerun passed in 566.463 seconds; an observation-only full run passed 1,621
in 574.954 seconds and three exact focused repetitions passed both cases.
These later passes do not explain the first failure. Its cause and capture gap
remain open. No fixture, assertion, concurrency or deadline was relaxed.

Original mandatory ASan/UBSan/no-swap 45-second memory acceptance passes:
handoff 41,750,528 bytes (39.82 MiB), installed IDE 42,827,776 bytes (40.84 MiB),
against the unchanged 67,108,864-byte growth limit. These bounded passes do not
establish sustained stability. Both original sanitizer hours FAIL in run
40653592773. Handoff artifact 12801712425 retains 497 ordered samples over
1,024.340570910 seconds; IDE artifact 12801917364 retains 505 over
1,045.865087283 seconds. Original Context host PIDs 18117/ns37 and 25734/ns37
respectively have exited pidfds at failure. Handoff samples an OOM-kill counter
rise to one; the IDE trace ends with zero sampled OOM kills, followed by later
Docker OOMKilled=true. Kernel queries failed with RuntimeError in both runs.
The Context/OOM association is an inference, without a direct kernel victim
record. Neither this observation nor the callback/request-ID fixes explains
historical unobserved worker exits.

Both peaks reach 2,147,500,032 bytes. The last complete samples contain about
2,024 MiB anonymous memory, 2.6–3.0 MiB file/shared memory and 1.9 MiB kernel
stacks. Live allocated bytes are small compared with retained allocator heaps;
prior exact overlays demonstrate sanitizer quarantine and growing primary/
shadow mappings, with other anonymous mappings still unattributed. Observed
huge-page usage varies between runners; it is not proof of waste or a source
cause. Exact dev76 accounting/mapping/symbol diagnostic 14272042, run
40659879477, is running under unchanged original hour workloads. Its green
collection status, if any, cannot establish acceptance.

Actual native Executor ENOSPC passes in artifact 12800204672: write errno28,
explicit exit1, no false completion, both holds and original owner epoch
retained, and raw ext4 volume/prefix bytes independently verified. The 21
bounded audit components also pass. Hour-run audit files remain complete and
ordered: 23 files/32,305,678 bytes for handoff; 27/33,573,543 for IDE. All tails
and unsuccessful attempts are preserved. These component passes do not prove
whole-deployment restore or execution-authority recovery. The dev75 attempt
that failed before injection on a registration broken pipe remains unexplained;
nine separate instrumented actual ENOSPC passes do not establish its cause.

The complete source archive matches all 2,383 Git blob IDs, modes and members
of tree914a. Source/tool checksums verify; tool archives are only digest-checked.
31 regular archives verify 3,172 overlapping recorded source bindings and 577
raw audit files, including the failed first foundation report. The unchanged
foundation rerun adds 258 bindings. Each completed diagnostic overlay is
reproduced exactly before interpreting its result. Installed IDE module and
native client bytes match the pinned companion source. These are scoped source
verifications, not complete shipped-image or release qualification.

The dev73 joint inventory branch and corrected refreshed public offscreen/xcb
probes remain diagnostics. Baseline IDE startup fails on missing glib. Refreshed
images retain vulnerabilities and missing Qt notices; full native, OS, Python,
IDE and plugin SBOM/license/advisory disposition and independent implemented-
system review remain open. No refreshed packaging is promoted to dev76.

All eleven full-release groups remain open, including all 763 current native
requirements/full driver semantics, public native launch, full debugger,
authenticated browser/WSS recovery and Git collaboration, complete deployed
workloads, restore/execution-authority recovery, upgrade/rollback, final stable
joint packaging and clean-install acceptance. The production-like qualification
cluster with enforced network policy and independent implemented-system security
reviewer are distinct missing external resources. No stable merge, annotated
tag, GitHub release or production migration has occurred. Publication is
already authorized once every mandatory final-source criterion passes.

[Current source-bound receipt](evidence/qualification-3b183138-20261028.json).
The following sections preserve earlier candidate checkpoints as history.

---

# Dev75 hosted checkpoint; full release remains unqualified

SPELL executable: `53b7e8ac38b4152d1ffbee6c0dfd549ac9b8fd75` (0.8.0.dev75).
Tested PR merge: `ac40bab3194342eb137e3416b9b18764a903bd7c`; identical tree:
`27a197b39ecafd22b6abbc8320b11ece962ffecb`.
Paired IDE: `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` (1.2.1.dev5).

All 14 core jobs, 1,616 foundation tests, 95 overlapping fault checks, 241 portable
tests and all nine lifecycle repetition jobs pass. Counts overlap. The original
45-second ASan/UBSan/no-swap memory checks pass against the unchanged 64 MiB bound:

| Workload | Growth | Peak | Ordered samples |
| --- | ---: | ---: | ---: |
| Native handoff | 44,318,720 bytes (42.27 MiB) | 1,305,194,496 bytes | 48 |
| Installed IDE recovery | 44,642,304 bytes (42.57 MiB) | 1,312,448,512 bytes | 48 |

Independent verification covers 31 regular archives, 3,172 overlapping source
bindings and 573 raw audit files. Three installed IDE module hashes and the
native IDE client hash match the pinned IDE. These remain bounded subsets.

Both original sanitizer hours fail in run 40644298431:

* Handoff artifact 12797338412 contains 491 ordered samples over 1,019.809039681 s.
  Context host PID 17355 / namespace PID 37 disappears between 1,017.735047316 s
  and 1,019.809039681 s as the sampled OOM-kill count rises to one.
* IDE artifact 12798096551 contains 499 ordered samples over 1,035.563428262 s.
  All eight original processes, including Context host PID 26628 / namespace
  PID 38, remain in its final sample, which records zero OOM kills. Later Docker
  state marks OOMKilled=true. Its victim and exit interval are not sampled.

Both containers remain running in their later state; both peak at 2,147,491,840
bytes. No kernel victim PID record is available. Last complete cohorts contain
about 2,024 MiB anonymous memory, 2.6–2.8 MiB file/shared memory and 1.875 MiB kernel
stacks. Native live allocations are roughly 9–10 MiB per Context/Executor while
allocator heaps retain hundreds of MiB. Exact diagnostic overlays observe ASan
quarantine retention. The complete resident allocation cause is not established.

Older dev73 hours record zero anonymous huge-page memory; the newer original
hours reach 1,012 / 992 MiB. This is an observed environment difference, not a
counterfactual estimate of wasted memory or proof of a source-level cause.
Diagnostic 8e0fe0ff / run 40647340475 collects numeric mappings, unchanged original
resource samples and postmeasurement symbols. Its handoff outcome also fails;
its IDE outcome is pending. Diagnostic collection success cannot qualify runtime.

All 23 / 27 retained audit files verify: 32,695,787 / 31,182,594 bytes. Syntax,
newline and ordering checks pass. This does not establish execution completeness,
whole-deployment restore or execution-authority recovery. No required records,
failed attempts, original samples or uncertain historical tails were removed.

The current native ENOSPC attempt, artifact 12796368711, fails before injection.
Worker 6 child registration returns context_unavailable / BrokenPipeError after
3,014 ms of registration RPC; total admission is 3,152 ms and thread CPU is 37 ms,
below the unchanged 4,000 ms admission deadline. Its cause remains unknown.

Independent diagnostics b51cedb and 4ec2e11 run three and six original cohorts.
All nine actual native ENOSPC attempts pass. Their 225 member-bind calls correlate
with server connection phases; neither set records a capacity rejection or client
I/O failure. Those passes do not explain the earlier broken pipe, historical
5,382 ms registration, 2,007 ms admission or separate 90-second worker exits.
Both diagnostic sources, all 675 source bindings and 216 raw audit files verify.

All 12 dev74 comparison/hour overlays verify and fail before execution on the
full native interface compilation error. Dev75 preserves the original callstack
interface layout/vtable and provides the original-getter fallback. That failed
build, unsuccessful local attempts and all earlier failures remain historical
failures. The hosted foundation passes; the earlier restricted local full
foundation attempt remains failed and unqualified.

Joint inventory 57b4d64 / run 40644955587 inspects dev73 and the paired IDE, and
is not promoted packaging. Refreshed offscreen/xcb public-main probes pass with
the actual project title; baseline startup still fails on missing glib. The
refreshed base in this run is digest 1151df52..., distinct from the earlier
8a7c3cd3... diagnostic. Native / baseline IDE / refreshed IDE / refreshed server
have 932 / 342 / 237 / 161 matches respectively. Unique advisory IDs are
227 / 146 / 116 / 69; baseline IDE has 145 CVE IDs plus one GHSA. Installed
notice bytes verify, but PySide6_Essentials and shiboken6 report no installed
notice members. Unknown licenses, complete vulnerability dispositions and
independent implemented-system security review remain open.

Fresh compatibility input reconciliation checks all 555 bindings against dev75:
546 match, nine drift, and all 47 historical reports are unchanged. All 763
current native requirements remain unqualified; 57 historical capture hashes
remain unresolved. Portable tests do not replace this acceptance.

All eleven full-release groups remain open. Public native launch, full original
driver semantics, debugger/browser/WSS/Git integration, full deployed workloads,
restore/execution-authority recovery and upgrade/rollback still require work.
The production-like cluster with enforced network policy and an independent
implemented-system security reviewer remain separate external resources.
Publication is already authorized once every final-source criterion passes;
production migration is not authorized. No stable merge, tag or release exists.

[Source-bound receipt](evidence/qualification-53b7e8a-20261028.json).

The following sections preserve earlier checkpoints and failures as history.

---

<!-- dev75-build-correction:start -->
# Current dev75: full-interface build correction requires fresh qualification

Dev74 executable `72b546b1b948f1b01850b8c0ab37c298c6f6ac4a`, tested merge
`d3f7c6bff0bda0b963382e1885470b9ac32cef01`, fails full native compilation:
CIF accesses `SPELLcallstackIF`; the new concrete helpers were absent there.
Allocation artifact12797015866 and sanitizer-hour artifacts12796402169 /
12795809505 retain the build logs. Neither hour executes a memory workload.
Earlier component passes did not cover this interface boundary.

Dev75 uses a free adapter declared alongside the unchanged real interface.
Known concrete callstacks copy under their existing lock; other implementations
use their original virtual getters. Original class layouts and vtables remain
unchanged. The regression now compiles actual methods through the actual
frozen/candidate interface and tests an alternate implementation.109 affected
interface/filename/memory-overlay components pass locally, with unchanged
sanitizers and oracle. Fresh whole-native mandatory and sustained results are
required at the exact new source. All earlier failures and all eleven open
full-release groups remain. No stable merge, tag or release.
<!-- dev75-build-correction:end -->

<!-- dev74-resume:start -->
# Current qualification: dev73 evidence reconciled, dev74 changes pending

Executable `8184bde25c58cb8b25a71fd794c38d3e3e1828d6` (`0.8.0.dev73`),
paired IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`; tested merge
`fb2a6d7065ee52229407f78aaa64fb2a644c57f4` has identical tree
`e7c1503f3e03b325798367871f4cb6529b7fbf85`.

All14 core jobs/1,613 foundation checks, nine lifecycle repetitions, actual
native ENOSPC and21 audit components pass. Original ASan/UBSan/no-swap45-second
handoff/installed-IDE growth is52,568,064/47,792,128 bytes (50.13/45.58MiB),
against the unchanged67,108,864-byte limit. Both retain48 observations.
Fresh independent verification covers31 archives/3,146 overlapping source
bindings/577 raw audit files, plus installed companion IDE inputs.

Both original sanitizer hours fail. Handoff retains1,029 ordered observations
over2,153.634870127 seconds; IDE retains1,048 over2,205.745637089 seconds.
Original Context namespace PID37 disappears during the first sampled cgroup
OOM-kill intervals (2,147.373–2,149.472 /2,201.553–2,203.661 seconds since first
observation). Later Docker OOM state also remains retained. The kernel victim
PID is not directly recorded. Before loss, anonymous memory is about2,022MiB,
file/shmem about3MiB, with much smaller sampled live native allocations than
allocator heaps. This does not prove absence of application leaks or identify
every allocation path. All23/27 raw audit files and65,429,630/70,789,644 bytes
verify complete and ordered. Whole-deployment restore remains unqualified.

All22 retrieved current/predecessor comparison/hour overlays reproduce exactly.
Optimized300-second and one-hour scenarios pass diagnostically; sanitizer
comparisons fail. Current ASan handoff artifact12780701369 separately fails
before native startup, with a Context-report denial and close-time connection
refusal chain. It is not classified as an OOM. Historical5,382ms registration,
90-second worker-exit and2,007ms admission failures remain separately unresolved.

Dev74 adds measured scope-owned filename and LINE/CSP snapshot reuse. It must
pass fresh original mandatory and sustained acceptance at its exact source;
component allocation reductions are not whole-runtime qualification. Sanitizer
settings, deadlines, concurrency, audit records, cgroup measurement and limits
remain unchanged. Earlier failures remain below and in retained archives.

The corrected independent packaging diagnostic `cf4c759`, run40642156662,
observes the exact installed project window and event loop in offscreen/xcb.
Baseline missing-GLib startup still fails. Refreshed IDE/server scans retain
237/161 vulnerability matches; all findings and license review remain open.
The refresh is not a promoted candidate. A production-like qualification
cluster enforcing network policy and an independent implemented-system security
reviewer are external gaps. Missing implementation/evidence are separate.

See [exact dev73 receipt](evidence/qualification-8184bde-20261027.json).
All eleven full-release groups remain false. No stable merge, tag or release.
<!-- dev74-resume:end -->

# Current dev73 candidate: fresh whole-runtime qualification pending

Measured corrections preserve original audit bytes, sanitizer options, limits,
deadlines, concurrency and workload. All163 final local components pass. LINE
audit calls reuse the existing locked prefix and synchronous two-part writer:
all10,004 acknowledged records match, while10,000 measured calls allocate
10,000 times before and once after. Callback lifetime guards settle tickets
after physical thread exit/cancellation cleanup and retire exited slots; native
MESSAGE/REQUEST controls and all subsequent dedicated fallbacks pass. The
historical90-second failure is not attributed to this newly reproduced defect.

The audit writer revisits previously advised completed prefixes after sync.
Real prior cache-bound failures and their raw records remain retained. A
deliberate successful advisory no-op reproduces256KiB retained by the old
cursor; final current tests revisit that prefix and keep every byte. Advice
remains advisory; no memory pass is inferred from a hint or component alone.

Both preceding6dd sanitizer hours fail. Handoff retains1,105 observations over
2,335.159192092seconds, peak2,147,495,936bytes. Its last sample has zero OOM/kill
counters; later Docker records OOMKilled=true. IDE retains472 observations over
991.929476709seconds with one sampled OOM kill. Both142-source overlays and all
23/27 raw audit files verify. Optimized results never replace sanitizer gates.

See [measured corrections](MEASURED_AUDIT_AND_CALLBACK_CORRECTIONS.md) and
[source-bound local receipt](evidence/measured-audit-callback-corrections-20261027.json).
All eleven full-release groups remain false. No stable v0.8 publication.

<!-- checkpoint-6dd8218:start -->
# Verified bounded checkpoint at 6dd8218, full release unqualified

Executable `6dd82189a4cdc4f021af3a357ccf747a0b459f98` (`0.8.0.dev72`), paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`; tested PR merge `4cead70f8c532bd8a0c064b309b22dfa9a1ed475` has
identical tree `e8a9e51741d48c340b1ecf7845e437da6fdb0b7a`.

All 14 core jobs pass, with 1,605 foundation tests and zero failures, errors or
skips. The real 10,000-admission Unix/JSON/peer-pin/epoch-rotation component
passes on CI; the prior local EPERM attempt remains failed and retained.
Both mandatory original-ASan/UBSan/no-swap 45-second memory checks pass:

| Scenario | Growth bytes | Peak bytes | All samples | Soak seconds |
|---|---:|---:|---:|---:|
| Handoff | 51,261,440 | 1,329,967,104 | 48 | 45.550778102 |
| Installed IDE | 51,329,024 | 1,055,313,920 | 47 | 45.616870880 |

Growth remains limited to 67,108,864 bytes, peak to 1,879,048,192, within a
2 GiB cgroup without swap. Original workload, concurrency, sanitizers, deadlines
and whole-cgroup measurement remain intact. Handoff growth is higher than the
preceding 30.30 MiB result; no whole-family improvement is inferred from the
isolated epoch-reader allocation correction.

All nine lifecycle repetitions pass: 72 startup families, three Listener
attempts and three 16-case terminal matrices. Actual native ENOSPC, 17 audit
components and independent extraction of the entire 8 MiB fault image pass.
All 16 core/audit archives verify 1,756 overlapping source bindings and 230 raw
audit files; repetitions verify 1,059 overlapping source bindings and 324 files.
The five ancillary workflows pass only within their 241-test portable,
prelaunch Compose/kind, static manifest and development Python inventory scopes.
Test counts overlap.

Both6dd sanitizer-hour attempts fail before one hour. The IDE archive retains all
472 observations spanning 991.929476709 seconds, peak 2,147,495,936 bytes and one
sampled OOM kill; an original process exits. All 142 exact-overlay sources and
27 raw audit files verify. These are failed sustained observations, never a
one-hour pass or a substitute for mandatory acceptance. Later successful
startups do not explain the historical registration/worker-exit failures.

See [source-bound receipt](evidence/qualification-6dd8218-20261027.json). All eleven full-release groups remain
false. Full original native/driver/763, public launch/debugger/browser/WSS/Git,
deployed Compose/Kubernetes/fault/restore/upgrade/rollback, complete security
disposition and stable joint artifacts/final installation remain unfinished.
There is no stable v0.8 merge, tag or release. Historical records follow.
<!-- checkpoint-6dd8218:end -->

# Native recovery resource acceptance

Dev65 `4f4a5ec` (run `40386646787`) passes 1,284 service tests, 95 overlapping
fault tests, 241 portable tests, 24 fresh startup cycles and all 16 terminal cases.
Twelve of fourteen core jobs and all five ancillary workflows pass. All nineteen
archives and recorded source hashes are verified, and the tested merge tree matches.
Both original families complete the full 45-second soak, preserve all eight
processes and advance every interval with zero memory-pressure/OOM events.
The fixed resource acceptance still fails in both profiles:

| Profile | Peak MiB | Window growth MiB | Required peak / growth MiB |
| --- | ---: | ---: | ---: |
| Handoff | 2,014.3 | 318.7 | 1,792 / 64 |
| Installed IDE | 1,991.6 | 347.7 | 1,792 / 64 |

The IPC and bridge allocation reductions and the bridge identity correction are
verified component changes. They do not resolve this full-family memory blocker.
No sanitizer settings, workload, soak duration, deadlines or resource thresholds
were relaxed. All eleven full-release gates remain unqualified; public runtime
and publication remain disabled. See the [latest complete receipt](evidence/native-codec/dev65-hosted/qualification-summary.json)
and [implementation/measurement notes](NATIVE_MESSAGE_CODEC.md).

Historical qualification records follow.

Dev59 `5d0d64f` completes both original-family soaks and settlement without OOM,
but **still fails** the fixed resource oracle. Handoff records five limit events,
a 2,147,491,840-byte peak and 201,719,808-byte window growth. Installed IDE has
no limit/OOM events but records a 2,133,803,008-byte peak and 206,489,600-byte
growth. Neither satisfies the 1792 MiB peak and 64 MiB growth requirements.
The codec correction and bounded dev60 diagnostic follow-up are described in
[NATIVE_MESSAGE_CODEC.md](NATIVE_MESSAGE_CODEC.md); prior failures below remain
historical evidence. Full recovery and release qualification remain false.

Dev58 `9e954dedc6ba985bc525fcdb1eb170affa2cd5b7` **fails** the new acceptance.
Core run `40369523732` completes with 12 successes and two failures. Both
handoff and installed-IDE recovery lose the original Context during the added
soak. The independent host samples and Docker state agree on an OOM kill.

| Profile | Samples | Peak resident cgroup bytes | Swap peak bytes | Limit events | OOM events | OOM kills |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Handoff | 42 | 2,147,483,648 | 0 | 52 | 1 | 1 |
| Installed IDE | 40 | 2,147,483,648 | 0 | 164 | 4 | 1 |

The original Context is absent from each final process sample; a running
container is therefore not evidence that the original family survived. The
host's pidfd check correctly fails. The successful-soak receipt and subsequent
resource-acceptance receipt are not emitted because the cohort raises first;
their absence is retained as a failed, incomplete qualification, never a pass.
Raw numeric cgroup/process observations and validation-only event denials are
retained in [the evidence directory](evidence/native-resources/qualification-summary.json).

The Context's latest observed live allocations are approximately 10 MiB while
its allocator heap is approximately 500 MiB. Executor and bridge resident
memory also grows. This narrows the investigation to allocation churn and
allocator retention but does not establish the allocation-site cause or prove
an application leak. The next corrective experiment must profile those sites
and preserve the existing sanitizer settings, authority deadlines and fixed
acceptance oracle. Merely increasing limits, shortening the soak or obtaining a
later green rerun would not resolve the demonstrated failure.

Dev57 allocator telemetry separates live allocations from retained allocator heap.
In one Context, live allocations stayed around 10 MiB while the ASan heap grew
past 500 MiB. The 1 GiB resident profile also permitted 1 GiB of swap; its observed
swap peak approached 664 MiB. This does not establish an application leak or
indefinite stability. ASan/UBSan settings remain unchanged.

Dev58 gives the two-Executor recovery probe the same 2 GiB combined budget as
explicit resident memory, with no swap (`--memory 2048m --memory-swap 2048m`).
Other cohorts keep their existing profiles. This is a diagnostic fixture budget,
not a production sizing recommendation. The public runtime stays disabled.

After A→B→A and same-owner reconnect, the original root, child and background
thread must advance in each of nine five-second intervals, with all original
pidfds alive. The fixture-only budget rises from 120 to 180 seconds to include
this added workload; admission, RPC, driver and lease deadlines are unchanged.

The host verifier requires consistent container identity, complete sampling,
zero swap, zero memory-limit/OOM events, peak resident usage at most 1792 MiB,
and no more than 64 MiB growth between median resident memory in the first and
last ten seconds of the 45-second soak. These thresholds are fixed before the
candidate executes. Failed or missing evidence fails the cohort and is retained.
A pass applies only to this workload and duration, not to a full release gate.

A separate real TLS regression showed explicit empty native events returning
400 at dev57. The frozen v0.7 event/display-buffer port deliberately supports
empty events. Dev58 preserves them as authenticated, idempotent audit records;
the 8192-byte bound, severity/scope rules, ownership and grant checks remain.
Dev57's unclassified RaiseEvent denial remains separately open until its cause
is established; later passes alone are insufficient.


## Dev82 integration — 2026-10-29 UTC

Exact executable16982c4dd698a937ce2ae4e37f4736055de9a2ce integrates dev81 plus native audit-generation identity fencing and bounded per-connection bridge-line reuse. The audit correction reproduces two historical-header races, then passes52 component checks. The bridge selection passes58 ASan/UBSan checks;10,000 short line reads fall from40,000 allocations/4,540,000 bytes to zero after component warm-up with unchanged digest. Counts overlap other suites and are not unique aggregate coverage. These do not establish whole-family sustained qualification.

GitHub writes recovered. Corrected observer47921d18/tree4d07383d is running in40828138175; results require complete collection. Fresh candidate CI, original45-second checks, sanitizer hours, ENOSPC and paired installed recovery remain pending. All eleven release groups remain false. Prior failure bodies and histories remain preserved. Current Qt6.10.3 attribution binds70/70 top libraries to exact upstream SDK bytes;12/230 Qt ELF files remain unbound and license/source/advisory review remains open. The qualification cluster and independent security reviewer remain unavailable.

Details: `evidence/qualification-dev82-integration-20261029.json`.


## Dev82 completed qualification and targeted follow-through (2026-10-29)

Exact SPELL8350123/tree7a17 (tested merge dd4c59a5, identical tree) with IDEb147/dev7 completed all44 jobs:35 successes and9 failures. Original45-second handoff/IDE growth is39,929,856/39,424,000 bytes (limit67,108,864). Original hours fail at1,053,573,120/1,050,255,360-byte growth and2,035,548,160/2,033,745,920-byte peaks (peak budget1,879,048,192). Original foundation times out at600s; all six optional sanitizer300s fail. Optional optimized hours pass7,639,040/7,350,272 bytes and do not replace mandatory acceptance.

The separate test-build correction136dbbc4 passes1,751 tests in558.09s under unchanged600s, zero failures/errors/skips, complete7,006-row journal, lint/format/types and package build/install/smoke. It is not the PR head or a full-release pass. Original timeouts and local capability failures remain preserved.

A separate exact-library control executes the unchanged two20ms buffered writers:181,981,184-byte cgroup growth over300.079s, live allocation delta−319 bytes, normal completion/cleanup. Sanitizer class/quarantine/RSS measurements overlap and are not added or subtracted from acceptance. This is demonstrated fixture retention, not a universal family lower bound. Late original-hour growth remains concentrated in Context and bridge; exact-ELF attribution and measured redundant-copy investigation continue without changing fixtures, limits, sanitizer checks or audit retention.

Unpromoted IDEdev9 has two identical hosted derivative builds and309 source passes with one unchanged Windows exclusion (all310 identities/order, eight Docker cases). The source suite imports repository source while using the actual installed PySide dependency. Separate installed desktop-byte/offscreen/xcb probes pass. These observations do not qualify native sustained recovery. Joint wheel timestamp drift was preserved; immutable-epoch builds and exact artifact installation are being requalified. GLIBCXX3.4.30 portability and full source/license/advisory/security review remain open.

Current security inventory remains243 packages/376 matches/187 advisory IDs. Actual pip candidate101 component/53 installed regressions and public startup pass; Qt229/230 SDK/prebuilt ELF relationships are not complete reproducible source builds or legal/advisory closure. All763 compatibility requirements remain unqualified, with555 bindings (546match/nine drift),47 historical reports and46 missing historical hashes. A prepared admitted TIME profile is only42 distinct requirements/168 dimensional checks.

All eleven complete release groups remain false. GitHub writes have recovered. Production-like enforced-NetworkPolicy cluster, independent implemented-system reviewer and Windows execution remain unavailable; unfinished implementation and failed tests remain separate. No stable tag/release or production migration. See [the completed-source receipt](evidence/qualification-dev82-completed-20261029.json). Historical bodies and raw unsuccessful attempts remain retained.


## Integrated dev83 candidate (2026-10-29)

Runtime8de53b3e/tree535fb71f (localbbd42db) combines measured native owned string transfer and GUI admission JSON move construction with the passing original-budget compiler corrections. Version0.8.0.dev83; IDEpair remains b147/dev7. Local103-case selection has97passes and six preserved AF_UNIX EPERM failures before product execution, zero skips/errors; original lint/format/types pass.31 original/affected hosted executions are pending at the final evidence/head identity. This candidate does not inherit dev82 passes or qualify any full release group. Original workloads, authority, sanitizers, deadlines, accounting, limits and audit retention remain unchanged. See [the prepared candidate receipt](evidence/qualification-dev83-prepared-20261029.json).
