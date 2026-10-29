<!-- BEGIN CURRENT DEV81 RECONCILIATION -->
# Current ownership measurements and local dev81 correction

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

Dev73 locked LINE audit-buffer reuse, callback exit/cancellation settlement and
deferred cache-prefix handling; dev75 filename/callstack ownership and the
interface-preserving adapter; dev76 caller-owned incoming request-ID rendering;
and dev77 exclusively owned bridge field/header reuse remain preserved with their
regressions. The dev77 frozen 10,000-cycle event/reply measurement remains
220,000 allocations / 13,340,000 bytes before and zero after component warm-up,
with identical output bytes. Its 147 distinct local regressions are historical
component evidence, not proof of sustained whole-family stability.

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

The intervening development fixes are retained at their own source identities.
Dev79 `17ac0d81afca81fe765177f4137e71641be2ef9b` integrates native STATUS snapshot
ownership and sequence reservation fixes, including actual-source ThreadSanitizer
reproduction of the prior counter/template races and owned missing-Csp storage.
Its snapshot lock is released before stack/send callbacks. The temporary
admission-body move preserves lvalue behavior and packet bytes; 10,000 rvalue
requests fell from 320,000 allocations / 28,310,000 bytes to 100,000 /
14,960,000 bytes in its separate component. Dev79's 119 integrated checks overlap
later collections and do not qualify the full family.

Dev80 `4c55321bad3a66118e087f1b8b9d7b9f55028065` binds acknowledgements to live
logical notification owners. The actual-source baseline reproduced an inactive
periodic STATUS ACK at Sequence=0 satisfying a different unsent CALL at Sequence=0.
The correction registers a stack-owned ticket before sending, removes it on
normal/error/cancellation exit, stores no inactive ACK credits and uses one
constructor-initialized, non-resetting notification sequence domain. The intended
wire Sequence values change under interleaving; other component wire bytes match,
so full wire-byte identity is not claimed. A receipt for an earlier retry of the
same live logical notification remains valid; this is not send-attempt fencing
or a durable-audit commit receipt. Existing configured waits, polling, reconnect
readiness and publish-before-ACK behavior remain. The separate component has
26 passing checks; the later integrated collection also exercises these paths.
These demonstrated defects do not establish unrelated historical startup,
control-report denial, driver-burst or Context-exit causes.

Hosted dev80 foundation failed its unchanged 600-second deadline: 1,674 collected,
1,039 completed PASSED outcomes in verbose stdout, an incomplete tail, and no final
JUnit. The clean local test-only `f59d17d0f8d25ea8c957ee910b9e50af6fc65422` attempt
also timed out at 600 seconds: 1,677 collected and 1,143 completed passing calls,
with retained ordered setup/call/teardown records but no final session/JUnit.
Zero recorded failed calls does not make an interrupted suite a pass. Measured
setup/call/teardown totals were 232.595 / 258.298 / 107.106 seconds; inspected
successful teardown paths do not establish a product ownership defect. Dev81's
bounded compilation reuse/batching and immediate result journal are locally
implemented; a complete foundation pass at the final candidate is outstanding.

A separate clean-source tail diagnostic at local253 selected 418 cases from the
534 f59 cases left unexecuted, excluding 116 exact IDs already exercised by the
integrated run. It completed 417 passes and one failure, zero errors/skips, in
78.247 seconds (78.617 seconds wrapper, exit 1, no timeout). The failure is the
same-UID memory-isolation test's positive-control `process_vm_readv`, before
`protect_runtime()` or its protected-read check executes. Minimal self/direct-child
probes returned EPERM (1) in restricted mode and ENOSYS (38) in the original
authorized/escalated environment. The latter retains UID/EUID 0, dumpable 1 and
verified direct ancestry/start-time/namespace observations; the Yama query returns
ENOENT. Positive-control capability is unavailable here; the exact platform
mechanism remains unknown. No product isolation defect, privacy-protection pass,
skipped test or pass conversion is inferred. The original failure did not retain
errno or the complete child identity; later probe records are separate observations,
not values retroactively assigned to that first failure. The initial
strict selection-name comparison failed before test execution; four generated
UUID-name differences and the corrected source-bound selection are retained.
These separate f59/699/253 sessions are not combined into a complete foundation
pass, and prior-candidate passes are not inherited.

Original native/installed-IDE bounded and sustained workloads must execute on
any promoted correction at its exact final identities. Local field-transfer,
native event-category and fixture-build/journal changes are integrated into
dev81; the repaired FakeStack observer remains a separate diagnostic tree.
All eleven release groups remain unqualified. No stable publication is claimed.

## Preserved historical measurements

The following source-bound measurements, failures and previously pending states
are retained as historical evidence; current outcomes are stated above.

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

# Dev75 measured ownership changes; full release unqualified

Parent executable: `8184bde25c58cb8b25a71fd794c38d3e3e1828d6` (dev73).
Paired IDE: `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`.

Actual dev73 allocation artifact12777243975 identifies repeated allocations in
`SPELLexecutorImpl::dispatch`, `getFullStack`, `getAvailableStack`,
`SPELLcif::notifyLine` and `SPELLserverCif::completeMessage`. These sampled paths
do not account for every growing byte or establish the cause of earlier exits.

Accepted procedure frames now borrow an exclusively owned filename copy for
their dispatch scope. Eight thread-local slots retain at most4KiB capacity
each after release; deeper nesting and oversized filenames use ordinary local
ownership. The immutable Python filename owner remains alive across nested
calls and GIL release. No borrowed reference leaves the dispatch scope.
Compiled original/corrected filters preserve all28 original cases and CPython
ownership checks.30,000 accepted dispatches allocate30,000 times before and
zero after warm-up. Added16-owner and100,000-byte controls preserve snapshots
past the cache capacity. These are component measurements, not native hours.

Callstack snapshots now copy under the original lock into caller-owned
storage. LINE notifications use eight exclusive scope-owned scratch slots with
ordinary local fallback. Existing duplicate suppression, recursive locking,
sequence/notification order, timestamp formatting and durable writer remain.
CSP metadata is assembled in the message's existing owned field. Original
public getters remain unchanged. A free adapter preserves the original
callstack interface layout and vtable and falls back to the original getters
for other implementations.

Compiled actual old/new native methods execute10,000 LINE and10,000 CSP calls.
Each path falls from30,000 allocations/1,580,000 bytes to zero after warm-up.
The entire10,004-record LINE outputs match,410,174 bytes each, SHA-256
`659f4c27f375b1100c5584cce7b7830990c0ac172b728dc1dab41645a9c56a8e`.
Metadata digests match. Empty/fallback, Unicode, duplicate, error-state,
recursive notification, maximum execution count, sixteen nested scratch owners,
oversized storage and eight concurrent scratch users execute. Transport and
audit sink adapters bound this component's scope; original native and durable
audit acceptance remain mandatory.

All153 affected local components pass, including existing dev73 audit and
callback exit/cancellation regressions. Later deeper-filename controls and
retained LINE measurement also pass; counts overlap. Initial harness compile,
path-collision and formatting failures remain retained. Original sanitizers,
deadlines, concurrency, workload, cgroup accounting, memory limits and required
audit records are unchanged. Retained buffer capacity remains measured; no
sanitizer retention is purged. Fresh hosted native/installed-IDE mandatory and
sustained acceptance must run at the exact dev74 source before qualification.

See [source-bound local receipt](evidence/measured-line-stack-corrections-20261027.json)
and [verified dev73 checkpoint](evidence/qualification-8184bde-20261027.json).
Both dev73 sanitizer hours remain failed, and all eleven release groups remain
open. No stable merge, tag, release or production migration has occurred.

Dev74 full native compilation failed through the interface boundary. Its logs
and unexecuted hour attempts remain retained. Dev75 adds actual interface
compilation and alternate-implementation fallback coverage;109 affected local
checks pass. No native runtime pass is inferred from these components.


## Dev82 integration — 2026-10-29 UTC

Exact executable16982c4dd698a937ce2ae4e37f4736055de9a2ce integrates dev81 plus native audit-generation identity fencing and bounded per-connection bridge-line reuse. The audit correction reproduces two historical-header races, then passes52 component checks. The bridge selection passes58 ASan/UBSan checks;10,000 short line reads fall from40,000 allocations/4,540,000 bytes to zero after component warm-up with unchanged digest. Counts overlap other suites and are not unique aggregate coverage. These do not establish whole-family sustained qualification.

GitHub writes recovered. Corrected observer47921d18/tree4d07383d is running in40828138175; results require complete collection. Fresh candidate CI, original45-second checks, sanitizer hours, ENOSPC and paired installed recovery remain pending. All eleven release groups remain false. Prior failure bodies and histories remain preserved. Current Qt6.10.3 attribution binds70/70 top libraries to exact upstream SDK bytes;12/230 Qt ELF files remain unbound and license/source/advisory review remains open. The qualification cluster and independent security reviewer remain unavailable.

Details: `evidence/qualification-dev82-integration-20261029.json`.
