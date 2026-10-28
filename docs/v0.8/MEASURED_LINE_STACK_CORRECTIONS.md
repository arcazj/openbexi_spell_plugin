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
