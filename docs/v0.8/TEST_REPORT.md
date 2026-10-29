<!-- BEGIN CURRENT DEV81 RECONCILIATION -->
# Current dev80 outcomes and local dev81 integration — release blocked

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

## Hosted outcomes at exact dev80 source

| Hosted run | Scope | Actual outcome |
| --- | --- | --- |
| [40770371656](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371656) | v0.8 services, authority and worker preflight | failure: 1 failure, 13 success |
| [40770371682](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371682) | v0.8 repeated native lifecycle evidence | success: 9 success |
| [40770371619](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371619) | v0.8 portable preparation and driver compatibility subset | success: 1 success |
| [40770371659](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371659) | v0.8 development Python supply chain inventory and known-vulnerability scan | success: 1 success |
| [40770371707](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371707) | v0.8 prelaunch multi-service Compose integration | success: 1 success |
| [40770371736](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371736) | v0.8 Kubernetes prelaunch static security gate | success: 1 success |
| [40770371744](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371744) | v0.8 native allocation site investigation (diagnostic only) | success: 1 success |
| [40770371746](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371746) | v0.8 kind five-process prelaunch runtime smoke | success: 1 success |
| [40770371786](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371786) | v0.8 durable native audit storage and disk-full failure | failure: 2 failure, 2 success |
| [40770371788](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40770371788) | v0.8 isolated memory comparisons (not release qualification) | failure: 7 failure, 4 success |

The portable subset has 241 passes, fault reproduction 95 and audit components
21. Counts overlap other suites and must not be summed as unique requirements.
Both optimized dev80 hour jobs have completed; their independently verified outcomes are recorded in the source-bound receipt and remain diagnostic-only.

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

## Foundation, event authority and targeted local implementation

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

Dev80 optimized handoff artifact `12856725049` failed before the recovery soak:
the original scheduler emitted WARNING with original `SCOPE_SYS=2`, which Context
rejected as invalid. The retained worker event is ordinal 261 and the later
terminal failure is ordinal 278. This is not a memory-growth outcome and does
not explain the earlier control-report denial. The local correction accepts
original PROC/SYS/CFG categories under the same execution, worker and controller
authority, keeps durable acknowledgement and unique event-receipt validation,
and still requires all 42 child-enabled lifecycle events. Its 84 focused and
115 overlay/release checks passed before integration; counts overlap the 306
integrated checks. Hosted native reruns remain outstanding.

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

## Compatibility, packaging and security

The fresh local-253 input reconciliation preserves all 763 requirements and
47 unchanged historical reports. Of 555 top-level bindings, 546 match and nine
drift. All 763 remain `NOT_FRESHLY_QUALIFIED`. Eleven previously unresolved
referenced byte identities were actually recovered and hash-verified: six exact
derived-source reconstructions, three immutable Git capture blobs and two exact
historical CRLF serializations. The historical gap falls from 57 to **46**;
historical report outcomes and current native statuses do not change. Matching
top-level inputs or recovered bytes is not fresh original native/driver execution.

The actual dev80 inventory collector `03bd8135b33920600389f03b6d5c3379c1d8e579`
examined SPELL `4c55321b…` / IDE `b1472b4d…` in image
`sha256:40edb5a579d392964599f76c5ca7fac35d829b9927f3d62c20cdf81c70100e45`
(run `40772154297`, artifact `12853840746`): 243 packages, 376 vulnerability
matches and 187 advisory IDs. Matches are not unique CVEs. This actual-byte
inventory remains separate from the older `57b4d64` diagnostic and its preserved
932 / 342 / 237 / 161 match counts.

The exact installed dev7 public-main offscreen and xcb probes entered the actual
Qt event loop and passed, without the old exact-title oracle. The 53 installed
regressions (44 original and nine added owned-process checks) and 89 component
checks passed. These are bounded installed subsets; full native debugger,
authenticated browser/WSS and Git acceptance remain open. Thirty-two recorded
dynamic dependency rows remain unreviewed; resolving the targeted startup
sonames is not a disposition of every delivered plugin/library.

Of 59 entries without recognized SPDX metadata, 52 have delivered Debian
notices and one has the delivered CPython license; six specific PE launcher
notice gaps remain proposed-only repairs. All 307 captured notice-byte bindings
were checked. Seventy actual Qt libraries are bound to the installed wheel/image,
but the wheel contains no corresponding SBOM/attribution members. Seven direct
PySide/Shiboken source-bound supplemental notices were verified separately.
Full Qt third-party coverage, corresponding source/source offer, legal
compatibility, vulnerability disposition and security acceptance remain open.

The local pip derivative `cbcada564d24a08b2667cc0ac1873bd6d3379b70`, tree
`89c37d20d88badb1545e700c32908c7568ef78f1`, has 101 component passes; the actual
derivative image has not executed and is not promoted. The local IDE dev8 / Qt
6.12.0 candidate `47f5a4c11e40d4f7c1885b8eaf5120abc3ead6b9`, tree
`510a28258b4ac03b850ae84df6ec235e65cb701b`, remains unpromoted because its original
graphics shutdown reproduces SIGBUS. Its completed original source suite collected
297 tests: 287 passed, one failed and nine explicitly skipped (eight unavailable
Docker-image prerequisites and one Windows-only case), in 381.722 seconds.
The original graphics child returned -7/SIGBUS. After JUnit and session-finish
exit status 1, pytest itself returned -6/SIGABRT with
`malloc_consolidate(): unaligned fastbin chunk detected` (383.162 seconds outer
elapsed). Both original failures and the unchanged source/test bindings are
retained. A separate allocation-observer failure is preserved and does not by
itself establish the exact original SIGBUS cause.
An isolated callback-lifetime diagnostic subsequently observed 19 SIGBUS and
one normal exit without its wrapper guard, versus 20 normal exits with positive
retain → original teardown return → release coverage. All 40 stdout byte hashes
matched and original Dashboard/Add point/parent-retention behavior was preserved.
The analogous exact-source dependency patch applies cleanly, but the full
dependency had not been rebuilt at that diagnostic stage. The subsequent genuine
target-library rebuild has its own byte identities and packaging limits below.
The interposer and its guarded
full-source suite are diagnostic only; they do not replace the original failure
or qualify a shipped dependency/package.
Its completed guarded source diagnostic records 297 tests: 288 passed, 0 failed, 0 errors and 9 unchanged skips in 375.697 seconds; outer process return code 0 remains part of that result.
Eight additional internal source-review diagnostic processes exercised 24
baseline/guard cycles, exception handling and reference balance. They are
analogue/interposer checks; they neither qualify the rebuilt dependency nor
replace the mandatory independent implemented-system security reviewer.

A genuine libpyside target rebuild followed from the exact official PySide6
6.12.0 source, using the original target CMakeLists, 22 original C++ units plus
generated MOC/resource units, and the Qt Core SDK library verified byte-identical
to the candidate wheel library. The first configure attempt failed on the Ninja
path; the second build failed on the SDK tool's ICU search path. Both unsuccessful
attempts are retained. The third baseline build and the corrected target build
completed with identical compiler commands. Other PySide binding modules, Qt
libraries and Shiboken were reused; this was not a rebuild of every dependency.
The actual target library changed from SHA-256
`3a5da08c5a660756836656875e9bb0c3098cbb1c5b02019e664689fa3b9f8734`
(418,720 bytes, rebuilt original source) to
`c477cd666a53952c15ea4d1b1d422dfc04a1ed5668087983e3eda502410af9e3`
(418,928 bytes, wrapper-lifetime correction). Original graphics examples run
against the rebuilt baseline recorded 17 SIGBUS, one SIGSEGV and two normal
exits; all 20 corrected-library executions exited normally. The separate matrix
retains 20 callback-lifetime executions and four public lifecycle/finalizer
processes for each library. These used actual mapped before/after libraries,
without `LD_PRELOAD`, and did not change the original fixtures.
A separate source/binary verification compared all 258 selected official source
files: 257 unchanged, with only the exact `pyside.cpp` correction. It checked all
5,183 SDK archive entries and 4,776 regular file payloads, 4,166 CMake and 12 Ninja
tool payloads, all 24 compiled units and 1,021 compiler-dependency paths, and the
original target/build commands. This is verification of the recorded target
rebuild and its support bytes, not the independent implemented-system security
review required for release.

The local derivative dependency wheel
`pyside6_essentials-6.12.0-1openbexi1-cp313-abi3-linux_x86_64.whl` is
84,379,401 bytes, SHA-256
`2acaf920512416cb49cda068f8ea9a9e0578c8415e1bea11b54f8b519d964b33`.
It retains 2,468 unchanged original payload members; the original library and
wheel-tag metadata changed, with an added correction notice, source patch and
build record, and a regenerated verified RECORD. The first pip invocation returned zero but performed
a same-version no-op, which is retained as an unsuccessful installation attempt.
The second installation used the prepared wheel in its isolated environment;
2,473 payload members and the actual mapped corrected-library SHA were verified,
with no `LD_PRELOAD` or `PYTHONPATH` dependency override. Support distributions
were reused, so this is not the complete joint clean-install acceptance.
The completed unchanged IDE source suite against the actually installed derivative records 297 tests: 288 passed, 0 failures, 0 errors and 9 explicit unchanged skips in 355.714 seconds. Its actual outer process returned 0 after 357.450055134 seconds; the original 1,200-second outer cap and per-case fixtures/deadlines remain unchanged. All original 297 node IDs and their order, all nine original skip reasons, 1,182 ordered journal records, source worktree cleanliness and all 2,473 installed payloads were reverified. The actual pytest PID/start-time and mapped corrected library are bound separately. Its PYTHONPATH contains only the reviewed evidence-journal directory, not a dependency override. This is local source-suite evidence at IDE 47f5a4c11e40d4f7c1885b8eaf5120abc3ead6b9, not complete joint installed-image or release qualification.

The subsequent genuine unmodified and corrected library builds have identical
exports/version requirements to each other and preserve every original non-weak
export, but their local build introduces `GLIBCXX_3.4.30` relative to the original
wheel's `GLIBCXX_3.4.29`. The retained official PyPA policy caps the original
`manylinux_2_34` tag at 3.4.29. Assertions remain enabled; an unpromoted derivative
must use a generic `linux_x86_64` tag with its explicit runtime requirement.
Four original weak exports are omitted by the rebuild; scanning 287 installed
candidate ELF files found no undefined use of those symbols, which is not a
complete ABI proof for external consumers. Portable policy-compliant rebuilding
and complete installed qualification remain outstanding.

The official QtBase 6.12 SDK's CDX has 212 components and its SPDX has 213
packages and 92 file records; all 92 file SHA-1 values match retained SDK bytes.
The separate unpromoted Qt6.12 wheel contains 243 Qt-tree shared objects (83
runtime libraries, 86 Qt plugins and 74 QML plugins), plus 26 binding/support
objects. Exact wheel/SDK/SPDX/CDX mapping covers 17 runtime libraries and 49 Qt
plugins, 66 of the 243 Qt-tree objects. The remaining 177 are outside that QtBase
subset; no QML or binding coverage is inferred. Neither SDK SBOM nor the 33
name-matched attribution/license candidates appears as an identical standalone
payload in that wheel; embedded resources were not searched. This bounded map
does not change the promoted dev80 Qt6.10.3 image's 70-library attribution gap or
disposition legal compatibility, advisories or source offers.
Neither inventory success, partial startup probes nor supplemental notices
qualify stable joint packaging. Current paired IDE remains dev7.

## Durable evidence and release boundaries

The last verified base at this source-record time is version 12 of
`openbexi-v08-qualification-evidence-20261027.zip`: 486,119,536 bytes, SHA-256
`aa8d2f3aa8d0112991f0722baeede60e844bd7656d4f4c58bc31ffe77891d2c4`, prefix
`session-history/20261028T214054Z/`, with 18 saved external volumes. New volumes
19–22 are also saved and verified: 1,031,728,950 bytes, 3,183 unique payload
members and 1,250 same-snapshot exact-content aliases. The final base append is
pending at this source-record time. `CURRENT_EVIDENCE_CHECKPOINT.json` at the
evidence archive root and its external saved-write receipt are authoritative for
the later completed checkpoint. A final archive's own digest cannot be embedded
in the payload it hashes. Version 9 and its three original volumes remain
historical checkpoints; no later records are silently claimed saved.

The complete local-253 source archive is 38,375,731 bytes, SHA-256
`6a5d000d43014fcdd51006f96cfad4e68e569be5b191e9b61f1619f484ac37f5`;
all 2,408 Git payload members, blob identities and executable/symlink modes were
verified. This is source-archive verification, not a stable package or shipped
system qualification.

The original IDE dev8 `47f5a4c11e40d4f7c1885b8eaf5120abc3ead6b9` build archive
(`source.tar`, 14,295,040 bytes, SHA-256
`195d4cb22e3365a1ce0abdb2bee560fab8870f147590fa20d565ddbd87fca5a5`)
has all 604 expected members and Git executable/symlink modes, but only 602 raw
Git-blob byte matches. `install.ps1` and `start.ps1` use their committed
`eol=crlf` checkout representation: respectively 1,451/1,975 archive bytes versus
1,422/1,936 Git-blob bytes. Both payloads equal the unchanged worktree, and
CRLF-to-LF comparison matches the corresponding Git blob; **raw byte equality
is false**. No test, example or Python runtime byte differs from Git. The
original archive and the failed raw-equality verifier are retained without
normalizing or replacing evidence.

A distinct recovery archive,
`qualification-source-ide-dev8-47f5a4c1-git-blobs.tar.gz`, is 8,332,780 bytes,
SHA-256 `953594b097130d5831774173d6e110b20d77507dd16971e7911bcc47e5ec96d9`.
All 604 raw Git blobs, modes and the complete member set were verified. This
later archive was not used for the completed original build or source suite;
it does not retroactively replace their recorded input representation or
qualify a release package.

Old failed builds, ineffective observers, incomplete tails,
failed queries and later Docker states remain preserved.

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

## Preserved historical checkpoints

Everything below this boundary is preserved historical evidence. Earlier wording
such as “current” or “still running” applies to its own recorded source and time;
the current-source reconciliation above supersedes those status summaries only.

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

# Verified predecessor exact-source checkpoint, 2026-10-27

Executable `892914f10f12bd9a3043a69e07f363a143445ec3` (`0.8.0.dev71`),
tested PR merge `0165d4ba44ec01dd014c2ccb0c1b4c558398c006`, identical tree
`2c8816f535d1ce86f69ffe78dbbd574b69f1f94f`, paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`.

- All 14 core jobs pass: 1,586 foundation tests, zero failures/errors/skips;
  the separate 95 fault tests overlap. The portable subset has 241 tests.
- Mandatory original-ASan/UBSan, no-swap, 45-second handoff / installed-IDE
  growth passes at 31,776,768 / 55,103,488 bytes against 67,108,864. Peaks are
  1,290,653,696 / 1,347,506,176 bytes. All 48 samples and 139 sources each verify.
- Actual rebuilt-native ENOSPC, all 17 audit components and independent
  extraction of the entire 8 MiB fault image pass. Sixteen core/audit artifacts
  verify 1,752 overlapping source bindings and 230 raw audit files.
- All nine repeated lifecycle jobs pass (72 startup families, three Listener
  attempts and three 16-case terminal matrices); 1,059 overlapping source
  bindings and 324 raw audit files verify. These passes do not explain old failures.
- All five ancillary workflows pass within their stated portable, prelaunch,
  static-manifest and development Python inventory scopes.

Both current original-sanitizer hour attempts fail early. Handoff observes
887.64 seconds, peak 2,147,495,936 bytes and one sampled OOM kill. IDE observes
736.11 seconds, peak 2,147,487,744 bytes; its last sample has zero OOM kills,
but later Docker state records `OOMKilled=true`. Neither observation is erased
or converted to a one-hour pass. Both earlier `3a970c45` sanitizer hours also fail.
Its two optimized diagnostic hours pass at 6.43 / 6.82 MiB growth while retaining
123,440,121 / 109,461,184 audit bytes. They do not replace mandatory acceptance.

Read-only sanitizer accounting at diagnostic commit `6055274d` reproduces
five-minute growth failure while showing substantial quarantine retention and
roughly 10 / 9 MiB live Context / Executor allocations. Byte-ranked allocation
paths are being measured before further optimization. Controlled durable-member
delay and completion reply loss terminate the affected family. The initial
prompt-denial diagnostic fails to inject because native sends DECLARE, not the
private OPEN schema; corrected diagnostic `d83e50c2` injects successfully and
terminates the affected worker while nine other families finish. It does not
reproduce the old hang. Reply loss after durable prompt registration is now
being measured at `d09bc75b`. The historical delayed-registration and separate
worker-exit causes remain open.

Evidence: [source-bound checkpoint](evidence/qualification-892914f-20261027.json)
and [sanitizer accounting](SANITIZER_MEMORY_ACCOUNTING.md). Every prior failure
and historical checkpoint below remains retained. All eleven full-release gates
remain false; nothing has been merged, tagged or published as stable v0.8.

# Historical Phase A/B test report

Date: 2026-10-22. Plugin baseline `109a47af47951e2fa54b60cb408a543b117f7f15`;
requirements base `76144fb704a8e3777209df04058c62d80bbc962f`;
IDE baseline `7585d221a58fcfe178b93046c691ad74a92148e9`.

| Check | Result | Evidence |
|---|---|---|
| Baseline API/refs/source/manual/deployment audit | Collected; public release metadata and healthy production verified | `evidence/baseline-audit.json` |
| IDE session/durable/procedure regressions | **37 passed**, 0 failed/skipped, warnings as errors | `evidence/baseline-regressions.xml` |
| Installed original-native-driver → binary DSS test | **1 passed**, actual 0.7.0 packages and exact native image | `evidence/native.xml`, `native.log` |
| Native process tree/socket trace | Listener, Context and Executor distinct PIDs observed | `evidence/native-trace.json` |
| Retained v0.7 qualification | Report hashes/inventories checked; full historical run not repeated | Existing `docs/V07_QUALIFICATION.json` and evidence |
| Baseline integrity | 109 retained report files and 225 installed package members match accepted hashes; original edits preserved | `evidence/review-integrity.json` |
| Architecture diagrams | Three editable DOT sources, PNG/SVG exports; repeat render bytes and checksums verified; images visually inspected | `diagrams/manifest.json`, `SHA256SUMS` |
| Hosted CI at baseline | **Absent**; 0 Actions/check/status records, aggregate pending | Baseline audit API results |
| Independent architecture/security review | **Pending** | `ARCHITECTURE_REVIEW.md` |
| v0.8 mandatory runtime/browser/Compose/K8s/security gates | **Not run** | `ACCEPTANCE_PLAN.md` |

Commands executed (PowerShell; use CPython 3.13 with pytest 8.4.2):

```powershell
# Plugin worktree; pypdf is an audit-only dependency.
& C:/projects/openbexi_spell_plugin/.venv/Scripts/python.exe -X utf8 scripts/audit_v08_baseline.py --ide C:/projects/openbexi_ide --original C:/projects/openbexi_spell_plugin --output .qualification/v08-baseline
# IDE baseline worktree; imports its frozen source through the existing fixture.
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& ./.venv/Scripts/python.exe -I -m pytest tests/test_sessions.py tests/test_durable_sessions.py tests/test_procedure_service.py -q -W error --junitxml=C:/obspell_v08/.qualification/v08-baseline-regressions.xml
# Plugin worktree; executes the already-retained, composition-adapted installed oracle.
& C:/projects/openbexi_ide/.venv/Scripts/python.exe -I scripts/trace_v07_baseline.py --installed-tests C:/obspell_v07/.qualification/v07-installed-fenced --output .qualification/v08-native-baseline
```

The trace harness records the exact retained oracle SHA-256, installed package
versions, test command, image, process IDs and socket tables. It does not repeat
fresh browser interaction or claim external DSS runs in a separate process in
that test: the acceptance fixture hosts DSS in its test process. Independent
deployed DSS lifecycle is a required v0.8 gate.

The v0.7 browser/Qt evidence and source complete the as-is UI call-path audit.
The fresh native test adds a current execution/driver trace. No failed tests
were reclassified and no v0.8 acceptance result is inferred from them.

The original checkpoint above preceded G1 review and implementation. It is
retained as historical evidence; G1 was subsequently reviewed and approved.

# Historical initial C/D foundation qualification

The owner authorized the G1 review resolutions and staged implementation with
"Approved , move forward". The original Phase A/B evidence above remains
historical evidence at its stated identities.

New implementation: standalone `server/`, version `0.8.0.dev1`; no change to
published v0.7 runtime packages or entry points. The service has no execution,
worker, driver, ownership transfer, browser session or WSS route.

Local CPython **3.13.16**, OpenSSL **3.5.9**: **51 passed**, zero errors, failures
or skips, with warnings as errors. Lint, formatting and mypy pass. Real TLS
sockets cover pinned service roles, forged identity/Origin/Host, independent
Context permissions, authorization before idempotency replay, malformed input,
Context isolation and concurrent writes. Separate real processes cover Listener
crash/restart, Context crash/restart, durable data and new incarnation.
A 100-request CAS race produces one revision winner and 99 conflicts.

`uv build server --python .venv/bin/python` built wheel and source distribution.
The wheel was installed without dependencies and its CLI executed successfully
with `python -I -m openbexi_spell_server --help`. Nothing was published.

Evidence: [result](evidence/server-foundation/result.json),
[JUnit](evidence/server-foundation/tests.xml),
[process trace](evidence/server-foundation/process-trace.json),
[development attempts](evidence/server-foundation/development-attempts.json) and
[package hashes](evidence/server-foundation/package-build.json). Four failed
development attempts are retained as compressed original JUnit files; they
were fixed/retested and are not relabeled as passes. The final report records
input hashes and a dirty working tree; it is local source-hash evidence, not an
assertion that the preexisting HEAD was the tested implementation commit.

Reproduce with `.venv/bin/python scripts/qualify_v08_server.py`; each invocation
retains a fresh output directory. The new pinned-action GitHub workflow runs
these foundation checks and package smoke on the candidate SHA and uploads
evidence, including failures. Hosted results must be read from the actual PR
checks; a local pass does not establish a hosted pass.

G1: approved for staged implementation under F1-F10. Initial C/D foundation
checks: PASS within the scope above. Full C/D integration: PENDING. E-L native
execution/ownership/driver/browser/Compose/Kubernetes/security/release gates:
PENDING, not inferred from 51 foundation tests. No native Executor test, Docker
deployment or Kubernetes cluster test was performed in this implementation run.


# Historical dev2 services and prelaunch authority qualification

Package `0.8.0.dev2` adds the bounded registry and ownership protocol described
in [EXECUTION_AUTHORITY.md](EXECUTION_AUTHORITY.md). Native execution remains
explicitly disabled. This supersedes the earlier foundation-only description,
while preserving that checkpoint's original results.

Local CPython **3.13.16**, OpenSSL **3.5.9**: **106 passed**, zero errors,
failures or skips, warnings as errors. Ruff lint/format and mypy pass. Exact
SHA-256s of **21** qualification inputs match the tested local files. The report
records parent HEAD `925ad0d` and a dirty working tree; these are source-hash
results, not a claim that the parent commit contained the new implementation.
Candidate hosted checks must independently run on the actual pushed SHA.

Evidence: [result](evidence/execution-authority/result.json),
[JUnit](evidence/execution-authority/tests.xml),
[real process trace](evidence/execution-authority/process-trace.json),
[development attempt](evidence/execution-authority/development-attempts.json),
[package build](evidence/execution-authority/package-build.json) and
[compatibility scope](evidence/execution-authority/compatibility-scope.json).

The added tests cover 100 concurrent logical reservations with one winner,
100 consumptions of one immutable start grant with one winner, ten distinct
single-use registry slots, same logical ID in two Contexts, simultaneous claims
and accepts, transfer of B while A/C remain unchanged, forged proofs, revocation,
expiry/rejection/cancellation, response-loss replay, private capability delivery,
rebind/late disconnect, bounded admission waits, audit rollback and SQLite failure.
Start/accept races cannot produce an accepted new owner plus old-origin start.
A deliberately delayed grant remains invalid after transfer and new-owner rebind.
Post-consumption transfer returns BLOCKED and retains the old owner and holds.

A real subprocess dies immediately after start-consumption commit; reopening
state fences the original grant and refuses replacement. Separate real service
processes demonstrate that Listener death/restart preserves Context ownership,
while Context death/restart advances its epoch, retains its procedure hold and
leaves the other Context's epoch unchanged. The credential-free trace records
those service processes. It does **not** record native Executor processes.

The initial 34-test authority development attempt retained one failure: a test
expected `controller_fenced` after an already closed connection, while the
correct denial was `connection_denied`. Its original compressed JUnit is retained;
the denial remains enforced. Manual design review also caught an epoch-restamping
hazard: issuance moved to original controller admission, and the new delayed-grant
regression passed. Neither observation is reclassified as a passed original run.

Wheel and sdist build passed; the isolated installed wheel CLI smoke passed.
All seven wheel source members match the checked files, licensing and source
tests are included, and no private keys are packaged. Nothing was published.
Original v0.7 runtime paths remain unchanged from the requirements base; the
37 historical baseline regressions and native/DSS test were not repeated here.
That integrity check is not a new full compatibility qualification.

**G2/E and G3/F remain pending.** These are authority protocol, actual TLS and
service-process tests. They do not launch a native worker, authenticate a worker
certificate/Pod UID, verify actual source inventory/aliases, pause descendants,
settle driver writes, exercise browser/WSS or deploy Compose/Kubernetes. No
native pause, external-effect recovery, production storage fencing, automatic
reuse, full security scan or release gate is inferred from these passes.


# Current dev3 source and worker-preflight qualification

Package `0.8.0.dev3`: **143 local CPython 3.13.16 tests pass**, zero failures,
errors or skips, warnings as errors. Ruff lint/format and mypy pass.
WORKER_PREFLIGHT.md defines the exact configured profile and limits.

New tests verify exact Git commit/tree/blob hashes, ignore working-tree changes
and replace refs, normalize approved aliases, reject unapproved metadata, and
reject unsafe or mismatched source inventories. Actual mTLS sockets and a
separate worker-preflight CLI process test role/scope/assignment checks and
source digest verification without importing or executing procedure code.
Expiry, forged receipts, rebind/transfer, Context restart, replay, capacity and
audit rollback are covered. Expired preflight at consumption rolls back the
spent flag and preserves the hold. Unsupported Kubernetes identity and
ambiguous worker/Listener roles fail startup.

Evidence: `evidence/worker-preflight/result.json`, `tests.xml`, service and
worker-preflight traces, package/source hashes and the retained failed development
attempt. The initial new-source run had one fixture failure because `git add .`
removed a staged, absent submodule before the test commit. The fixture now
commits the staged gitlink directly; the source rejection remains enforced.
Intermediate lint findings about unused/imported fixtures were corrected.

The source-hash result records the parent HEAD plus dirty local state; candidate
hosted checks must independently run on the resulting pushed SHA. The scoped
workflow also builds the wheel and smokes both service and preflight CLIs.

**Runtime remains disabled.** The worker reports a digest using a registered
credential; it is not binary/image/hardware attestation. Read-only mounts,
Kubernetes Pod UID/admission, native execution/pause/descendants, final source
immutability at launch, driver actual-send/settlement, browsers and deployments
remain unqualified. Docker is unavailable on this local execution host. No
native Executor or deployment result is inferred from the preflight PID.
Original v0.7 runtime files remain unchanged; its historical baseline/native
evidence is retained and was not rerun in this increment. No merge or release.

# Disconnect barrier qualification — 2026-10-23

Development package `0.8.0.dev4`: **148 tests passed**, zero failures/errors/skips,
warnings as errors; lint, formatting and mypy passed. Exact source hashes,
commands and JUnit are in `evidence/disconnect-barrier/`. Earlier checkpoints
above retain their original scope and identities.

The new tests exercise a held execution mutex during close, durable CLOSING
after timeout, admission denial, unrelated database progress, original-key
retry, live permission revocation, rebind preservation, restart recovery and
schema-version preservation when worker preflight initializes. A development
test initially used an unsupported ContextStore context manager; its fixture
was corrected to use explicit closing before the final qualification.

No actual driver write or native Executor was run by these checks. The barrier
orders future bounded writes; native quiescence, effect settlement, deployment
and full compatibility gates remain pending. Package schema 4 intentionally
rejects downgrade to older binaries.

# IDE/gateway pair qualification

Server package `0.8.0.dev5`, paired IDE `1.2.1.dev1` at the exact commit in
`IDE_PAIR.json`: **152 local tests pass**, zero failures/errors/skips, warnings
as errors; lint/format/mypy pass. Source hashes and installed IDE source hashes
are retained in `evidence/ide-pair/`. Four new real-boundary checks use actual
IDE clients and the Qt panel over the certificate gateway, Listener and Context:
three separate user certificates, 20 observer reads, denied observer mutations,
explicit handoff, original-key replay, stale owner denial, rebind/late disconnect,
forged headers, direct internal-role denial and live role revocation.

The companion IDE retains its separate 11 passing client/Qt tests and the failed
local legacy baseline (21 passed, 16 failed) caused by PID/procfs namespace
mismatch. Hosted full-IDE checks must be read on their actual SHA; no local
compatibility pass is inferred. First hosted setup failed on missing libEGL;
the workflow now installs the Qt runtime and retains startup logs.

A new hosted diagnostic verifies frozen v0.7 image/archive bytes and probes real
native process startup/execution in an isolated non-root container. Its actual
outcome must be read from CI; it is not v0.8 native launch, effect settlement,
descendant pause or Compose/Kubernetes qualification. All full runtime gates
remain pending and `runtime_enabled` remains false.

## Final paired GUI/concurrency increment

**154 local tests pass**, zero failures/errors/skips, with lint/format/mypy
passing. `IDE_PAIR.json` pins the final companion source including GUI shutdown
and local-execution-fallback guards. `evidence/ide-pair-final/` retains exact
source hashes, installed IDE module hashes, JUnit and process traces. A real
100-request TLS reservation race across eight independent clients produces one
winner and 99 conflicts. Three actual Qt panels (captured in `evidence/ide-pair-final/ide-three-panels.png`) complete reserve → request →
accept → rebind → observer refresh → disconnect. Fourteen companion IDE client
and GUI tests pass locally, including nonblocking shutdown and rejection of
local Run/Debug while connected to the server.

The expanded IDE hosted run at `74335a1` passed **232 tests**, with one explicit
Windows-only Job ownership skip on Linux: SDK and DSS examples were installed,
and all eight existing immutable-image Docker execution tests ran. Both PR and
push workflows passed (`39908884967`, `39908880908`). Earlier `ab44417` hosted
results had 218 passes and 15 skips; those skips are not counted as passes.
The latest GUI guard candidate must run its own hosted checks.

The frozen native boundary diagnostic passed in hosted PR run `39908551614`.
The verified downloaded artifact and origin metadata are retained under
`evidence/native-boundary/`. It observed SPELL-Listener PID 9, SPELL-Context PID
26 and SPELL-Executor_v3 PID 74 in the container, with PAUSED → FINISHED.
These are real native PIDs, independently observed from registry/preflight PIDs.
The original v0.7 image is identified by its exact archive/image hashes.
No v0.8 native worker launch or driver settlement is inferred from that result.

# Portable legacy compatibility subset and full-suite diagnostic

Latest companion IDE `a1ec00f`: **235 hosted tests pass**, with one Windows-only
Job ownership test skipped on Linux; both PR `39909450551` and push
`39909445313` pass. This includes all 14 new client/Qt tests, companion SDK/DSS
examples and the eight existing offline Python Docker execution tests. The
paired server candidate `3fd050f` passed both hosted workflows (`39909811358`,
`39909806537`), including all 154 scoped checks and frozen native diagnostic.

A broader local plugin diagnostic initially collected 916 cases with 23 import
errors because grpc/protobuf were absent. After installing their pinned
versions, the full historical root suite recorded **744 passed, 227 failed and
271 errors**. This is a failed diagnostic, not a compatibility pass. Of those
failures/errors, 336 were missing historical Windows capture files, 141 were
composed test-module relative-import warnings, two were missing pypdf, 17
concerned the legacy token-preparation helper and two rejected stale source
identity assertions. Original compressed JUnit/logs are retained in
`evidence/compatibility-diagnostics/`.

The published v0.7 raw archive was downloaded and its exact 217,653,956-byte
size and SHA-256 verified. Its manifest describes 7,838 files. Those are later
v0.7 captures; this does not supply every earlier absolute Windows capture
referenced by historical development tests. No report was rewritten, source
hash restamped, missing capture fabricated or failure relabeled. The full root
suite has not been qualified for the current candidate. G4 remains pending.

Portable fixes: package-relative imports in composed fixture modules now have
their actual package metadata; the GPL legacy `<>` helper also handles adjacent
`<`/`>` operator tokens without changing whitespace, strings, comments, encoding
or line positions. This helper is still preparation-only, not a newly integrated
native compiler. Actual native grammar qualification remains separate.

The first portable run had 191 passes and two resource-warning errors. Follow-up
fixed real read-only viewer connection cleanup, closed recorder connections and
released HTTP error responses. A direct regression proves the viewer closes
SQLite on both success and failed namespace lookup. No warning filter was added.

Final local portable subset: **241 tests passed**, zero failures/errors/skips,
with warnings as errors, including actual original protobuf dispatch and binary
DSS TCP exchanges. Exact commands, tool versions and source hashes are in
`evidence/portable-compatibility/`. The separate hosted compatibility workflow
runs this explicit subset; it must not be presented as all 763 requirements,
a native worker/DSS-process test or v0.8 actual-send fencing qualification.
Published v0.7 artifacts remain unchanged; source fixes are unreleased and need
their own future wheel/image build and native acceptance before publication.

## Private actual-send boundary, development candidate 0.8.0.dev6

The current local service/paired-IDE suite passes **179 tests**, zero failures,
errors or skips, with warnings as errors. Ruff formatting/lint and mypy pass.
The 25 new boundary cases use the actual GPL fenced transport and independent
DSS processes. Five-stage receipts, ten concurrent driver operations, another
execution's progress during receipt waiting, stale/forged provenance, wire
identity binding, role revocation, capacity/endpoint denial, handoff while a
receipt is pending, real backpressured writes, lost release receipts and process
death between an actual TCP write and the SENT commit are covered.

`DRIVER_WRITE_GATE.md` defines this private trusted-Context seam. Final live
admission and the bounded actual socket write share the execution mutex used by
controller changes. Short authority and separate driver ledger commits precede
the write. Receipt waits hold neither execution nor database mutex. Missing or
uncertain effects retain recovery holds; no replay or synthetic receipt exists.
Start admission and consumption now both require live `execution:start` as well
as control permission. Creating the gate upgrades authority storage to schema 5;
older binaries reject that state.

The first compatibility attempt caught three strict telemetry-preimage errors
when the original transport source was edited (238 passed, 3 setup errors).
Those diagnostics are retained. The fix preserves the original `transport.py`
byte-for-byte and implements the mandatory-admission variant in the separate
GPL `fenced_transport.py`; no immutable patch recipe hash was changed. Final
portable compatibility rerun: **241 passed**, zero failures/errors/skips, with
warnings as errors. It still does not cover the full historical root suite.

The server development wheel builds and passes isolated installed import,
package-version consistency and CLI checks. Evidence, source hashes, commands,
JUnit, DSS PIDs, failed compatibility diagnostic and wheel digest are retained
in `evidence/driver-write-gate/`. Local reports identify the prior Git head plus
exact changed source hashes; hosted candidate-SHA checks must be assessed
separately. The companion IDE remains pinned to `a1ec00f` by IDE_PAIR.json and
its actual three-panel integration is included in the 179 tests.

**Full v0.8 remains unqualified and `runtime_enabled: false`.** No native worker
or service route invokes this seam yet. Ten driver operations are not ten native
Executors. Full native driver lifecycle/TM/resource ACLs, native child admission,
quiescence and handoff, all-763 compatibility, browser/WSS, real Compose and
Kubernetes admission/network/storage/failure recovery, independent security
review and release acceptance remain pending. No tag/release/merge follows from
these results.

## Retained native compute and Context event driver, 0.8.0.dev8

Hosted push **d962268** and its PR workflow passed the first actual v0.8 retained
native launch cohort. Ten distinct approved procedures consumed their original
grants over real mTLS and ran simultaneously in ten separate read-only,
non-root, single-use containers. Host Docker inventory verified thirty distinct
live native Listener/Context/Executor PIDs. All ten procedures finished and all
containers terminated. Twenty real EV lifecycle calls were committed to Context
before driver acknowledgement. Ten spent slots and ten logical reservations
remained held. Worker-to-worker native-port and external TCP denial passed;
Context had no Docker socket or host manager. The positive handoff check occurred
after container termination and remained BLOCKED with old ownership/epoch.

The server/source/IDE/driver/launch suite passed **217 tests** locally and hosted
at this code checkpoint, with zero failures/errors/skips and warnings as errors;
lint/format/mypy and installed development-wheel checks passed. The **241-test**
portable compatibility PR workflow passed on the same candidate. The redacted counts, public source hashes and workflow references are in
`evidence/native-retained-launch/qualification-summary.json`. Detailed logs,
process observations and original failures remain in their existing CI runs.

Earlier completion tests correctly failed on real EV calls. Original native
controller code emits start/finish events even for arithmetic-only procedures;
removing printing alone was insufficient. The final implementation parses the
original event protobuf in the GPL agent, forwards it over pinned mTLS, and
acknowledges only after Context's atomic, original-grant-authorized journal
commit. Non-procedure scopes, changed replays, fenced owners, unknown bindings
and full audit storage are denied. Other native driver calls remain denied.
Schema 6 prevents old-binary downgrade and is preserved by the socket driver
gate. Audit text never serves as a quiescence or release proof.

A later check adds a physical worker clone using the same certificate,
incarnation and spent original grant; final candidate CI must verify rejection
before native startup. The final suite also adds a concurrent native event vs
handoff regression and a per-execution event bound. These additions do not
retroactively change the d962268 artifact's scope.

**Full v0.8 is still unfinished and unqualified.** This is retained compute plus
scoped audit logging, not native TC/TM, safe cooperative pause/handoff, child
admission, worker reclamation/recovery, native IDE Run/Debug, browser/WSS, all 763
requirements, production Compose/Kubernetes or independent security/release
acceptance. The companion IDE remains pinned to a1ec00f and its existing
prelaunch control/panel integration is exercised by the service suite. No
release/tag/merge is authorized by these subset results.

Final native-code checkpoint **c8b286c** passed hosted PR and push services/native
workflows, including **218 scoped tests** and wheel smoke. Its native cohort
also started a physical clone with an original worker certificate, incarnation
and spent grant; it was rejected before opening a native session. Ten positive
workers, thirty native PIDs, twenty durable lifecycle events and all retained
holds were verified again. The same-code PR compatibility subset passed **241
tests**. The redacted summary now identifies this checkpoint; detailed CI
artifacts are not republished in the repository. Full qualification remains false.

# dev9 Context-owned original TC/TM boundary

The optional GPL host and route contract are documented in NATIVE_DSS.md.
The standalone Apache server and default gateway/Listener/IDE retain their
execution-disabled defaults. The worker forwards original protobuf bytes under
the original consumed grant; Context selects the endpoint, resource allowlist,
wire identities and non-replayable operation UUID. Schema 7 protects the new
bounded call ledger against older binaries.

Fresh local CPython **3.13.16** qualification passed **246 scoped tests**, with
zero failures, errors or skips and warnings as errors. Ruff lint/format and mypy
passed. The real mTLS/original-protobuf/independent-DSS subset adds 28 tests:
one real TC has five correlated ACKED receipts; twenty duplicate RPCs have one
winner; other original driver methods and wrong certificates/grants/resources
are denied; transfer between stages blocks the next write; a lost RELEASE
receipt retains uncertainty and ownership holds and cannot be replayed; bounded
call capacity is reserved before any wire effect. Telemetry uses original
CreateTmItem/RefreshItem messages and the existing packet/catalog validation.

The unchanged portable compatibility subset also passed **241 tests**, with
zero failures/errors/skips and warnings as errors. An offline wheel build with
the pinned build backend and clean isolated installed-wheel version/import
check passed for **0.8.0.dev9**. No existing environment was modified to install
the wheel. An initial test fixture used the wrong generated protobuf class and
one fixture import triggered lint; both failed diagnostics are retained in the
local development log and are not counted as passes. The first packaging
command found no pip in the shared uv environment; the wheel was instead built
from the offline uv cache and installed in a new isolated environment.

The hosted native matrix now keeps audit-only compute and adds a separate
`--native-dss` cohort. The latter requires ten real native SendCommand calls,
original RefreshItem calls, ten retained native workers and fifty durable TC
stage receipts, using a separate internal-network DSS container. **This new
native profile is NOT RUN locally:** Docker/Kubernetes tools are unavailable in
this workspace. Its candidate-SHA CI result must pass before claiming native
TC/TM qualification. It does not close native quiescence/live transfer, children,
recovery, IDE execution, full historical compatibility, browser/WSS, production
Compose/Kubernetes or independent security/release acceptance.


## dev10 single-consumer proof and native fixture correction

The dev9 PR services/native run 39999917882 completed: foundation,
native-boundary and audit-only launch passed, but the new native DSS job failed.
Artifact 12520924294 retained all ten worker failures, each `NameError: name
'Send' is not defined`; the procedure fixture lacked `from spell.lang import *`.
The dev10 fixture adds the SDK import. This is a corrected cause, not yet a
native pass.

A separate adversarial probe against dev9 confirmed a more serious defect:
a second process holding a copied ORIGINAL certificate and start configuration
could skip consumption and call the newly added driver route successfully
(HTTP 200 where 403 was required). The pre-fix failing JUnit is retained as
`original-config-probe-before-fix.xml` in local qualification evidence. The
honest clone's failed consumption was insufficient proof against direct RPC.

Dev10 atomically commits a hash of a new random 256-bit runtime proof with the
single successful consumption. Only that consumer receives the plaintext;
the native agent retains it in memory, never in the original configuration,
logs or a replayable response. All check/event/driver requests now require
this proof plus the unchanged original grant, certificate assignment and live
authority. A lost receipt cannot be refreshed; slots and reservations remain
retained. Schema 8 rejects unsafe old-binary access. Retained launch uses
`openbexi.worker/2`; preflight stays on version 1. This does not attest worker
memory or admit untrusted procedure code.

Fresh CPython **3.13.16** qualification passed **254 scoped tests**, zero
failures/errors/skips, warnings as errors; lint/format/mypy passed. New checks
cover copied configuration, missing/malformed/guessed proofs, lost-proof denial
and retention, atomic rollback on failed audit commit, and absence of plaintext
proofs in both effect databases. The first focused run exposed one stale
schema-6 expectation (now schema 8); that failure is retained separately.
Evidence: local `v08-server/run-20261023T181302Z-64733ab3`, with exact changed
code hashes. The README/protocol documentation was updated during that run;
no tested code changed after capture. Candidate-SHA CI must independently
qualify the committed source and documentation.

An offline **0.8.0.dev10** wheel build and clean isolated installed-wheel
version/import plus both service/worker CLI smokes passed. The existing dev9
**241-test portable compatibility** pass still applies to the unchanged legacy
code; it is not all-763 qualification. Hosted dev10 audit/DSS cohorts are
pending. The DSS cohort additionally requires a separate physical process with
only copied original credentials/configuration to receive HTTP 403 on direct
driver RPC. It must still prove ten commands, telemetry and fifty ACKED stages.

Full v0.8 remains **unqualified**, with public runtime disabled. Native
quiescence/live transfer, children, recovery/reclamation, full compatibility,
IDE/browser execution, deployment and independent security/release acceptance
remain open. No merge, tag or release is authorized by these subset results.


## dev11 native-client route integration

The dev10 hosted PR run 40001929895 passed foundation (254 tests) and
native-boundary. Both actual launch cohorts failed before native-ready:
`Route.call` rejected the protocol-2 launch as an unconfigured route. Direct
HTTP tests had covered the new server protocol but not the agent's real
client allowlist. Artifacts 12523245135 (audit) and 12522007581 (DSS) retain
the original failures. This is not an application procedure failure or a pass
for the corrected dev9 fixture.

Dev11 updates the explicit client allowlist to protocol 2 for consume/check/
event/driver, leaving challenge/verify at version 1. The physical clone probe
now asserts the transport's actual `Fault.status`, not an HTTPError cause. A
new real-client mTLS regression sends checks, events and an actual command,
proves direct driver use without the winner proof is denied, and rejects both
client-route and server-body launch downgrade. Its initial certificate-fixture
key error is retained in `client-v2-fix.xml`; the corrected focused test passed
in `client-v2-corrected.xml`. Full local and hosted qualification follow below.


Fresh dev11 CPython **3.13.16** qualification passed **255 scoped tests**, zero
failures/errors/skips and warnings as errors, with lint/format/mypy all passing.
Evidence: `v08-server/run-20261023T181847Z-b34d7eb0`; exact tested code hashes are
retained under prior head 2ba8743 plus local changes. Offline wheel build and
clean isolated installed **0.8.0.dev11** version/import and both CLI smokes
passed. The dev10 hosted 241-test compatibility job also passed. Native dev11
candidate-SHA results remain pending; full v0.8 stays unqualified.


### Native SDK fixture follow-up

At dev11 head cbb2abd, hosted PR run 40002594765 passed the audit-only native
cohort and native-boundary. The DSS cohort reached ten actual running native
Executors but again failed `NameError: Send`, with no denied driver methods
(artifact 12523475378). The earlier `from spell.lang import *` imported the
compatibility facade rather than the native function exports. Existing native
conformance fixtures explicitly use `spell.lang.functions`. The follow-up
changes the DSS procedure to `from spell.lang.functions import Send,GetTM`.
Server package/runtime-proof logic is unchanged; the hosted native result is
still mandatory. All failed artifacts remain retained; no native TC/TM pass is
inferred from a syntactically valid fixture or from the audit-only cohort.


## dev12 original native command-catalog response

The e20357a hosted PR run 40003202950 passed the audit-only native cohort and
native-boundary. The DSS cohort then reached the actual native Send path and
failed `Invalid original command catalog response` in the installed proxy's
critical-command check, with no denied RPC method. Artifact 12523221760 retains
all ten original failures. Context's TC DatabaseLookup had omitted the original
`kind: COMMAND` discriminator that the composed native proxy requires.

Dev12 supplies this discriminator for an explicitly admitted single command.
The existing resource permission check still runs first; unknown/unlisted
commands and sequences remain denied. The new original-protobuf regression
checks the native catalog response's name/kind/critical/arguments and denies
CMD2 and SEQNAME. This is a response-contract correction, not expanded TC scope.
Local and hosted candidate results follow; no native pass is inferred yet.


Fresh dev12 CPython **3.13.16** qualification passed **256 scoped tests** with
zero failures/errors/skips and warnings as errors; lint, format and mypy passed.
Evidence: `v08-server/run-20261023T182835Z-2a5aba63` with source hashes under
prior head e20357a plus changed code. An offline **0.8.0.dev12** wheel build,
clean isolated version/import and both CLI smokes passed. The native candidate
must independently prove the corrected catalog contract through real Send;
full v0.8 remains unqualified and public runtime stays disabled.


### Physical copied-configuration probe validity

Review of the new physical probe found that its empty SendCommand payload
could independently receive resource-denied HTTP 403 if proof enforcement
regressed. The probe now serializes a valid original CMD1 CommandDesc with
the same original credential/configuration. CMD1 is explicitly permitted and
already used by the positive cohort, so a missing-consumer-proof denial can no
longer be confused with an unlisted command. A successful bypass would also
execute an eleventh command and violate the exact ten-command/fifty-stage
oracle. This is a qualification-strength correction; server logic is unchanged.
The unit/RPC copied-configuration regression already used a valid CMD1 and
retains its pre-fix HTTP-200 failure. The stronger physical probe still requires
its own hosted candidate-SHA result.


## dev13 neutral options from the composed native proxy

The 8887833 hosted PR run 40003950252 passed audit-only launch and native-
boundary, but the real SendCommand request was denied (artifact 12522339194).
Review of the frozen proxy composition in command_feature_patches.py and
command_catalog_patches.py confirms it always adds `ConfirmCritical: false`
after the native confirmation hook. Context's earlier timeout-only schema
rejected this legitimate native wire option.

Dev13 accepts only the neutral composed forms: ConfirmCritical/LoadOnly exactly
false, SendDelay numerically zero, and addInfo an empty dictionary, alongside
the existing positive timeout of at most three seconds. Actual critical commands
are still rejected at adapter startup; nonneutral options, delayed/scheduled or
load-only operations, nonempty metadata, unknown resources and other methods
remain denied before any effect intent. Tests require a real five-stage command
with these defaults and reject seven attempts to expand or mis-type them.
The native agent now logs only method/status/fixed error code on driver denial,
never a payload, grant or runtime proof. The valid physical clone probe remains
mandatory. Local and hosted results follow; full v0.8 remains unqualified.


Fresh dev13 CPython **3.13.16** qualification passed **264 scoped tests**, zero
failures/errors/skips and warnings as errors; lint/format/mypy passed. Evidence:
`v08-server/run-20261023T183448Z-9047e8b2`, with exact changed code hashes under
prior head 2aa20a1. Offline wheel build and clean isolated installed dev13
version/import and both CLI smokes passed. The native harness was subsequently
strengthened to compare all fifty ordered receipt rows across the independent
Context and driver databases, require nonempty receipt hashes, and report only
a digest/count and equality result. This harness change still needs hosted
validation; no additional native pass is claimed from the local suite.


## Confirmed hosted dev13 retained native TC/TM subset

Code **14ddf3df7956f2462a915072f5341488789b6842**, PR checkout merge
**21b409e469f8353fab8abf1ebe890382f161d58d**:
[services/native run 40004938954](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40004938954)
passed all four jobs. Foundation passed **264 scoped tests**, zero failures,
errors or skips, and built/installed/smoked the dev13 package. Native-boundary
and the audit-only cohort passed separately.

Native DSS artifact **12524290803**, ZIP SHA-256
`5e53a10d80b8b993ab4da84765d7d8175a8f2b7129de9b86a3e55ef5b95c3a3e`,
was downloaded, CRC-checked and inspected. All **81 source hashes** matched the
candidate checkout. It proves ten completed and terminated native workers,
thirty distinct running native Listener/Context/Executor PIDs, ten original
SendCommand and ten RefreshItem calls, twenty durable native lifecycle events,
and **fifty identical ACKED effect rows in each separate database**, including
nonempty receipt hashes. The valid-command copied-original-configuration probe
was denied, as was the honest spent-grant clone. Command count stayed exactly
ten, with ten logical holds and spent slots retained. Worker cross-peer native
port and external TCP denial passed; Context had no host manager/Docker socket.

The durable redacted receipt is
`evidence/native-context-dss/qualification-summary.json`. Raw operational
archives and credentials are not republished. This closes the retained positive
native TC/TM and direct copied-config subset only. Handoff remained BLOCKED
**after termination** with the original owner preserved; quiescence/live
handoff is NOT qualified. Full native fault/reconnect/child/recovery semantics,
all-763 compatibility, IDE/browser execution, production deployment, independent
security/SBOM/vulnerability and release acceptance remain open. Full v0.8 is
unfinished/unqualified and public runtime remains disabled.


The same code commit's
[portable compatibility run 40004938969](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40004938969)
also passed **241 tests**, zero failures/errors/skips and warnings as errors.
Both PR workflows completed successfully. This is the named portable subset,
not qualification of all 763 inherited requirements.


## dev14 durable fenced native pause probe

The next increment implements NATIVE_PAUSE.md: explicit opt-in Context-owned
barriers fence original-grant effect admission under the existing per-execution
mutex and commit a PAUSING decision without waiting for a worker. Only the
certificate-bound consumption winner can poll/report under the unchanged
original grant and memory-only proof. This safety channel can report after
controller revocation but cannot admit effects or grant authority. Unknown,
expired, restarted and status-only barriers preserve owner/epoch and every hold.
No report can assert qualified family quiescence; effective native handoff and
resumption remain unavailable.

The new real-mTLS/independent-DSS checks exercise fencing, a between-stage pause,
forged/invalid proofs, original binding and worker identity, role revocation,
expiry/dead worker, late report, concurrent accepts, lost/changed report replies,
audit rollback, restart and plaintext-secret absence. Agent checks reject family
proof inferred from main PAUSED and prevent repeating an admitted pause after
lost diagnostic delivery. The first focused attempt exposed the Context worker
route classifier still treating the new routes as preflight (404); the classifier
was fixed. One restart fixture used a nonexistent path attribute and was fixed.
The first full 289-test run also detected changed live-session error precedence
from grant-validation refactoring; existing effect-path precedence was restored.
Those failed JUnit records remain in local qualification evidence. The corrected
289-test run passed with zero failures/errors/skips; the final lost-reply case
is included in the subsequent candidate run below.

The separate hosted `--native-pause-probe` cohort must demonstrate the actual
native boundary: main B paused while its background thread counter still
advances, nine unrelated procedures complete, no owner/epoch changes, all holds
retained, bounded controller latency and explicit independent host teardown of B.
It is a negative safety qualification and never marks native_pause_qualified or
full_v08_qualified true. No native outcome is claimed before candidate-SHA CI.


Final local CPython **3.13.16** candidate qualification passed **290 scoped
tests**, zero failures/errors/skips, warnings as errors, with lint/format/mypy
passing. Evidence: `v08-server/run-20261023T191649Z-51403d96`, prior head ead1a5d
plus exact changed source hashes. This includes the lost-pause-report regression:
response loss reuses the recorded diagnostic without another native pause.
Offline wheel build and clean isolated installed **0.8.0.dev14** import/version
and both service/preflight CLI smokes passed. Hosted candidate-SHA audit, DSS and
new pause-probe outcomes remain pending; native family quiescence/live handoff
and full v0.8 remain unqualified.


## Confirmed hosted dev14 native pause negative boundary

Code **34f201da11318850e8fbe3aac5ee17e6ff403371**, PR merge checkout
**854955fcb447e4a59484bc4a5fe39ffa2208d9d4**:
[services/native run 40010794562](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794562)
passed all five jobs, including **290 scoped tests**, native-boundary, audit,
DSS and the new pause-probe cohort. The same code's
[portable compatibility run 40010794672](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794672)
passed **241 tests**, zero failures/errors/skips. Package build/install/CLI
smokes passed. All test attempts remain retained separately.

Artifact **12527050416**, ZIP SHA-256
`c02788c03babaf9a728a96da10bf4f2df774b2f849f2a59285654f40a6261bc3`,
was downloaded, CRC-checked and inspected. All **17 runtime source hashes**
matched the candidate. Ten real native procedures reached RUNNING, with thirty
distinct native Listener/Context/Executor PIDs. B's main Executor became
**PAUSED**, yet its background counter advanced **89 to 99**. The transfer
remained **UNPROVEN/BLOCKED**, preserving owner/epoch and all ten logical holds
and spent slots. Ten unrelated-controller reads had maximum observed latency
**0.01278221 seconds**. The other nine procedures finished and persisted their
start/finish lifecycle events; B persisted a start only (19 events total).
Independent host cleanup terminated B after evidence capture; it was neither
native completion nor runtime quiescence/reclamation.

The durable redacted receipt is
`evidence/native-pause-probe/qualification-summary.json`. This confirms that
main-status-only pause cannot authorize a live handoff and that the new Context
barrier fails closed without blocking other procedures. It does not fix the
native provider's missing whole-family barrier. The required correction is
native acknowledgment of participating threads/children plus control/prompt
queue draining, followed by explicit separately admitted new-owner resume
provenance. Positive native pause/handoff/resume, children, recovery and full
v0.8 remain unfinished/unqualified. Public runtime remains disabled.


## dev15 cooperative background Python component (candidate)

The opt-in thread component uses CPython 3.13 monitoring alongside the original
native debugger trace. It holds observed snapshot background threads at their
next monitored line, including late entrants. Bounded waits, original one-shot
identity/deadline, retained disappeared participants and monitoring failure do
not authorize resume or positive family proof. The original Context pause
contract stays unchanged. A new native matrix profile contrasts the original
counter-still-running negative probe with an acknowledged, stable-counter
component probe. Both must retain owner/epoch and all holds; nine unrelated
native procedures must finish. The published v0.7 image stays byte-identical;
only the explicit profile loads a candidate read-only host session/library.

Development attempts are retained in `.qualification/native-pause/`: the first
component run exposed test-snippet indentation (five failures/six passes), fixed
without weakening its real-thread assertions. The next run passed ten checks
and found this local environment denies AF_UNIX socket creation. The diagnostic
wire was implemented on private loopback TCP, consistent with the native helper
profile. All eleven real-CPython component checks then passed. Two worker-boundary
cases also verify that success or loss of this helper cannot promote the worker
report to whole-family quiescence. There is no helper resume action.

Offline dev15 wheel build, clean isolated import/version and both service and
preflight CLI smokes passed. Local scoped suite and candidate-SHA hosted outcomes
are recorded below once verified. Until then native thread integration is
pending; full family pause/handoff/resume and full v0.8 remain unqualified.

The first full local candidate run passed **303 scoped tests**, zero failures,
errors or skips, with lint/format/mypy and warnings-as-errors passing. Evidence:
`v08-server/run-20261023T194207Z-60e2de45`. A final worker refinement extends the
one-time local safety attempt to the cooperative helper on authority loss; the
final exact-source run is retained separately. Hosted native outcomes remain
pending.


The first hosted thread cohort at **6b178d0** failed its acknowledgment oracle
in [run 40014006886](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40014006886),
while native-boundary, audit, DSS and the original negative pause cohort passed.
Its retained artifact **12526799005** (ZIP SHA-256
`4e6ec00989849acfb5158ec49d34fe5159a0f1c519fb28c7106511291c4cb436`)
was downloaded and CRC/digest checked. It recorded two observed background
identities, one acknowledgment, deadline expiry and UNPROVEN main PAUSED; the
owner/epoch was not transferred. Investigation reproduced the specific bug
locally against the original candidate: resolving `<frozen os>` relative to a
snapshot working directory wrongly admitted a synthetic participant. The fix
requires an originally absolute filename before resolving the snapshot boundary.
A regression now runs with the native snapshot working directory and excludes
frozen, synthetic and relative code while requiring a real background thread to
acknowledge. It does not remove unknown participants by liveness or weaken the
barrier. Candidate-SHA native requalification is required below.


The corrected focused native-pause/component suite passed **40 checks**. The
full local run `v08-server/run-20261023T195114Z-0ba5a66d` passed **304 scoped tests**,
zero failures/errors/skips, lint/format/mypy and warnings-as-errors. The next
hosted thread cohort at **795874d** recorded exactly one observed background
thread, one acknowledgment, no expiry and original main PAUSED; it then failed
the host socket-inventory command. Its retained artifact **12527836953** has ZIP
SHA-256 `b54819b341eb07fb68ff95cc5a0abdc3d319064a71c3de194669a21b23e940f2`
(CRC/digest checked). The socket assertion was narrowed to LISTEN entries,
rather than including established/closing TCP records. CI path filters now cover
the new component and candidate host session. Neither failed attempt is claimed
as successful native integration; complete stable-counter/other-worker results
remain gated on the final candidate. The local 304-test evidence precedes that
small inventory assertion/CI-filter refinement; final exact-source qualification
is recorded separately.


## Confirmed hosted dev15 observed Python-thread component

Final exact-source local qualification
`v08-server/run-20261023T195458Z-9ebc93b4` passed **304 scoped tests**, zero
failures/errors/skips, lint/format/mypy and warnings-as-errors. Every recorded
source hash matched executable code **41a2fb2409f147b6b9bd018f1fe6f089f0eb71e2**.
The offline dev15 build and isolated import/version/CLI smokes passed.

At the same code, merge checkout **d32d9eb5676645548ae2d7110c8cd4cf47ef8b53**,
[services/native run 40015231877](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40015231877)
passed all **six jobs**: foundation (304 tests plus package checks),
native-boundary and audit/DSS/original pause-probe/new thread-barrier cohorts.
[Portable compatibility 40015231748](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40015231748)
passed **241 tests**, zero failures/errors/skips; full all-763 remains unqualified.

The component artifact **12527589091** (ZIP SHA-256
`b96c0324093d195d5d4d6b25d1b4da9601cbde580f17f9ea0a71e7f83acc557c`)
proved main PAUSED with the real background counter stable at **72 to 72**, one
observed thread/one acknowledgment and no expiry/failure. The original negative
control artifact **12528820448** (ZIP SHA-256
`2032617b5bf553ae92161973b08ec20c2d1ef93f3a19f76ce9d789b476716550`)
proved main PAUSED still leaves the counter advancing **62 to 81** without the
component. Both downloaded artifacts passed ZIP CRC/digest checks and all
**19 runtime source hashes** matched the candidate.

The component cohort had ten native Executors/thirty distinct native PIDs,
nine unrelated normal completions, nineteen durable lifecycle events, actual
loopback-only helper binding, unchanged owner/epoch and all ten logical
holds/spent slots retained. Maximum observed unrelated-controller read latency
was **0.014496056 seconds**. Independent host cleanup ended B after collecting
evidence; this is not native completion, reclamation or whole-family proof.
The durable redacted receipt is
`evidence/native-thread-barrier/qualification-summary.json`.

This qualifies the **observed snapshot background-Python component only**.
Native extensions/unknown participants, children and prompt/control/effect queue
settlement remain unqualified. Context refuses effective transfer and every
whole-family/runtime/full-v0.8 flag stays false. Next implementation is native
child admission plus family queue/effect settlement before any ownership CAS
and explicitly admitted new-owner resume. The PR remains draft and unmerged;
no tag, release or production deployment is authorized by these test results.


## dev16 full-release request, child authority and publication preflight

The latest owner request, **Qualify and release full v0.8**, supplies conditional
merge/tag/GitHub publication authorization once all mandatory gates pass. It does
not waive qualification or authorize production migration. RELEASE_READINESS.md
and RELEASE_GATES.json record the active request and exact pending groups.

The new optional child-admission authority uses original live parent identity,
consumption-winner proof, immutable arguments/mode/source binding and the same
canonical reservation namespace as top-level runs. Grant delivery/consumption is
single use, with no token recovery, replay authority or hold release. Schema 10
fences restart and older binaries. Native before-RUN integration remains absent;
all replies keep native_start_qualified false. The first focused attempt found
root-consume suffix classification incorrectly applying to child-consume and a
test using an integer file descriptor as a path (12 failed/13 passed). Exact
root-route matching and the fixture were corrected; 25 checks then passed. The
expanded checks include missing winner proof and parent-catalog rebinding.
Publication preflight cases reject partial native receipts, stale paired sources,
missing gates, tampering, development/dirty checkouts and hidden runtime changes.

Final local CPython **3.13.16** qualification passed **344 scoped tests**, zero
failures/errors/skips, lint/format/mypy and warnings-as-errors. Evidence:
`v08-server/run-20261023T202621Z-c7777e70`; all recorded source hashes matched the
candidate working tree. Earlier intermediate full run passed 341 before final
source/guard regressions. Offline dev16 wheel build, isolated installed family
module import/version and both service/preflight CLI smokes passed.

The requested full inherited diagnostic was interrupted after repeated failures
and errors. A bounded reproduction (`v08-full-release/inherited-bounded.xml`)
passed 16 and failed 3, first failures caused by missing historical Windows
child-arguments captures. This is not a completed full compatibility run or a
proved application regression. Historical proof needs the original immutable
sources and retained raw archive; current native changes need fresh qualification.
The 241-test portable subset remains separately scoped.

The publication preflight rejected the current development checkout with all
**eleven full mandatory gate groups unqualified**, development version and
uncommitted-source notices. It did not publish. Hosted exact-candidate scoped,
package/native component and compatibility outcomes are recorded when verified.
The child RPC suite is not native child execution or full v0.8 qualification.


## Confirmed hosted dev16 authority and failed full-publication qualification

Executable code **7d2ab39951e3e250aa5bbb43633641fbd5254a3c**, PR merge checkout
**39ad48dd59e48c2c1fb378da30a9b1d8cf1736a5**:
[services/native run 40020149313](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020149313)
passed all six jobs. Foundation passed **344 scoped tests**, zero failures,
errors or skips, including **28 child-authority cases** and **12 publication
preflight cases**, plus package build/install/CLI checks. The audit, DSS,
original negative pause, observed-thread and native-boundary jobs also passed.
[Portable compatibility 40020147843](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020147843)
passed **241 tests**, zero failures/errors/skips. Those are named subsets.

Foundation artifact **12529419483**, ZIP SHA-256
`27311f95e897a2405c203ba2dd8437dbea5c2be5a1b7898322558adda7653c80`,
was downloaded and ZIP CRC/digest checked. All **111 recorded source hashes**
matched the candidate. The receipt is
`evidence/child-admission/qualification-summary.json`. It explicitly keeps native
before-RUN child execution, native pause and full-v0.8 qualification false.

On the clean committed candidate, the publication preflight exited **1**:
**full_v08_qualified=false, eligible_for_publication=false**. All eleven mandatory
full gate groups remain unqualified and the package is a development version.
No uncommitted-source blocker remains on that assessment. The executed report
is `evidence/release-readiness/publication-preflight.json`; the bounded inherited
failure is separately summarized beside it. No native child was launched by the
new API tests and no mandatory gate was promoted by a green component workflow.
The latest verified published release remains v0.7. Full v0.8 publication is
conditionally authorized, but the requested qualification has failed and
substantial native/UI/deployment/recovery/security work remains. No v0.8 release
was created.

### dev17 native before-spawn child provider candidate

Adds a checked-source compiled Context launch gate, exact native peer process
identity, original-family admission/consumption and a separate hosted native
child cohort. The 22 new locally executable provider/RPC cases pass, including
all mode bindings, nested provenance, races, revocation and committed-but-lost
replies. An additional real Unix SO_PEERCRED/pidfd case is retained unchanged;
this managed local host rejects creation of AF_UNIX sockets with EPERM, so its
local result is a failure, not a pass or a skip. Hosted Ubuntu qualification is
required. No native child result or full release qualification is inferred from
these component checks. Prior dev16 hosted results remain historical exact-source
evidence, not verification of changed dev17 runtime code.

First dev17 hosted attempt at `08ec573` (PR run 40038718571) passed the
367 scoped checks, package smoke and the five existing baseline/native profiles.
The new child profile compiled all 74 Context translation units, reproduced the
frozen native composition and started ten roots through the checked native gate,
but timed out before observing children RUNNING. That job is failed, with its
original CI artifact retained (12537798253; ZIP SHA-256
`0cdb260c05bfba78ea5defe91663767504330e702e11232583fea1fe1831e546`).
It is not a positive child-start qualification. Follow-up adds direct native
start/peer-denial probes, strict receipt types, current authority checks before
visible-child RUN, bounded native log diagnostics and the required explicit
`spell.runtime.ARGS` import in the child fixture.

The `c4fb768` push child job (40039300726) exposed a startup notification race:
nine roots became ready; the tenth Executor was physically PAUSED but startup
waited for a PAUSED notification consumed by the runtime pump during an info
request. No child success is claimed. The follow-up installs that pump only
after `NativeSession.start()` has completed its own handshake. The failed ZIP
12537944717 was verified by CRC and SHA-256
`e81dc53fb5e1ec1282914398af1859d217c68457c8b7610365b9649b8e2f5d02`.
The same `c4fb768` PR native child run (40039305597) passed direct native GUI
unadmitted-root and same-UID Unix peer denial, then reached WAITING in the parent
without child RUNNING. Its ZIP 12538438420 passed CRC/SHA verification
(`e0e6a3cce648ac1c54c03ed77686e8650a5bdea1ba5b104d2fd2427610ac97a6`).
Follow-up records bounded before-spawn admission stages and retained child-state
counts to distinguish an authority rejection from native startup blockage.

At `45d187f`, all existing native jobs and 372 scoped tests passed; the new child
profile remained failed. Verified ZIP 12538728112
(`6981fecc659cfdc83cb59fc63c4e273f6c3e3ba0f8f1d5d580192ebbb76812f6`)
showed the original native before-spawn child request being rejected by the
provider's positive-only instance-number check, with zero child authority rows.
The original native `getInstanceId()` assigns `#0` to a first child. The validator
now accepts canonical zero-based suffixes and tests exactly-one admission for
that original format. No failed native run is relabeled as a pass.

Agent-memory hardening also requires non-dumpability before config/launch. Its
real subprocess flag test passes locally. This managed host denies even a
positive-control `process_vm_readv` against a test child, so the additional
before/after memory-read regression fails locally on the positive control and
must pass in hosted Linux CI. It is not skipped, and denial without a working
positive control is never counted as a security pass.

The `ed5c9de` child cohort completed all ten roots and ten admitted children,
observed forty simultaneous native PIDs, retained ten consumed child rows and
twenty logical holds, and denied both native GUI and same-UID peer bypasses.
Its final audit assertion failed: hidden automatic children do not traverse
original `callbackEventCall()`'s STATUS_LOADED branch and therefore do not emit
the same start event as visible children. The next harness checks this original
source behavior explicitly (root start/finish, visible-child start, every child
finish) and retains observed per-worker counts; no start event is fabricated.
The failed ZIP 12538963062 passed CRC and digest checks
(`a3653cdf0b3b92c9fe9fd81d58ef4822a290dbb766b243b494ba58f75e2a2d07`).

The same executable checkpoint's push DSS cohort failed on one original
SendCommand HTTP 503 under the ten-worker burst. No command retry was performed.
ZIP 12539241160 passed CRC and SHA-256 verification
(`edf0fdb0b34bd73956c9c4dc735b0ac9d3bbbea6ba3de86ce42ab4cddfd1f660`).
A follow-up adds durable bounded failure categories to the private Context
ledger and a real mTLS held-resource regression: busy denial produces no binary
intent/effect, records the reason and retains replay denial. Failure diagnostics
must establish the bottleneck before any timeout/admission policy is changed.

At **b644d56223f0a859819c19afef0f5f5b1d18a06e**, all six native component jobs
in push run [40041544143](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40041544143)
passed, including the new before-spawn child cohort. It completed ten roots and
ten automatic blocking children (five visible/five hidden), verified forty
native PIDs, original argument transfer, native GUI/peer bypass denial and
physical spent-grant clone denial, and retained ten consumed child admissions,
ten spent workers and twenty logical holds. Thirty-five actual lifecycle EV
receipts match the original visible/hidden distinction. The child ZIP digest
`b656651a7970af562a23884fd58448e4e71548388c37ac19e42fc0a6792a0a8a`
and CRC were verified, and all 23 source hashes matched that commit. The
[redacted receipt](evidence/native-child-start/qualification-summary.json)
contains counts, public source hashes and qualification limits only.

The same push's foundation suite hit the runner's 180-second limit; the overall
workflow is failed, not green. Artifact 12539822036 has ZIP digest
`c064242a9921ed34109f8037d388e00d19a6876d7f29035a6498207c3ea4c63d`.
The follow-up allows 300 seconds for the expanded suite, keeps lint/type budgets
unchanged, retains partial logs and exit 124 on timeout, and never marks such an
attempt passed. Service/effect/transport timeouts are unchanged. Two actual
subprocess regressions verify timeout and nonzero-exit failure retention.
A separate real mTLS/DSS regression runs three ten-request bursts, checks thirty
commands and 150 ACKED stage rows in each independent ledger, and does not retry.
These three new local regressions passed; hosted full-suite results remain
required. All full release gates remain unqualified.

Final local scoped run before the metadata-reader correction passed **377 tests**
with warnings as errors and deliberately deselected the two Linux controls this
managed host cannot execute (Unix peer/pidfd and positive-control cross-process
memory read). Those two remain mandatory, unskipped in hosted CI. The new fixed
metadata endpoint tests then passed **3/3**, and the driver/effect regression run
passed **74 tests** before the final HTTP-error-close addition. These are explicit
subsets, not a completed all-382 result.

The security review found that inherited urllib metadata reads could follow a
DSS redirect or environment proxy away from the operator-owned endpoint. The
private v0.8 adapter now refuses both, limits metadata paths to state/telemetry,
and closes HTTP-error responses. Actual HTTP peer tests confirm no request to
the redirect target/proxy or unlisted path and no success for a closed 503
response. Published v0.7 transport bytes remain unchanged. Hosted exact-source
CI, including the new 300-second scoped-suite budget and these regressions,
is required before treating the final candidate as verified.

At **39ce43c7f0b9d8ce90f4789e62f27fc26a4c0b3e**, hosted push
[40043463719](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40043463719)
and PR [40043468765](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40043468765)
passed all seven services/native jobs. The expanded foundation suite completed
**382 tests**, zero failures/errors/skips, lint/format/mypy, isolated dev17 wheel
installation/version and service/preflight CLI smokes. This includes the actual
same-UID memory-read positive control and subsequent protection denial, Unix
peer/pidfd tests, metadata redirect/proxy denial, three ten-command mTLS bursts,
all original driver/effect checks and the native child cohort. These are scoped
component checks; no full v0.8 gate is promoted.

The next candidate adds a separate native Listener-survival cohort. It uses a
real read-only observer through an independently pinned edge/Listener/Context
path, kills and recreates the Listener process, checks continuing native counters
and unchanged thirty PIDs, and compares Context incarnation, owners, epochs,
generations, holds and spent slots. The Listener has no host manager or authority
volume. This is a new test awaiting actual hosted execution, not a recorded pass;
it does not qualify controller disconnection, recovery, browser/WSS or production
deployment. Existing private native profiles remain separate.

At **56439d763074e8e62be0457a57286c6b10639444**, push
[40044575533](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40044575533)
passed all eight services/native jobs and all **382 scoped tests** with zero
failures/errors/skips. Foundation archive digest
`267868148fa551f6bef8a9f2d3fd5522a1bd62abf01ead2c5c6ec3c655a365d8`,
CRC and all **119** repository source hashes were verified. The
[redacted foundation receipt](evidence/native-child-start/foundation-summary.json)
also records the distinct failed PR attempt below.

The new Listener cohort passed in both push and PR runs. It killed the actual
Listener and recreated a distinct process/container while all ten native
procedures advanced, thirty native PIDs stayed unchanged, and Context process,
incarnation, owners, epochs and generations remained identical. Ten logical
holds and ten spent workers remained. Worker-as-edge impersonation was denied.
The Listener had no host manager or authority volume. The push Listener ZIP
digest `b77d996210abad1f5d8b149a2daaca083df0f4298bf7632a014200a6797705e0`,
CRC and all **24** source hashes were verified; the
[redacted receipt](evidence/listener-survival/qualification-summary.json) contains
counts, public source hashes and explicit limits. This is read-only observer
survival, not active-controller disconnection, native recovery or full services
qualification.

PR [40044579825](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40044579825)
passed all seven native jobs but its foundation suite had **381 passes and one
failure**, `test_twenty_duplicate_rpc_calls_produce_one_real_command`: one 200
and sixteen 409 responses were observed; the previous assertion discarded the
remaining three denial statuses/error codes. Archive 12540783103 digest
`0693f6a2a09c29a49d08c066b76cb6521511c2412e8a91fd9cdcba397c51fb02` and CRC
were verified. No all-green PR result is inferred. The follow-up retains bounded
status/error-code diagnostics while preserving its one-success/nineteen-replay
assertion and no-retry behavior. A local focused rerun passed, but cannot explain
or override the failed hosted attempt. The cause remains under investigation.

The next native child candidate extends that existing cohort with one visible,
automatic blocking grandchild under child 0. The trusted host opens a separate
start barrier only after all first-level children are running, requires a second
distinct child-running observation in that worker and **41** simultaneous native
PIDs, then checks eleven consumed child admissions, one consumed same-family
parent link, twenty-one logical holds and thirty-seven original EV receipts.
Generated procedure sources compiled and 27 local provider tests passed (the
managed host's Unix peer control was deliberately deselected, still mandatory
unskipped in hosted CI). This new nested native cohort awaits hosted execution;
no nested or full-family pass is claimed from source/provider checks.

At **9bbae553b863b40129111f2d904a5cdf33891706**, all seven native jobs passed
in push run 40045545732 and PR run 40045550149, including the expanded nested
cohort. It verified **41 native PIDs, eleven consumed admissions with one correct
consumed same-family parent link, 37 original lifecycle receipts, 21 retained
holds and ten spent workers**. ZIP digest
`1459a71a6ab2cbd8c1561c3260fe7716e64efd778b7fcbd7b1a17c8ec2869618`, CRC and
all 23 repository source hashes matched. See
[evidence/native-child-start/nested-summary.json](evidence/native-child-start/nested-summary.json).
Only one visible automatic blocking grandchild is qualified; manual, nonblocking,
error/prompt/return/repeat, full-family handoff/resume and recovery remain pending.

Both foundation attempts at 9bbae55 failed the ten-independent-effect test before
any command effect: the metadata reader's one-slot admission queue exceeded its
250ms budget. The PR archive 12541003473 digest
`2b9f706c7a307601c7daece15a855069f23308fa435d372eb7c8b24e93c8d66f` and
push archive 12541097738 digest
`dc519337203b86f832a131e5b4bb3c14498f631973a40c59c2f1d4ce1dc0a19c`, plus both
CRCs, were verified. The duplicate-driver assertion passed in these attempts;
its earlier differing denials remain unexplained, not presumed fixed. The
follow-up allows three concurrent metadata reads against the fixed DSS API's
four configured handlers, preserving one handler for independent observation.
Queue/socket/effect deadlines, replay denial and exact test expectations remain
unchanged. Hosted load qualification is required; this change is not yet a pass.

The same next candidate adds the installed pinned IDE observer through a
separate actual gateway to the native Listener-survival cohort: exact installed
client hash/version, discovery and unchanged execution identities before/after
Listener replacement, explicit 503 during outage, control denial for the read-only
user and no reconstructed controller proof. This is pending hosted execution;
it cannot qualify native IDE Run/Debug, Qt/browser controls or full v0.8.

At **d523c96b4636c51dedf62a62563469e0de20982e**, the installed pinned IDE native
observer passed hosted Listener jobs in both push 40045966181 and PR 40045970114.
It used the actual installed client (version/hash checked), a separate gateway,
Listener and unchanged Context. It observed ten actual native executions, was
denied control, received 503 while Listener was absent and reconnected to the
original execution identities with no controller proof. All ten native counters
advanced through outage, thirty PIDs stayed unchanged and ten holds/spent slots
remained. The push artifact 12540868163 digest
`a991dd80314dd3c25b56e3b49370c30ee62d830614fc7ffb911b0b17b63abcfb`, CRC and
all 24 source hashes were verified. See
[evidence/listener-survival/ide-observer-summary.json](evidence/listener-survival/ide-observer-summary.json).
Native IDE Run/Debug, active-controller disconnect and full v0.8 remain unqualified.

The final local scoped suite at d523c96 completed **380 tests, two deliberately
deselected Linux positive controls**, zero failures/errors, warnings as errors.
Those controls remain mandatory/unskipped in hosted CI. Ruff and mypy passed.
Clean full-publication preflight exited **1** with all eleven full groups false
and the package still 0.8.0.dev17; no publication occurred.

Final executable candidate **d523c96b4636c51dedf62a62563469e0de20982e** passed
**all eight services/native jobs in both push 40045966181 and PR 40045970114**.
Both portable workflows 40045966101/40045970135 also succeeded. The foundation
suite completed **382 tests, zero failures/errors/skips**, lint/format/mypy and
isolated installed package checks. This includes unchanged strict replay and
ten-independent-effect assertions after the bounded metadata concurrency fix.
PR foundation artifact 12541695642 digest
`78e07b565e46b83eeb3f8873a3ed1feb23b7666594a4b54d713ba6152cc3bf36` and CRC
were verified, and all 119 public source hashes matched d523c96. See
[evidence/native-child-start/dev17-final-foundation.json](evidence/native-child-start/dev17-final-foundation.json).
These results qualify the stated development components only. All eleven full
release groups remain false; public runtime remains disabled.

## dev18 bounded concurrent command admission (in progress)

Latest evidence-head PR run 40046331677 retained a failure at
`test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss`: two
requests returned 503 with durable `native_driver_resource_busy` categories.
Push run 40046325660 and all seven native jobs in both runs passed. The failed
PR foundation archive 12541263559 digest
`ee9dd2354ec97fa5f8f8f2fadf4840af352bca83c195f8cfbe19e9b035c757b5` and CRC
were independently verified. That failed run is not replaced by earlier green
results. This is a distinct command-resource wait bottleneck, after the earlier
metadata admission correction.

A deterministic regression holds actual TRANSPORT sends before receipt reads.
Before correction, only one of ten calls reached this point; the test failed.
The private simulator adapter now permits at most ten independent command
streams (below DSS's sixteen TCP handlers), with immediate capacity denial.
It retains original per-operation identities, per-stage authorization under the
execution mutex, separate durable ledgers, bounded deadlines and no replay.
The normal case requires all ten real streams to reach the receipt barrier,
the eleventh request to produce no effect, and exactly five ACKED rows for each
accepted operation in both ledgers. A second case fences control while all ten
receipts are pending: no call may progress beyond TRANSPORT or execute a command,
all call outcomes remain uncertain, and original owner/epoch/holds are retained.
No native handoff success or full release gate is inferred. Hosted dev18
qualification is pending.

Local dev18 validation: **74 driver/effect tests passed**, including both new
actual-send/receipt-barrier cases. Full scoped local run: **382 passed, two
explicitly deselected host-incompatible Linux positive controls**, warnings as
errors, zero failures. Hosted CI retains both controls unskipped (384 total).
Ruff format/lint, mypy over fifteen server files, dev18 wheel build, isolated
installed version match and service CLI smoke passed. No hosted dev18 result is
claimed yet.
## dev18 exact-source hosted completion and dev19 native control work

Runtime commit `14642765fb5642600d5525105f57d0a6b8bccb1d` passed all eight
services/native jobs in PR run 40112024277 and push run 40112020263. Portable
runs 40112024274 and 40112020176 passed. PR foundation completed **384 tests,
zero failures/errors/skips**, plus lint/format/types and installed package smokes.
Artifact 12567297002 SHA-256
`233adecaf6f5ce60e72acfcf3b32e9a05d332e2cc9c376cfe91227fc036a680a`, its ZIP
CRC and all 119 public source hashes were verified against that runtime commit.
The redacted receipt is
[evidence/native-child-start/dev18-final-foundation.json](evidence/native-child-start/dev18-final-foundation.json).
This validates the bounded independent-command correction; full v0.8 is still
unqualified, including all-763 compatibility and deployment qualification.

The dev19 candidate adds the explicit private native RUN journal described in
[NATIVE_CONTROL_JOURNAL.md](NATIVE_CONTROL_JOURNAL.md). Twenty-five focused tests
pass over actual mTLS, including lost replies, competing admissions, a fence
between admission and IPC, and restart retaining uncertainty/holds. Initial
focused execution exposed missing fixed client routes and a restart-fixture
error; both were corrected. The subsequent focused suite, lint/format and mypy
passed. Hosted native and final full-suite results remain pending for dev19.

The first dev19 full local run retained **406 passed, one failed, two deselected**:
the existing 100-way child-admission test had one winner but only 91 of 99
expected conflict responses. The other eight status/error pairs were not retained
by the old assertion, so no cause is claimed. The assertion now records bounded
status/error counts without changing one-winner/ninety-nine-conflict requirements.
Ten isolated repetitions passed; the full confirmation run then passed **407
tests, two deselected**, warnings as errors. The two managed-host-incompatible
Linux positive controls remain mandatory and unskipped in hosted CI (expected
409 tests). This intermittent original anomaly remains an open qualification risk.
The final strengthened 25 journal tests passed again, including checking the
committed uncertain row before the native send boundary. Ruff/format/mypy passed;
the dev19 wheel built and its isolated installed import/version/CLI smoke passed.
Hosted dev19 native execution and exact-source CI remain pending.

## dev19 hosted evidence and dev20 telemetry admission correction

At **ec9ad5d94022a8915970f0e5ac5c5c2a44e11f60**, push run 40113822680 passed
all eight services/native jobs. PR run 40113825594 passed seven jobs, including
foundation (**409 tests, zero failures/errors/skips**) and the native child cohort,
but failed the DSS cohort. Portable PR 40113825595 passed. Foundation artifact
12567672711 digest
`d1287126cfc78bea43ad02e2a40eac4f57ff948e9fab03c2d0a29fbf8982d7c9`,
CRC and 122 source hashes were verified. Child artifact 12567304316 digest
`d62f544d7936e2ba3a8028d479a927fd2ba423f7564b50233c667bfac86abefa`,
CRC and 25 hashes were verified. Ten workers recorded sixteen original agent
RUN attempts, with six correct consumed child bindings; every IPC acknowledgment
remained uncertain and no family transfer was authorized.
See [foundation](evidence/native-child-start/dev19-foundation.json) and
[child journal](evidence/native-child-start/dev19-child.json) receipts.

The failed PR DSS artifact 12567532971 digest
`fb20c26abb841169572f9df931c619b50012ab6f4094e99ccdfe24ad6f9ea9bc`,
CRC and all 90 source hashes were verified. One TM/RefreshItem call encountered
RemoteDisconnected: 49 driver calls completed, one stayed UNCERTAIN, and all 50
command-stage receipts were ACKED. The affected native procedure failed; the
successful push run does not override this failure.
[Redacted failed-run receipt](evidence/native-context-dss/dev19-failed-telemetry.json).

Inspection found that the three-reader metadata limit covered current_state()
but inherited sample() called get(telemetry) directly. Two deterministic
regressions fail against dev19: ten inherited samples exceed the reader limit at
the actual four-handler HTTP boundary, and a saturated metadata budget still
permits HTTP. Dev20 moves the unchanged three-reader/250 ms admission budget into
get(), so initialization, state and telemetry share it. No deadline, handler
capacity, command receipt rule or retry behavior changes; the legacy transport
and original patch preimages remain unchanged. Both regressions and the complete
79-test metadata/driver/effect group pass after the change. Full local and hosted
dev20 qualification remain pending. This evidence establishes the admission gap;
the hosted disconnect's exact server-side interleaving was not captured.

The final dev20 local suite passed **409 tests, two deselected**, warnings as
errors (166.68 seconds). Ruff/format/mypy and the built, isolated installed dev20
wheel import/version/CLI smoke passed. Hosted CI must run all **411** checks,
including the two Linux positive controls, and the real native DSS cohort.

## Verified dev20 executable checkpoint

Executable **a9c9bb17c4b68e9a53b79f6263ac93f44f0a6695** passed all eight
services/native jobs in PR run 40114793223. The foundation suite passed **411
tests, zero failures/errors/skips**, plus lint/format/types and installed package
checks. Both portable runs 40114793208 and 40114789291 passed. The push native DSS
job passed; final push foundation/child statuses were still in progress at this
checkpoint, so no all-green push claim is made.

PR foundation artifact 12568097164 digest
`a16f1659bb3387905198cb406cba8adf62c24e48229bc3501dbaaf46453968cb`,
CRC and all 122 source hashes were verified. Native DSS artifact 12568435398 digest
`5cf9bc8043cbd9cd3bf4eb9dba5f9f63ff39778082421bf25449384d3e1b3305`,
CRC and all 90 hashes were verified. Its 50 driver calls completed with no
recorded failures: ten commands, ten refreshes and fifty matching ACKED stages
in each authority/driver ledger. Ten workers terminated with ten logical holds
and spent slots retained. Copied-original-config command denial remained active.
See [foundation](evidence/native-context-dss/dev20-foundation.json) and
[native DSS](evidence/native-context-dss/dev20-dss.json) receipts.

The original strict 100-way child-admission race also passed fifty fresh-state
repetitions (38.43 seconds): 5000 admission attempts, 50 winners, 4950 conflicts.
The earlier eight unclassified responses remain unexplained. This stress result
is not evidence that their cause was repaired.
[Reproduction harness and counts](evidence/native-child-start/dev20-race-stress.json).

Clean full-publication preflight still exited **1** with all eleven full gate
groups false and development version 0.8.0.dev20. No merge, tag, release or
production migration occurred.
[Publication preflight](evidence/release-readiness/publication-preflight-dev20.json).

These evidence-only changes preserve all 122 hashed foundation inputs and all
90 native DSS inputs of a9c9bb1. They are saved on a separate qualification branch
to preserve the still-active push validation. Full-family native handoff/resume,
joint native IDE Run/Debug, all-763 compatibility, deployed Compose/Kubernetes
faults/recovery and final security/release acceptance remain incomplete.

Final follow-up: push services/native run **40114789340** completed successfully
at the same a9c9bb1 executable commit. Both PR and push now pass all eight
services/native jobs and both portable workflows pass. The evidence branch can
be integrated without cancelling the original validation. All full-release
gates remain false; no additional runtime functionality is inferred.

## dev21 bounded execution admission correction

The unchanged executable code at documentation head 6e5cecb had another failed
PR foundation run, **40116162199/job 120937765044**: 411 tests, one burst failure,
ten HTTP 500 responses. All seven native jobs and the push workflow passed.
Artifact 12568851330 SHA-256
`2aad062856f053e03041c8ec752cdf609dc811ffcb6a275401a4ac9c58495812`,
CRC and all 122 source hashes were verified. The failure remains retained in
[the redacted receipt](evidence/native-context-dss/dev20-documentation-head-failure.json).

Type-only exception diagnostics reproduced execution_busy in local strict burst
stress: the diagnostic-only source failed repetition 9, and FIFO alone failed
repetition 28. Dev21 adds bounded FIFO admission (64 waiters, the same 250 ms
deadline) and removes redundant execution-mutex admission from identity-only
reads. Each read still uses one consistent state transaction. Mutations and
every actual send retain their final original-grant check and execution mutex;
reads are not effect permits. No socket, metadata or effect deadlines were
increased and no retries were added. The failed hosted run's original exceptions
were not captured, so its precise interleaving is not claimed to be known.

FIFO plus snapshot reads passed 30 fresh-state repetitions: **900 commands,
4500 ACKED stages in each ledger**, unchanged exact success/count assertions.
[Harness, counts and source hashes](evidence/native-context-dss/dev21-burst-stress.json).
The 72 focused authority/driver tests passed. Full local suite: **416 passed,
two deselected**, warnings as errors, 161.68 seconds. Those Linux controls remain
mandatory in hosted CI (418 expected tests). Ruff/format/mypy and isolated dev21
wheel install/import/version/CLI passed. Tests cover non-owner release, cancelled
head, interrupted wait, bounded queue, no barging and real mTLS identity checks
while another action owns the stage lock, followed by post-disconnect rejection.
Exact-source hosted dev21 results are pending; no full gate is promoted.

## dev21 hosted completion; dev22 native before-forward candidate

Runtime **0d31c4905be4b74702b95a566bb07d99cabc6b1a** passed all eight jobs in
both PR 40119871531 and push 40119867008; both portable runs 40119871566 and
40119867010 passed. Foundation completed **418 tests without failures/errors/skips**.
Artifact 12571330675 SHA-256
`e9867abee05118c9f725294802d751b4cb340936fac913d5daf52de7261b3f2d`,
CRC and 124 source hashes were independently checked.
[Receipt](evidence/native-context-dss/dev21-foundation.json).

Dev22 adds a real native Context hook before Executor IPC forwarding. A RUN
message carries the original journal UUID; the native Context authenticates
the owned agent over the existing Unix helper and receives one-shot live
admission through pinned worker-to-Context mTLS. Unknown/replayed IDs or changed
targets never forward. Lost admission responses cannot retry; schema 12 retains
FORWARD_UNPROVEN and fences it on restart. The authenticated helper remains
bounded; no host socket, privilege or new grant is added. The original Executor
queue and other mutation paths are not yet fenced by this component.

The native child cohort must prove sixteen forward rows with identical original
journal identities and ten actual unregistered-RUN probes. Each probe bypasses
the Python wrapper, requires native callback denial and verifies that the
Executor remains PAUSED before legitimate execution. This is an isolated
audit/compute profile; it cannot dispatch satellite commands. Exact native
Context source reproduction and the 74-unit build remain mandatory in CI.

Local: **58 focused checks passed, one hosted-only peer control excluded**;
full suite **422 passed, two deselected**, warnings as errors, 196.11 seconds.
Both Linux controls remain mandatory in hosted CI, for 424 expected tests.
Ruff/format/mypy and isolated dev22 package install/import/version/CLI passed.
Hosted native compilation and before-forward positive/negative evidence are
pending. Neither forwarding admission nor IPC acknowledgment qualifies native
dequeue, family quiescence, handoff/resume or full v0.8 release.

### Verified dev22 executable result

**bfa4a7f07c5c2289c7329bd1da10ee08c5e69932** passed all eight jobs in both
PR services/native run **40120586927** and push **40120582247**. PR portable
compatibility **40120586930** also passed. Foundation completed **424 tests,
zero failures/errors/skips**; both previously excluded Linux controls ran.

Foundation artifact 12570687307 digest
`328fbd49feda6a2e9e8ab3995e2c20b525ef489fdecd117daa50ca92c95c7715`,
CRC and 124 source hashes were verified. Native child/forward artifact 12571112042
digest `970deacb6809aabe1f7b5c93cff9c41da30c563652f7d49887ebc7fac8449b08`,
CRC and 26 hashes were verified. The real rebuilt native Context denied all ten
unregistered RUN probes, accepted sixteen legitimate forwards with identical
journal origins/operation hashes, and retained FORWARD_UNPROVEN for every one.
Eleven child admissions including one nested child, 21 holds and ten spent
workers remained. No native dequeue or quiescence proof was synthesized.
[Foundation](evidence/native-child-start/dev22-foundation.json) and
[actual forwarding component](evidence/native-child-start/dev22-forward.json).

The [clean publication preflight](evidence/release-readiness/publication-preflight-dev22.json)
still exits **1**: dev22 is a development package and all eleven full groups are
unqualified. No PR merge, v0.8 tag, release or production migration occurred.
These documentation/evidence changes preserve all 124 foundation and 26 native
qualification inputs from bfa4a7f.

## dev23 native initial RUN consumption candidate

Dev23 carries the immutable RUN UUID through the real native command structure
and checks live authority again at `SPELLcontroller::executeCommand`, before RUN
effects. Context binds each admitted member to its spawned PID; the helper
requires the exact read-only candidate Executor, owned native Context parent,
pidfd incarnation and SO_PEERCRED identity. Executor callbacks are limited to
their own instance and cannot spawn/bind/forward. A consumption must match its
original verified forward and cannot retry after reply loss. Schema 13 records
EXECUTION_UNPROVEN, retaining all holds and restart fencing.

The private candidate defers internal hidden/headless `setAutoRun` to the normal
initial pause. Its opt-in child client issues one admitted initial RUN for hidden
and visible automatic children. The frozen published programs and default
legacy child behavior are preserved. Only initial RUN is covered: other direct
mutations, prompts, queue dispositions, complete family barrier and new-owner
resume remain unfinished. Consumption admission is not completion or settlement.

Local result: **431 passed, three deselected**, warnings as errors, 166.56 seconds.
The two prior Linux controls and new exact Executor peer control remain mandatory
in hosted CI, for **434 expected checks**. The new control was attempted locally;
this managed host rejects AF_UNIX socket creation with EPERM. No pass is inferred.
**67 focused checks passed**, with two peer controls excluded. Ruff check/format,
mypy (17 modules), and isolated installed dev23 wheel import/version and both
CLI help checks passed. Frozen source patch reproduction matched the original
Context preimage; source manifests select **74 Context / 112 Executor units**,
139 unique compilation units. Native compilation was not performed on this host.

The hosted child cohort must now produce **21 matching journal/forward/consumption
rows and exact PID bindings**, including hidden children, and retain all 21 holds,
ten spent workers and the ten actual native unadmitted-RUN denials. Exact-source
hosted results are pending. All eleven full release groups remain unqualified;
no merge, version tag, release, or production migration is performed.

### dev23 hosted service pass and retained native build failure

At **944ed1e66431e71a5fc408d13115478960b3d580**, both PR 40128997839 and push
40128993473 passed foundation and six existing native jobs, but the child-family
job failed before executing the new native candidate. Foundation completed
**434 tests, zero failures/errors/skips**, including all three Linux controls.
PR portable workflow 40128997842 passed. Foundation artifact 12574466940 digest
`95e859cef7ac4f24f50a9c43b54f6bffa702ba3ef8d64a1b1848ea9102907a74`,
CRC and all **127** repository hashes were verified. Native failed artifact
12574905892 digest `b51fd2e1aa6a47289164f32498421700bf6b8b1a95bd7c9af6673e7fd7824a58`,
CRC and **29** hashes were verified. The direct Executor link lacked the frozen
`ws_filter.cpp` and `continuation.cpp` support objects. No native consumption
success is inferred from this failed build. Redacted receipts retain the
[service pass](evidence/native-child-start/dev23-foundation.json) and
[native failure](evidence/native-child-start/dev23-native-build-failure.json).

## dev24 candidate: frozen common runtime and native stale-consumption probe

The builder now reproduces the frozen 13-library common runtime with both
manifest-verified supplemental support units. Context remains a separate native
graph. Executor links the candidate common library; its main registers that
library's DTA init function before Python startup, so the installed Python shim
cannot load a second executor singleton. The private session explicitly selects
the read-only candidate Executor. Native root fixtures require the DTA built-in
origin and exactly the candidate shared library in their process maps.
Source selection is 74 Context / 112 Executor units, 120 common-library units,
and two supplemental units; there are **144 unique compilation units**.

After the 21 legitimate family RUNs, a fresh eleventh worker/slot/certificate and
independent controller connection tests the actual native consumption race.
The agent delays only before the final live authority check; the host closes
the controller durably and then permits that check to proceed. Passing requires
exact HTTP 403, zero consumption receipts, a still-PAUSED Executor with the same
three native PIDs, no procedure-body write marker, unchanged unrelated execution
states, and retained owner/epoch. Host-observed termination must still leave
**22 logical holds and 11 spent workers**. The first ten workers still prove ten
concurrent procedures; the extra probe is a separate later execution.

Local: **68 focused checks passed, two peer controls deselected**. The additional
mTLS regression exercises the same forwarding/connection-close/consumption
ordering. Ruff/format/mypy and isolated installed dev24 package import/version
and both CLI checks passed. Full hosted suite now expects **435** checks, with
all three Linux controls mandatory. Native compilation and the new actual race
probe are pending exact-source hosted validation. All full release gates remain
false; no handoff, queue settlement, release or recovery proof is synthesized.

### dev24 retained hosted outcomes

At **c4973097baebf9aec6fdc21a319daebf36fc5c80**, push foundation passed **435
checks with no failures/errors/skips**; PR foundation failed three driver
concurrency assertions. Both native family jobs failed startup because the
harness requested eleven slots and the authority correctly enforces ten.
The candidate native Context, Executor and shared library did build, with 144
units and both frozen support objects verified; no native execution pass follows.

Push artifact 12574527246 digest
`16a6013631f962f1a5975f760787059389b4828e93b68ee21f48a9a4fd78d74f`,
PR failure artifact 12574397471 digest
`622f8a59533bfa1efedcebd0700dc6570c9492e01fcd5c360adf79a742711845`,
and native failure artifact 12574418449 digest
`068f8d91daa55071f82b7c15389c087f6e2948b29cb1683ee269511bc5ca2e27`
were checked with ZIP CRCs and respectively **128 / 128 / 30** repository source
hashes. The native support hashes also matched the frozen v0.7 Git revision.
[Push](evidence/native-child-start/dev24-push-foundation.json),
[PR failure](evidence/native-child-start/dev24-pr-foundation-failure.json),
[native pool failure](evidence/native-child-start/dev24-native-pool-failure.json).
The original hosted failure includes nested execution_busy and subsequent grant
fencing; its exact scheduler interleaving is not claimed.

## dev25: final write boundary, response budget and isolated native race probe

The driver uses a bounded FIFO reentrant ledger writer before the execution
mutex. Durable pre-intent, identity/nonce bookkeeping and receipt settlement no
longer occupy that mutex. Actual socket write, SENT transitions and partial-send
failure fencing remain protected together. All final live-grant checks and the
250 ms/200 ms limits remain. Concurrent settlement/uncertainty serializes both
ledgers; a failed uncertainty fence poisons the Context and keeps all holds.
A Context-owned absolute TC deadline prevents an expired queued operation from
sending after its budget. See [DRIVER_WRITE_GATE.md](DRIVER_WRITE_GATE.md).

The driver RPC's old two-second response socket contradicted its permitted
three-second operation. That route now uses the documented five-second RPC
response budget; two-second TCP/TLS connect, ordinary RPC sockets, server
watchdog and TC operation limits are preserved. Driver test HTTP calls now use
that same five-second budget. A controlled actual mTLS response held beyond two
seconds demonstrates the mismatch; this does not establish every prior timeout's
cause. No effect, command replay, receipt or fencing assertion was relaxed.

Stress history is retained: an initial bookkeeping split failed 5/30 cases;
writer ordering with the old unfair RLock hit an HTTP timeout at case 13; FIFO
passed 30/30 (900 commands, 4500 ACKED stages per ledger). After adding absolute
TC deadlines, the old three-second test response budget timed out at case 21.
The final aligned-budget run passed **30/30**, again **900 commands / 4500 ACKED
stages per ledger**, in 108.37 seconds. Both earlier timeouts remain failures.

Three new fencing/poison regressions fail with the previous c497 effect module;
the delayed-response regression fails with its previous transport client.
The final deadline/driver focused suite passed 88 checks before adding the
response-budget regression; both the new budget and expired-send checks passed.
The latest complete local suite and exact-source hosted outcomes are pending.
All three Linux kernel controls remain mandatory in hosted CI.

The native stale-consumption probe now runs in its own **Context B** with two
slots: a fresh worker and an unstarted reserved witness. The primary Context A
keeps its original ten-slot limit, ten spent workers and 21 holds. B must retain
two holds and one spent worker, preserve its witness and leave A unchanged.
No slot limit is enlarged and no worker is reused.

The C++ probe holds at actual Executor command consumption before opening its
Unix channel. Host observation deliberately exceeds the ordinary four-second
socket deadline before closing the controller and allowing the final check.
Passing still requires an authenticated real native callback, HTTP 403, zero
consumption receipts, unchanged three PIDs, PAUSED status and no body-write marker.
The hold cannot authorize a write or bypass the final check. This closes the
probe's timeout ambiguity; exact native execution validation remains pending.
Public runtime, whole-family settlement/handoff/resume and all full release
qualification groups remain false.


Final dev25 local result: **441 passed, three mandatory-hosted Linux controls
deselected**, warnings as errors, **197.29 seconds**. Full CI expects **444**
checks without skips. Ruff/format/mypy and a fresh isolated installed wheel
import/version, absolute-deadline API and both CLI checks passed. The controlled
response-budget check fails with the previous two-second Route implementation;
the final mTLS delayed-response and expired-queued-write checks both passed.
[Final strict stress receipt](evidence/native-context-dss/dev25-driver-stress.json)
retains exact source hashes, harness, final counts and earlier failed variants.
Exact-source hosted native execution remains pending.

The completed stale-RUN oracle is followed by independent host container teardown,
matching the existing negative pause probes. A closed controller connection
cannot authorize native close/resume. Host termination still cannot release B's
holds or qualify family quiescence/recovery.

### dev25 hosted confirmation and retained family failure

At **f14749f6e0fca1ac16c8fb8fdf5917506115e068**, PR 40133883368 and push
40133879115 passed foundation (**444 checks, zero failures/errors/skips**) and
all six other native jobs: boundary, audit, DSS, pause, observed-thread barrier
and Listener survival. Both child-family jobs failed waiting for child-running.
This is not an all-green workflow or complete native-family qualification.

Foundation artifact 12576600823 digest
`240de0558e308a2a776a0a3812891e42c4f878134acf61d27bc17ecd68afcb5f`
and failed family artifact 12575767828 digest
`6ae6eca46a19d23542b9b97cddd9cd46654e9115af9e03c35217a5207b0a160a`
were verified with ZIP CRCs and **128 / 30** repository hashes. The family
artifact shows ten actual root final-consumption admission callbacks and ten
RUNNING roots, but no consumed child admissions. It never reached the isolated
stale-controller probe. Exact source of the root stall is not yet established.
[Foundation receipt](evidence/native-child-start/dev25-foundation.json) and
[retained family failure](evidence/native-child-start/dev25-family-failure.json).

## dev26 candidate: trusted singleton bootstrap and bounded progress diagnosis

The native singleton check moves from the procedure fixture into the candidate
Executor's trusted bootstrap, before procedure tracing. Its own main registers
the built-in DTA initializer and sets an internal Executor role marker. Under
the GIL, bootstrap requires the built-in DTA module and only the candidate common
library in process mappings. A failure prevents Executor initialization. The
Context retains its independent original metadata graph; the private session
clears the Executor marker before launching Listener/Context, and only Executor
main sets it. The original frozen source programs remain untouched.

The fixture no longer mixes generator/map-inspection assertions into the child
procedure test. This removes an unrelated debugger/tracing boundary from that
oracle; no child count, grant, PID, consumption, deadline or singleton assertion
is relaxed. Candidate progress diagnostics emit at most 64 code positions and
never variable values, arguments or capabilities. The next native run must still
prove all 21 consumptions and the independent Context B stale-admission denial.
The cause of the prior stall is not labelled fixed before that run.

Local: frozen native patch reproduction, **68 focused control/child checks**
(two kernel peer controls excluded), Ruff/format/mypy passed. All driver/service
runtime code is preserved from f14749f; only package version changes. The exact
native bootstrap/child execution and stale-controller probe await hosted CI.

### dev26 actual family completion; strict validator mismatch retained

At **20078bc5836106e4eb90acdec6d84d9199743b2f**, both PR 40135761109 and push
40135757016 again passed foundation and the six other native jobs. Foundation
completed **444 checks without failures/errors/skips**. The child cohort reached
**41 native PIDs, 11 consumed children including the grandchild, 21 exact Executor
bindings and 21 before-forward/consumption callbacks**. All ten parent workers
reached native FINISHED and completed container cleanup. Whole-family transfer
remained BLOCKED with holds retained.

The workflow still failed: its legacy lifecycle expectation omitted hidden
child start events. Worker 1 correctly produced two starts/two finishes for its
root and now-admitted hidden child; the validator expected one start/two finishes.
The check was not bypassed, and the separate stale-controller probe never ran.

Family artifact 12576209442 digest
`91af31d17d6ebafda50d7766d4a5e47fb95b3bb0b3a114902b0a62729d36a3fd`,
ZIP CRC, all 30 repository inputs and **all 144 compiled native source hashes**
were checked against the reproduced frozen composition plus exact candidate
patches. Both supplemental sources matched the frozen Git revision. Foundation
artifact 12576980111 digest
`fc20f528c703fd132a46a553e0b4a678136bfce194221249d682e14f67233b05`,
CRC and 128 source hashes were checked.
[Family validator failure](evidence/native-child-start/dev26-family-validator-failure.json)
and [foundation](evidence/native-child-start/dev26-foundation.json).

Dev27 changes the oracle to require **one real start and finish for each of the
21 procedures**, including hidden children: exactly **42** durable lifecycle
records. Original request IDs, all journal joins, 21 bindings/consumptions,
41-PID concurrent/nested checks and the isolated stale-controller oracle remain
mandatory. Runtime/driver/transport and native C++ code are unchanged from dev26;
only this stronger expected lifecycle count and package metadata change.
Exact-source hosted confirmation and the actual stale-controller probe are
pending. Full v0.8 remains unqualified and all full release gates remain false.


## Dev27 family completion and failed independent consumption probe

At **cdc33dcdeb4bbcb8b1e9b7912efda586ef002e70**, PR run 40136588771 passed
foundation (**444 tests, zero failures/errors/skips**) and the six other native
jobs. The primary family passed all **21 native RUN consumptions/bindings,
11 consumed children, 41 native PIDs and exactly 42 lifecycle events**. Its
holds and spent workers remained retained. The separate Context B probe reached
native before-forward admission, but the Executor did not create its pre-channel
hold marker. The worker timed out before the host could close the controller.
**This run does not verify stale-controller rejection at native consumption.**

Verified foundation artifact 12577040844 SHA-256
`101d9874da09ee55e00ecca7c5dbcba41c5e41cac5e3d6c6d6b5bcf16619ec50`
and family artifact 12577775750 SHA-256
`1da82e4dac59b030c7b28f460dccff5bd1220d36353ea91f462bc4ef1749019c`,
ZIP CRCs, 128/30 repository input hashes and all 144 compiled native source
hashes. Only redacted counts and public source hashes are retained in Git.
[Foundation receipt](evidence/native-child-start/dev27-foundation.json) and
[failed probe receipt](evidence/native-child-start/dev27-consumption-probe-failure.json).

Dev28 assigns the probe workspace tmpfs explicitly to UID/GID 10003 with mode
0700. Before RUN the agent checks ownership and proves marker-directory
writability. A missing marker cannot silently stand in for inability to write
one. The candidate native hook also emits a bounded failure reason on rejection;
the worker publishes only one of five fixed probe categories, never raw logs.
The preceding timeout's exact cause remains unconfirmed until hosted execution.
No authority check, expected callback, HTTP 403, lifecycle count or retained-hold
requirement is removed. The C++ hold remains before the ordinary socket deadline.

Local dev28: **68 focused control/child tests passed**, two mandatory hosted
kernel peer controls excluded; Ruff/format, mypy (17 modules), frozen native
patch-preimage reconstruction, wheel build and isolated installed version/CLI
smokes passed. Actual native C++ compilation/execution requires hosted CI.
All eleven full release gate groups remain false; no full v0.8, release,
production migration, family quiescence or safe post-start handoff is claimed.


## Dev28 verified native final-admission fence and retained DSS failure

**05aff1c525dca5ecd9d15ba322166b871c9ec024** passed every job in push
40137535527. PR 40137539739 passed foundation (**444 tests without skips**),
the native family and five other native jobs, but its DSS job failed.
Portable PR 40137539750 passed. The complete PR workflow is failed evidence.

The native family proves **21 exact final RUN consumptions/bindings, 11 child
admissions, 41 PIDs and 42 lifecycle events**. Its independent Context B probe
held the actual Executor before channel creation, waited five seconds, durably
closed its controller, then obtained a real **HTTP 403** at final admission.
No consumption row or body marker appeared; the same three native PIDs remained.
Original owner/epoch and CONTROLLER_DISCONNECTED stayed recorded. B retained two
holds/one spent worker after independent host teardown; the unstarted witness
and Context A's 21 holds/ten spent workers were unchanged. This is a negative
admission proof, not family quiescence, positive handoff or new-owner resume.

Family artifact 12578175646 SHA-256
`ab4e5f127f3887560ff4df32d9b2458883e2cdbc0033a0056bf1afee74e9a847`,
CRC, 30 repository and all 144 compiled native source hashes were verified.
Foundation artifact 12578161451 SHA-256
`f58996d0bb3227dcce2a9cbdd61b87ab7cb969c064bff0a6bff70eafe90aaa37`,
CRC and 128 repository source hashes were verified.
[Native consumption receipt](evidence/native-child-start/dev28-consumption.json)
and [foundation receipt](evidence/native-child-start/dev28-foundation.json).
Explicit worker-owned writable tmpfs allowed the probe to complete; the prior
run's missing-marker cause is not independently reconstructed from lost logs.

The PR DSS failure had **38 completed driver calls, four uncertain calls and
45 ACKED stages**. Four chains identify effect_deadline_expired. The native
fixture already uses Timeout=2; it has not been increased. Failure artifact
12577406524 SHA-256
`dcad7450c2ffeb315665b04ef62dbb4435e52a0cdb5284aa108827887b8c9089`,
CRC and 95 source hashes were checked.
[Retained failure](evidence/native-context-dss/dev28-dss-failure.json).
No failed command is retried. A separate local 30-case stress with the same
explicit two-second timeout passed 900 commands/4500 ACKED stages per ledger;
that does not explain or erase the hosted failure.

## Dev29 incomplete-operation fencing correction

A deterministic reproduction found a safety gap independent of timing
performance: after earlier stages have receipts, the next stage may fail its
deadline before creating an INTENT. The previous uncertainty path found no row
for that stage and returned, leaving the execution OWNED. A partially completed
multi-stage operation must prevent further writes until reconciliation.

The gate now looks for prior stages with the exact original operation,
execution and grant provenance. It retains their real receipts, records
DRIVER_OPERATION_INCOMPLETE, revokes the capability and marks only that
execution RECOVERY_REQUIRED under its execution mutex. It does not manufacture
an unsent stage or mark ACKED receipts uncertain. A never-started operation,
foreign grant and fully settled receipt cannot fence another execution. An audit
failure poisons the authority while retaining every hold, even if the fencing
transaction rolls back. The original timeout, lock order and no-replay rule
remain unchanged.

The exact old 05aff1c effects module fails **three** new safety regressions;
its unrelated/settled-operation positive control passes. The corrected module
passes all four. Local full service checks passed **445 tests**, with the three
mandatory hosted Linux controls excluded. Afterwards the real ten-request burst
case was expanded to explicit two- and three-second deadlines; both cases passed.
The final hosted suite therefore expects **449 tests without skips**.
Ruff/format/mypy and an isolated installed dev29 wheel/version/CLI smoke passed.
Final repeated two-second stress passed **900 commands and 4500 matching ACKED stages per ledger** in 30 fresh-state cases (111.53 seconds). Exact-source hosted confirmation is pending.
[Safety regressions](evidence/native-context-dss/dev29-incomplete-stage.json) and
[two-second stress](evidence/native-context-dss/dev29-two-second-stress.json).

The next native qualification candidate also provisions explicit Docker CPU
weights: Context/DSS 2048, each worker 128, checked through Docker configuration.
Ten worker cgroups previously used default weights while all competed with the
services. These are relative scheduling weights, not guaranteed CPU reservations,
and the preceding deadline failure's cause remains unproven. Per-worker two-CPU
limits, all operation/write deadlines, full native counts and admission oracles
remain unchanged. The default-weight failure is retained rather than relabelled
fixed by this deployment candidate. Full production resource qualification is
still required. No full release gate is promoted.


## Dev29 exact-source hosted confirmation

At **2c354255562bfcf1bafee16badc1255cbc44ed6f**, PR 40138571818 and push
40138566510 passed all eight service/native jobs. Portable PR 40138571844 passed.
Foundation completed **449 tests without failures/errors/skips**. Native DSS
completed **ten commands and fifty matching ACKED stages in each ledger**.
The family repeated **21 final consumptions/bindings, 11 children, 41 PIDs,
42 lifecycle records and the actual isolated stale-controller HTTP-403 oracle**.
Docker configuration verified Context/DSS CPU shares 2048 and worker shares 128.
The earlier failure remains retained; this does not establish its exact cause.

Verified artifact digests/CRCs and public source hashes:

- Foundation 12577772598, SHA-256
  `5a8aef70becc74e4457e544190284aa34f4bf25c3053525ca9c67c431bc61ddf`,
  128 repository inputs; [receipt](evidence/native-child-start/dev29-foundation.json).
- DSS 12578186871, SHA-256
  `0f3fee28a46743d7bb6ff0516721da05fb2542e23f2d7d460cb6ecd78a23e593`,
  95 repository inputs; [receipt](evidence/native-context-dss/dev29-dss.json).
- Family 12577738973, SHA-256
  `7ebe44c02424475dc65f9fe0b95a949ff325c02396819e7120defff5d77d9467`,
  30 repository and all 144 compiled source inputs;
  [receipt](evidence/native-child-start/dev29-family.json).

## Dev30 candidate: durable members and incarnation continuity

Context now retains an immutable original member roster before native local
binding can return ALLOW. RUN forwarding/consumption require the target's row.
Original grant, memory-only proof, source/parent, numeric/type and uniqueness
checks precede registration. Reply loss cannot rebind; restart preserves/fences
records. The roster is agent-observed worker-namespace metadata and explicitly
REGISTERED_UNPROVEN, not independent host attestation or full family pause.
NATIVE_CONTROL_JOURNAL.md records the exact protocol and limitations.

Review also found a process-incarnation validation interval: authentication
checked pidfd liveness before reading identity metadata, but did not recheck the
pin afterward. Two deterministic tests hold a successful identity result, cause
real kernel pidfd death, and resume authentication. Both fail with the exact
2c35425 helper because it returns an authorized role after death. The candidate
rechecks both Executor/Context pins after identity reads and before returning
permission; member registration also rechecks both pins after its durable RPC.
This closes the observed validation interval, not every possible later process
failure or the unimplemented whole-family barrier.

The new tests exercise real Context mTLS and kernel pidfds; their metadata/wire
result at the death interval is deliberately injected. Actual SO_PEERCRED,
/proc and read-only executable tests remain mandatory hosted positive controls.
An initial direct /proc-read attempt could not resolve managed local child PIDs
and is not counted as before/after security proof. Initial lost-reply tests also
caught a missing client Route allow-list entry; that was corrected before the
successful 36-case run. Two further source-integrity cases then passed in the
484-test full run. Final local regression confirmation passed **486 tests**, with three mandatory
hosted Linux controls excluded. All **40** new member/incarnation cases passed,
including both process-death cases; hosted expects **489 tests without skips**.
[Local original-member evidence](evidence/native-child-start/dev30-local-members.json).
Ruff/format/mypy and isolated installed dev30 wheel/version/CLI checks passed.

The hosted native oracle now requires 21 original durable member rows, and the
isolated stale-controller probe retains its one member. All previous native
counts, HTTP 403/no-body/unchanged-PID/hold checks remain mandatory. No full
release gate, positive transfer, public native Run/Debug, Compose/Kubernetes
qualification or release is inferred from this increment.


## Dev30 native compatibility failure and dev31 zero-index correction

At **88efd352054de499c6d8ed1c84066eabb7f8d398**, foundation passed **489 tests
without failures/errors/skips** and six other native jobs passed in PR
40139911934. Both PR/push family jobs timed out waiting for native-child-running.
The workflow is failed evidence. Each of the ten roots registered/consumed RUN;
ten child admissions were consumed, but every child registration was denied
with a Fault. The original error category suppressed its precise HTTP code.

The source and private retained traces identify a concrete compatibility
mismatch: frozen `lib/SPELL_CTX/src/SPELLexecutorManager.C:getInstanceId` assigns
**#0** to the first instance of a procedure. All ten child fixture instance
mentions in native log tails used #0. The new roster incorrectly required a
positive suffix even though the existing native child gate accepts canonical
zero. Two targeted mTLS root/child tests reproduce **HTTP 400** before correction.

Dev31 accepts the original canonical nonnegative decimal suffix, still bounded
to nine ASCII digits and forbidding leading zeros except the single zero.
It preserves the exact approved source prefix, original grant, parent, immutable
target/PID binding, one-shot receipt, replay and incarnation checks. The child
regression also forwards/consumes its admitted zero-index RUN exactly once and
denies replacement/replay. The native allocator and C++ code are unchanged.
Actual native confirmation remains mandatory; this unit result is not a pass
for the complete family or full v0.8.

During a temporary workspace outage, read-only diagnostic run **40140893578**
(job 121012234067) independently verified the failure archive digest, CRC and
30 input hashes, emitting only redacted counts/fixed public-source error
categories. Its temporary workflow was removed after saving the diagnosis.
Once the workspace returned, local checks repeated the CRC/source checks,
verified all 144 compiled native sources and counted the zero suffixes without
publishing raw operational traces.

- Family artifact 12578346624 SHA-256
  `2f1ff404f691a6d15e2b60f3b56322e3fc7feca9a1dec194090036c91dc3de51`;
  [retained failure](evidence/native-child-start/dev30-family-failure.json).
- Foundation artifact 12578196957 SHA-256
  `fcc609f365a7f3004ddcf2d8e10cbabe69a1c3bb9fc78f74fd33f61542d32ffa`;
  129 source hashes; [receipt](evidence/native-child-start/dev30-foundation.json).

Dev31 local: **41 member tests and 68 existing control/child tests passed**,
with two mandatory hosted peer controls excluded from the selected suite.
The preceding full dev30 local run passed 486 tests with three hosted controls
excluded. Ruff/format/mypy and isolated installed dev31 wheel/version/CLI pass.
Hosted dev31 must pass **490 tests without skips** plus the unchanged native
21-member/41-PID/42-event, durable roster and real stale-controller HTTP-403
oracles. All eleven full release gate groups remain false.


## Dev31 exact-source native and hosted confirmation

At **9de50ea9f9971aefcea0fffd6c306485bc2410e6**, PR **40141633927** and push
**40141630301** passed all eight service/native jobs. Portable PR 40141633920
passed. Foundation completed **490 tests with zero failures/errors/skips**.
The final local suite completed **487 tests**, excluding the same three
mandatory hosted Linux controls. No native C++ changes were needed for the
zero-index compatibility correction.

The actual family completed **21 final RUN consumptions, 21 exact local PID
bindings, 21 original durable member rows, 11 children, 41 PIDs and 42 lifecycle
events**. The isolated Context B probe again received real **HTTP 403** at
Executor consumption after controller disconnection, with no consumption
receipt/body execution, unchanged native PIDs and retained original owner,
epoch and holds. Its one original durable member stayed recorded. Member rows
remain REGISTERED_UNPROVEN; this does not establish independent host attestation,
full family quiescence or positive transfer. Native DSS separately completed ten
commands and fifty matching ACKED stages in each ledger.

Verified ZIP digests, CRCs and exact public inputs:

- Foundation 12578414448 SHA-256
  `7da597549b544cb34f70cef67ac024bc862339462ad59a171920419d4aa7ee8f`;
  129 source inputs; [receipt](evidence/native-child-start/dev31-foundation.json).
- Family 12578584223 SHA-256
  `a366158ad4ac689931b8c2ddc96edc90151d4a4732139b42269a084398f555ed`;
  30 repository and all 144 compiled native source inputs;
  [receipt](evidence/native-child-start/dev31-family.json).
- DSS 12578229302 SHA-256
  `d1dbafef8f02ee14ec14ee195f93c7b36eeefe581c7f45d0a4cde05d2707af03`;
  95 source inputs; [receipt](evidence/native-context-dss/dev31-dss.json).

The failed dev30 native result and before/after zero-instance tests remain
retained. Interactive commands beyond initial RUN must obtain a fresh explicit
owner-admitted grant; extending the worker's StartGrant into general controller
permission would be a confused-deputy error. Complete native mutations,
command/prompt queue settlement, all-participant pause and explicit new-owner
resume remain prerequisites for full handoff and public Run/Debug. All eleven
full release gate groups remain false; no merge, tag, release or production
migration occurred.


## Dev39 native Context error-field interoperability

Both dev38 services workflows failed their family profile: PR 40156748754
and push 40156745123. Other seven service/native jobs and the PR portable subset
passed. The downloaded PR family artifact 12585320877 passed CRC and SHA-256
`0c16f07a211ba78c44e3cc295c43c32dba34fe1d981ec309f697217b535bcbb8`;
all 35 recorded repository input hashes matched exact code 8bc0fcac7741c6813bd2758bd938735eecc62017.
It contains ten ready root Executors and the first foreign GUI login denial,
then `Host operation failed: docker`. It is failed evidence. The retained
Context SSLEOF startup diagnostic preceded successful startup and is not the
terminal failure of this probe; the separate dev37 startup failure remains
unresolved.

A generated-response regression reproduced empty denial details: literal
`Error`/`Reason` fields are outside the frozen native bridge's FIELD inventory.
Changing to the original `ErrorMsg`/`ErrorReason` constants and nonfatal flag
passes that same compiled branch plus actual Python bridge reader. The first
test harness draft selected the earlier key-query branch and failed compilation;
that extraction was corrected before reproducing the intended protocol failure.
No native pass is claimed from either local message-shell test.

Final focused GUI/Executor checks passed **63 tests**, warnings as errors.
Ruff/format/mypy and the isolated installed dev39 wheel/version/service CLI
smoke passed; all 18 wheel module bytes match source. The full local suite executed 632 cases: **629 passed and three failed**
because this environment forbids AF_UNIX sockets and the process-memory-read
positive control. These mandatory hosted security controls are unchanged and
are not counted as local passes. Original native hosted confirmation is pending.
The failed dev38 artifact's 144 compiled source units and seven candidate headers
were independently verified using the frozen image's own provenance. Initial
reconstruction with repository recipes matched 142 units; the two legacy
comparison units require the exact frozen syntax helper and then match. No
frozen v0.7 file is edited. All eleven mandatory full
release groups remain unqualified, public runtime disabled and no release.


Reinspection of dev37 failed artifact 12584023613 (verified ZIP SHA/CRC)
corrects the earlier causal interpretation: its retained Context SSLEOFError
preceded successful readiness. Two roots reached native-ready; worker 2 had
root admission and one registered member, then timed out at native LOADED.
The terminal startup cause remains unresolved. The historical failure receipt
now explicitly distinguishes the recovered diagnostic from that failure.


## Dev39 hosted outcome and dev40 completion-audit candidate

Dev39 c4411d3 passed hosted **632 service tests**, zero failures/errors/skips,
installed package checks and **241 portable tests**. All 139 foundation input
hashes and archive SHA/CRC matched. Both service workflows failed the family
job later: the corrected native GUI boundary passed all five foreign requests,
two proposed-key denials and nonreuse; the 41-PID family consumed 11 children,
but worker 0 had three starts and only two durable finishes. The original
19-operation/18-management/eight-roster and owner probes were not reached.
The failed artifact SHA/CRC, all 35 repository and 144 compiled inputs match;
see dev39-family-failure.json. This is a failed overall component run.

The original controller publishes terminal FINISHED in setStatus before
setEndTime emits its synchronous finish audit event. The worker previously
announced completion and killed the native processes/relay as soon as it read
that status. Dev40 retains them while waiting at most five seconds for real
Context-acknowledged start/end events for every currently admitted member.
The same original EV requests and exact authority receipts supply the counters;
no event is created, replayed or inferred from status. Duplicate/absent receipts,
unknown substitutes, 65-member/130-counter capacity and deadline failures remain
failed evidence. Notification pumping continues during that bounded wait.
This audit settlement is neither participant closure nor quiescence, command
queue disposition, safe reuse, transfer or a full-family qualification.

Eight regressions exercise delayed committed completion, the actual worker
completion statements, missing nested receipts, foreign events, duplicates and
bounds. The actual dev39 worker statements reproduce early completion; the
corrected focused GUI/Executor/lifecycle suite passed **71 tests**. Initial
new-test lint rejected a lambda assignment; it was corrected before final
checks. Full scoped and original native confirmation are pending.


Dev40 final local run executed **640 tests: 637 passed and three failed** on
the unchanged Unix-socket/process-memory security positive controls blocked by
this environment. All 140 recorded source hashes match committed candidate
ce6daedf7c3cfb5698a7dfb7935c0b8523a843bb. Lint/format/types passed. The isolated
installed dev40 wheel version/service CLI and all 18 module byte comparisons
passed. Full hosted foundation/native confirmation is still pending here.


## Dev40 exact-source hosted confirmation

At ce6daedf7c3cfb5698a7dfb7935c0b8523a843bb, PR 40158609260 and push
40158606495 passed all eight service/native jobs. Foundation passed **640
tests**, zero failures/errors/skips, including all three mandatory Linux
security controls; all 140 source hashes and artifact digest/CRC matched.
Portable run 40158609322 passed **241 tests** without skips/errors/failures.

The verified family artifact 12585064798 passed SHA/CRC, all 35 repository
hashes, seven candidate headers and 144 compiled native source unit comparisons
using immutable runtime provenance. All ten workers waited for real lifecycle
acknowledgements: 21 durable members, 41 native PIDs, 11 consumed children,
42 unique lifecycle events (nested worker three starts/three finishes),
21 initial native RUN consumptions, 21 retained holds and ten spent workers.
The foreign GUI/key boundary passed; isolated original-Executor tests denied
19 mutations, 18 Context management requests and eight roster messages.
Stale initial RUN/owner STEP consumption returned actual HTTP 403; same-owner
RUN/PAUSE/RUN used three fresh grants. These are bounded components.

See dev40-foundation.json/dev40-family.json. Public runtime, full-family
quiescence/transfer, command queue settlement and full v0.8 remain false.
The separate LOADED startup reliability issue remains unresolved; a later pass
does not establish its cause. All eleven mandatory full groups remain pending,
and the clean dev40 publication preflight exits 1. No merge/tag/release.


## Dev44 paired installed IDE native control qualification

Executable candidate **`bd85c635d0cc3389425924face9eb0755be4eda2`**, paired
IDE **`cf0e9dd7581b283d63c98c95c46cdd368e005ac7`**, passed all **12 latest** jobs after one terminal-job rerun
in [workflow 40249941420](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40249941420).
The first terminal job (121339435097) failed before its matrix: ten child
admissions were consumed, but worker 1 recorded no child member-binding or
running event; all containers stayed live and no OOM was reported. The failure
artifact passed digest/CRC and all 119 source checks. A single unchanged fresh
repeat (121341159923) passed all sixteen terminal cases. Its pass does not
establish a cause or fix. The original failure and worker traces are retained
in `evidence/native-ide-controls/terminal-recheck-failure.json`.

The CI merge tree equals the executable candidate tree. Hosted CPython 3.13.16
passed **1,052 service tests**, zero errors/failures/skips, plus Ruff lint/format,
mypy and installed-package smoke checks. The separate IDE workflow passed
**258 tests with one Windows-only skip**; all 50 installed Python modules match
the pinned source. Local 230-service, 69-focused, 37-IDE and 11-supply checks
are overlapping regression suites, not additive full-qualification counts.

Three certificate-bound installed clients now control existing private native
executions through separate gateway/Listener processes. A accepts B's request;
the host freezes the same eight processes; B explicitly resumes and executes
Pause/Step/Run. Step changes the original native source position and pauses.
A's stale commands and driver packet are denied; C only observes. Both epoch
DSS commands have ten matching stage receipts. Terminal settlement exits the
original family and releases its holds while preserving the witness. Four
additional installed-client Abort/Close cases pass while paused/running. The
separate full native terminal matrix passes all sixteen cases; forced loss
remains unknown/held. The native cohort also passes 21 prompt generations and
ten independent DSS commands with fifty matching stage receipts per ledger.

Artifacts passed SHA256 and ZIP integrity checks; all 173 foundation and
119 native repository source hashes match the candidate. All 144 compiled-unit
hashes and ten candidate headers equal the previously verified terminal build;
the build inputs are unchanged. A fresh local reconstruction independently
matched 142 units; two legacy-comparison units require the original frozen
syntax helper and are recorded as continuity checks, not new reconstruction
passes. See [the exact component receipt](evidence/native-ide-controls/qualification-summary.json).

Compose and kind five-service prelaunch identity/CAS/isolation/restart, static
Kubernetes manifests and the development Python inventory scan passed. The
unpublished server package retains an explicit registry-audit exclusion. The
old dev43 wheel-name failure and strict local-audit version-reader failure are
preserved; neither is reclassified as a pass. The Step count correction changes
only the report value from two to three; the native Step oracle already passed.

This adds existing-execution native controls, not public provisioning or full
browser/debugger acceptance. All eleven full release gates remain false; the
clean dev44 publication preflight exits 1. No merge, tag, stable release or
production migration was performed. Current blockers are in
[RELEASE_READINESS.md](RELEASE_READINESS.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).


## Dev46 repeated ownership and native startup coverage

Executable candidate **`ed35c8d5e6f47ec3a05023c0be4937e300cb78cf`**, paired
IDE **`cf0e9dd7581b283d63c98c95c46cdd368e005ac7`**, passed all **13 first-attempt**
jobs in [workflow 40252610379](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40252610379).
The CI merge `cab899c7a6779b2ce8d2892d43e533949566ed8c` has exactly the
candidate tree. Hosted CPython 3.13.16 passed **1,065 service tests**, with zero
errors, failures or skips, plus lint, formatting, mypy and installed-package
smokes. All mandatory Linux controls executed. The local 212-test expanded
suite and 58-test focused suite overlap; local AF_UNIX is unavailable and local
mypy was not installed. They are not substitute hosted qualification counts.

The one-transfer limitation is removed within the private sealed-family
profile. Each subsequent transfer requires completed prior activation, settled
journals, new host proof and explicit owner resume. Schema 20 atomically archives
the preceding handoff and pause record with the next fencing transition.
Original member origin remains stable. Real mTLS tests execute eight transfers,
deny every earlier grant and host proof, and deny the ninth without revoking
the current owner. Lost second activation replies are never retried; stale epoch
markers stay fenced and audit failure rolls back history and fencing together.

Both native handoff and installed IDE cohorts execute **A→B→A at epochs 1/2/3**
using the same **eight original processes**. Root, child and background counters
remain stationary during both three-second host freezes, then advance after
explicit resume. Earlier A and B controller/native requests and the first host
proof are denied. Three actual native DSS commands have **15 matching ACKED
stage receipts per ledger**. The installed IDE verifies native Pause/Step/Run;
Step changes the original source position. Final host settlement verifies exit
of the original family, releases its holds, preserves the unrelated witness and
leaves the worker spent. The native eight-transfer limit itself has service/runtime
coverage; the original native cohort executes two transfers.

The installed IDE's four additional Abort/Close cases pass. The separate complete
native terminal matrix passes all **16 cases**, including forced loss remaining
unknown/held. The new startup-stress profile executes **24 additional fresh
root/child families** after the ten-worker cohort. Each has fresh Context state,
credentials and a single-use worker; both native members bind and execute, then
independent host terminal settlement releases only their reservations. No worker
reuse or failed-operation retry is added.

Startup observations were added at `d1494291d1085f9b77fc110fa8a4de09207fe097`,
whose 12 jobs and 1,060 hosted tests passed. Repeated transfer first passed all
12 jobs at `83113624ff3853d3c4c802a50b48dad4f3703429` with 1,065 tests.
The final candidate adds the fresh-family stress workflow. Bounded fixed-stage
native markers and read-only process/task snapshots retain useful failure
evidence without reading argv/environment or changing timeouts, retries or
admission. The historical dev37 root-LOADED and dev44 admitted-child/no-binding
failures remain **unresolved**. These successful samples establish no cause or
fix. See [the diagnostic guide](NATIVE_STARTUP_DIAGNOSTICS.md).

Nine final artifact archives passed SHA256 and ZIP integrity checks. Every
recorded foundation source hash (**177**) and native-profile repository hash
(**121 per artifact**) matches the candidate. The installed IDE client hash
matches its unchanged pin. All eleven candidate native header hashes match;
144 compiled-unit hashes are retained per profile, and terminal/IDE/stress build
source identities agree. This checkpoint does not claim a fresh independent
local reconstruction of all compiled native units. Exact workflows, artifacts,
source inventories, handoff/settlement results and diagnostic indexes are in
[the component receipt](evidence/repeated-handoff/qualification-summary.json).

Compose and kind five-service prelaunch identity/isolation/CAS/restart, static
Kubernetes checks and the development Python inventory scan passed. They remain
prelaunch components. The unpublished server's registry-audit exclusion remains
explicit; native/OS inventory and independent implemented-system review are not
qualified. All eleven full release gates remain false. The clean dev46
publication preflight exits 1; no merge, tag, stable release or production
migration was performed. Full blockers remain in [RELEASE_READINESS.md](RELEASE_READINESS.md).


## Dev47 same-owner native reconnection

Executable candidate **`82dc4cb99201d2f96ff02b023331a6c32b0502f7`**, paired IDE
**`faf2052ba764cbc147ef05f261164853e08489c8`**, passed all **13 first-attempt jobs**
in [workflow 40256356289](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40256356289).
The CI merge has the exact candidate tree. CPython 3.13.16 passed **1,087 service
tests** with zero failures/errors/skips, Ruff, formatting, mypy and isolated
installed-package smokes. Mandatory Linux controls executed. The independent IDE
workflow passed **266 tests and one Windows-only skip**; all fifty wheel Python
modules match its pinned source. All four deployment/inventory workflows passed.

Two new reconnect regressions fail against exact prior commit `accb144` with
HTTP 409 `native_rebind_unqualified`, both before and after explicit session
close. They pass after the fix. The final local focused suite passed 139 tests;
45 local IDE client/Qt checks passed. These overlap hosted counts. A broader
local attempt was incomplete because grpc/protobuf were unavailable and its
available subset stopped with a runtime-library error. It is not represented
as full qualification; hosted evidence includes the complete mandatory suite.

Same-owner reconnection now requires a new authenticated connection, settled
native/prompt/effect journals, separate original-container host freeze proof
and an explicit resume. Schema 21 journals reconnection separately from
ownership claims. The owner and ownership epoch remain unchanged; connection
generation increments once. Old controller/runtime proofs remain denied, even
for a valid native packet with the same ownership epoch. Lost activation replies
are never retried. Eight transfers/reconnects share one capacity limit; audit
failure rolls back admission and history together.

Both actual-native and installed IDE cohorts retain the original **eight
processes** through A→B→A, then explicitly close A's session. Root, child and
background counters advance for three seconds while old mutations are denied.
The same family is frozen for three seconds and explicitly resumed with A still
owning epoch 3 at generation 4. A stale connection packet is denied; its fresh
same-payload counterpart succeeds. **Four DSS commands and twenty identical
ACKED stages per ledger** cover epochs 1/2/3 and generations 1/2/3/4. Final host
settlement observes original-process exit, releases only that family, preserves
the unrelated witness and leaves the worker spent.

The installed IDE also passes native Step and four Abort/Close cases; all sixteen
terminal cases and 24 fresh root/child startup/settlement cycles pass. Artifact
SHA256/ZIP integrity and all recorded repository hashes are verified, including
178 foundation inputs and 121 per extended native profile. Eleven native header
hashes match; 144 compiled-unit hashes per profile match prior source-bound
inventories. This does not claim a new local reconstruction of every C++ unit.

[The component receipt](evidence/native-reconnect/qualification-summary.json)
contains exact runs, artifacts, original counters, source inventories and wheel
verification. The explicit-session profile does not establish generic abrupt
network/controller recovery. Historical startup failure causes remain unresolved.
All eleven full release gates remain false and clean dev47 publication preflight
exits 1. No merge, tag, stable release or production migration was performed.


## Dev48 transport drain, concurrent observers and deployment image consistency

Executable candidate **`40f38fb10690652819b367eafd9695f3ad0c69ce`** retains server
**`0.8.0.dev48`** and the unchanged IDE pin
**`faf2052ba764cbc147ef05f261164853e08489c8`** (`1.2.1.dev3`). All **13 first-attempt
jobs** passed in [workflow 40258910955](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40258910955).
The CI merge and candidate trees match. CPython 3.13.16 passed **1,094 service
tests**, with zero failures/errors/skips, plus lint, formatting, mypy and isolated
package smokes. Two intermediate dev48 core workflows also passed all thirteen
jobs; their separate kind failures remain recorded.

The `5ec9429` follow-up failed native handoff, native IDE and startup stress.
The first two failures respectively captured an old-epoch native status query
and suspended a command-poll TLS exchange across host freeze. Dev48 adds an
explicit loop-boundary transport drain before freeze. Counted outgoing RPCs
finish, new RPC admission is held, and only a new one-shot activation can resume
the agent. A lost activation response is never retried. The drain explicitly
reports `quiescence_proven: false`; independent host freeze, original pidfds and
settled journals remain required.

Both native and installed-IDE profiles record three distinct drain events with
zero active RPCs. They preserve the original **eight processes** through A→B→A
and same-owner reconnect, retaining epoch 3 and advancing connection generation
to 4. Four DSS commands have **twenty matching ACKED stages per ledger**; stale
packets remain denied. Native Step, four installed-IDE Abort/Close cases, all
**sixteen terminal cases** and **24 fresh root/child startup-and-settlement
cycles** pass. These new samples do not establish the cause of historical
root-LOADED or child-binding failures.

Twenty separately authenticated installed IDE clients now concurrently read ten
native executions. Every client is denied controller access, fails closed during
Listener SIGKILL, then reconnects to the same execution identities. All **thirty
native PIDs**, Context identity, owners/epochs and reservations remain unchanged;
all ten procedures advance during the outage. This is an installed-client
component, not browser/WSS, endurance load or full Compose workload acceptance.

The startup-stress cleanup path previously overwrote the primary exception with
a directory-removal error. It now retains the first error and separate cleanup
failures, attempts all removals, and preserves potentially live bind-mount state
when container removal fails. Native admission failures retain bounded
status/code/cause categories. Focused local checks passed **20 tests**. A broader
local attempt passed 87 and failed two existing exact Unix-peer identity tests
at `socket.connect` with the environment's `PermissionError`; hosted Linux
executes those tests without skips. Local counts overlap hosted results.

Kind initially loaded a dev47 image while the manifest requested dev48, so
Context rollout timed out before runtime probes. The workflow now builds and
loads both tags from the renderer's image definitions. The corrected
[kind workflow 40258910971](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40258910971)
passes service probes and persistent-state restart checks; its retained status
shows all five workloads ready with the intended images. Bounded status capture
now precedes cluster deletion and excludes logs, environment and Secret data.
Compose prelaunch, Kubernetes static and Python inventory workflows also pass.
The development package's registry-audit exclusion remains explicit.

Seventeen final archives pass SHA256 and ZIP integrity checks. Every recorded
repository hash matches the candidate, including 180 foundation inputs and 121
per extended native profile. Eleven native header hashes match; the 144-unit
compiled-source inventories agree with the prior source-bound checkpoint. This
does not claim a fresh local reconstruction of all C++ units. Exact artifacts,
drain records, native/observer results and failed attempts are in
[the component receipt](evidence/native-handoff-drain/qualification-summary.json).

The clean dev48 publication preflight exits 1. All eleven full-release gates
remain false: startup reliability, wider native/driver/controller faults,
all-763 compatibility and original archival captures, public launch/full
debugger/browser/WSS/Git, full deployed recovery, a production-like cluster,
independent implementation security review, native/OS inventory and stable
packaging remain unqualified. No stable publication or production migration
is justified by this component checkpoint.

## Dev49 untimed prompt handoff and installed-client transport

Executable **`dc66d32cab359b8d5b471b7fa983b834e0f68e22`**, server **0.8.0.dev49**, and unchanged paired IDE **`faf2052ba764cbc147ef05f261164853e08489c8`** passed all **13 first-attempt jobs** in [workflow 40261890283](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40261890283). Candidate and CI merge trees match. CPython 3.13.16 passed **1,119 service tests**, zero failures/errors/skips, plus lint, formatting, mypy and isolated package checks.

Both actual-native and installed IDE profiles preserve the same unanswered exact-zero-timeout prompt across host freeze and activation. Original prompt ID, family origin, member binding, target and definition digest remain unchanged. B is denied before explicit resume; A and observers remain denied afterward. Exactly one fresh B reply produces native ANSWER_SELECTED. The reply journal retains CONSUMED_UNPROVEN while the separate prompt row records the selected outcome. No old reply grant is rewritten. Timed/unclassified and queued/uncertain cases remain blocked; races are covered by real authority tests.

The installed IDE uses its pinned authenticated request transport through the private Listener authority operation. This is not prompt GUI or browser qualification. Existing three transport drains, eight original processes, A→B→A, same-owner reconnect, native Step and twenty matching DSS stages remain verified. Four IDE terminal cases, the sixteen-case terminal matrix, twenty-four fresh startup/settlement cycles, and twenty distinct observers across ten live executions also pass. Historical startup failures still have no established cause.

Two earlier candidates each finished with eleven passing and two failed core jobs. Their four native failure artifacts retain exact hashes and source inventories: the first exposed the missing IDE transport path; three reached native answer selection before an incorrect fixture expectation required CLOSED_UNPROVEN instead of preserving consumed provenance. The corrected assertion still independently requires native ANSWER_SELECTED and exact current-owner provenance. No failed attempt is relabelled successful.

Local runs cover **228 distinct passing cases**, overlapping each other and hosted tests. Local mypy was unavailable; mandatory hosted type checks passed. Seventeen final artifact SHA256/ZIP checks pass. All recorded repository hashes match, including **182 foundation inputs** and **121 per extended native profile**. Eleven native headers and 144-unit compiled-source inventories agree with the prior checkpoint; no fresh local reconstruction of every C++ unit is claimed. Compose, kind, Kubernetes static and Python inventory workflows pass their bounded scopes, including the explicit development-package registry-audit exclusion.

[The component receipt](evidence/native-prompt-handoff/qualification-summary.json), retained failures and native-build inventory bind these results to exact sources. The clean [dev49 publication preflight](evidence/release-readiness/publication-preflight-dev49.json) exits 1. All eleven full-release gates remain false; no stable publication or production migration occurred.

## Dev50 native admission transport and full available component recheck

Executable **`e5198820b938ae47421c20062ceccd1b6a98f24c`**, server **0.8.0.dev50**, passed all **13 first-attempt jobs** in [workflow 40264114884](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40264114884). The candidate and CI merge have the same tree. Hosted CPython 3.13 passed **1,141 tests**, zero failures/errors/skips, plus lint, formatting, mypy and installed-package checks. The pinned IDE remains `faf2052ba764cbc147ef05f261164853e08489c8`, v1.2.1.dev3.

The original admission wait failed two compiled real-signal regressions after about 10 ms. The corrected transport resumes only interrupted/transient calls on the same socket and original byte offset under the original four-second deadline. All **eleven compiled transport cases** pass in hosted Linux: readiness, signal-storm deadlines, successful replies, partial I/O with EINTR/EAGAIN, peer mismatch, denial, lost replies and size limits. No reconnect, semantic retry, authority refresh or timeout increase was added. Local Unix sockets are unavailable; all those hosted tests remain enabled. Local runs contain **171 distinct passing cases**, overlapping hosted tests; the two pre-fix failures are retained.

The dev49 evidence-only follow-up at `5bde4fd` was twelve passing jobs and one native-prompts failure. Workers 2 and 3 completed server-side member binding but ALLOW delivery hit BrokenPipeError; native traces did not reach member-bound. Its artifact SHA256, ZIP integrity and 121 repository inputs were verified. This historical cause remains unproven; the signal reproducer is not attributed to it. New fixed-label numeric diagnostics distinguish native transport reason/timing from worker dispatch/reply timing without logging packets or credentials.

The available native and installed IDE profiles pass again: unanswered exact-zero-timeout prompt handoff, eight original processes through A/B/A and reconnect, three drains per profile, four DSS commands with twenty matching stages, native Step, four IDE terminal cases, sixteen terminal cases, twenty-four fresh startup/settlement cycles and twenty authenticated observers across ten live executions and thirty unchanged PIDs. Historical startup failures remain open.

Compose, kind, static Kubernetes and Python supply-chain workflows pass their bounded scopes. Seventeen artifact digests/ZIPs and all recorded source hashes were checked. Twelve admission headers match; 144-unit compiled-source inventories agree with the preceding checkpoint. No independent local reconstruction of all native C++ units is claimed. Supply-chain results retain the development-package registry-audit exclusion.

[The component receipt](evidence/native-admission-channel/qualification-summary.json) binds the results and retained failure to exact sources. The clean [publication preflight](evidence/release-readiness/publication-preflight-dev50.json) exits 1. All eleven full-release gates remain false; no stable publication or production migration occurred.


## Dev51/dev52 paired desktop reconnect and completed-session cleanup

IDE **`1ac0b8ae9a8412f1f34135af3dd9d1b749f53f1e`**, **1.2.1.dev4**, corrects stale cached controller proofs hiding Reconnect control and live reconnect reusing a closed session. It opens a fresh authenticated session and retains prior sessions used by other executions. Explicit Disconnect closes all known sessions with independent stable close keys. Three local regressions failed before the repair; **51 focused client/Qt cases** pass afterwards. The [complete IDE workflow](https://github.com/arcazj/openbexi_ide/actions/runs/40264995293) passes **272 tests with one Windows-only skip**. Artifact integrity and all fifty wheel Python modules match the pinned source.

SPELL dev51 **`b935fd3e0800945bca66a4860bad4cc53f8ef9ac`** then exposed a second failure: the actual Qt/TLS test reconnected and requested resume but Disconnect could not acknowledge the already-closed original session with a fresh cleanup key. Its 1,142-test result has 1,141 passes and that one failure. Dev52 **`1a3f51f8b10e1f333bcd73f007c3f8d2b18095cc`** requires the original subject, current permission, inactive session and original durable completed-close receipt before acknowledging fresh cleanup. It never repeats fencing or adopts a pending close under another key, including after authority restart. Two focused pre-fix regressions failed; **106 local authority/contract/control cases** pass after repair.

At dev52, [workflow 40265747097](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40265747097) passes **all 1,144 service tests**, including the unchanged Qt reconnect/disconnect test, with zero failures/errors/skips. Lint, format, mypy and package checks pass; candidate and CI merge trees match, and all 185 foundation source inputs match. The Qt test uses a host-evidence service fixture, while native IDE/handoff/prompt/child and 24-family startup profiles independently pass. The full core run is **failed: twelve of thirteen jobs pass**. Its native terminal cohort stops before child admission with ten uncertain DSS command calls and twenty ACKED stages. No new terminal case matrix is qualified by that failed job. All four deployment/inventory workflows pass their bounded scopes.

All seventeen artifact digests, ZIPs and recorded repository hashes were checked. The failed native artifact has 122 verified source inputs. [The retained checkpoint](evidence/ide-reconnect-sessions/dev52-qualification.json) and [original failure report](evidence/ide-reconnect-sessions/dev52-native-terminal-result.json) preserve this result. The timeout cause is unestablished. A local ten-stream SQL durability-only diagnostic with a synthetic write sink completed within 439 ms; it did not exercise actual sockets/native processes and cannot establish the hosted failure cause.

## Dev53 DSS failure diagnostics and bounded suite budget

Executable **`5c162f0214163820267e0741d65e5dd68ac22402`**, server **0.8.0.dev53**, records fixed phase/stage labels and bounded numeric durations for command failures. It distinguishes preparation, metadata, connection, authority/deadline checks, send admission, receipt waits and settlement. Exception messages, payloads and credentials remain excluded. The native report now retains per-stage ledger state counts. Existing deadlines, live authority checks, durable journals and no-replay behavior are unchanged. Five deterministic diagnostic cases and all 45 authority tests pass locally; these overlap hosted coverage.

The initial dev53 run passes all twelve native jobs, including sixteen terminal cases and twenty-four fresh startup/settlement cycles, plus 241 portable checks and all four ancillary workflows. Its service suite reached 1,003 passing progress markers and no failing/error marker before the old 300-second harness cap terminated it without a final JUnit. This is retained as [failed evidence](evidence/ide-reconnect-sessions/dev53-foundation-timeout.json), with [the initial checkpoint](evidence/ide-reconnect-sessions/dev53-initial-checkpoint.json). The preceding 1,144-case suite took 270.94 seconds.

Harness candidate **`d01fc30a114e0f45978b2771493917aea16269b1`** keeps the same dev53 runtime and adds a finite 600-second suite budget with a 15-minute foundation job. Operation deadlines, assertions, supported SQLite DELETE/FULL durability and no-replay rules remain unchanged. Three qualification-runner failure/timeout-retention checks pass locally. The [fresh full available qualification](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40267235234) passes all **thirteen first-attempt core jobs** and **five ancillary workflows**. CPython 3.13.16 passes **1,149 service tests**, with zero failures/errors/skips, plus lint, format, types and installed-package checks. The separate portable subset passes **241 tests**, with 191 recorded source inputs verified. All 186 foundation source inputs match. The candidate and CI merge have identical trees. The clean [dev53 publication preflight](evidence/ide-reconnect-sessions/publication-preflight-dev53-final.json) exits 1: all eleven full-release gate groups remain false. No stable publication, merge or production migration occurred.

The final native and installed-IDE profiles retain eight original processes through A/B/A and explicit same-owner reconnect, an unanswered untimed prompt and twenty matching DSS stages for four commands. Four installed-IDE terminal cases, the sixteen-case terminal matrix, twenty-four fresh startup/settlement cycles and twenty authenticated observers across ten advancing executions and thirty unchanged PIDs pass. All eighteen artifact digests and ZIP integrity checks pass; every recorded repository input matches the exact candidate. Twelve native headers match and the 144-unit compiled-source inventories agree with the prior source-bound checkpoint; no fresh local reconstruction of all C++ units is claimed. Python registry-audit exclusions remain explicit. [The final receipt](evidence/ide-reconnect-sessions/qualification-summary.json) binds these results. Historical DSS deadline and native startup failure causes remain unestablished; later passing samples do not close them.

## Dev54 controlled fault reproduction and deadline/readiness repairs

Candidate **`11823881f0c1c5daf770611687ae21ce41aec271`**, server **0.8.0.dev54**, paired
with unchanged IDE **`1ac0b8ae9a8412f1f34135af3dd9d1b749f53f1e` / 1.2.1.dev4**,
passes [run 40273133915](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40273133915) and all five ancillary workflows.
The fourteen core jobs include a new 37-case fault suite.
**1,175 service tests**, **37 overlapping fault probes**, and **241 portable
tests** pass with zero failures/errors/skips. These overlapping counts are not
additive full-qualification coverage. Lint, format, types and installed package
checks pass.

The compiled late-readiness probe fails before the native correction and passes
afterward. Original native admission remains four seconds. Real worker
mTLS/SQLite/DSS probes distinguish writer/commit delays from uncertain receipts,
retain holds and deny retries under both old and new keys. Compiled Unix-client
probes reproduce dropped/delayed replies after durable binding; their native
peer roles/process pins are explicit fixtures.

Initial candidate `fb04f3d` passed all fourteen core jobs, 1,170 service tests,
37 fault probes and 241 portable checks, but kind failed with Context B HTTP 503.
[That attempt](evidence/fault-reproduction/initial-attempt.json) remains failed
overall. Readiness had checked only Context A. The correction requires both
Contexts within the same original 65-second budget, never retries mutations,
and retains immediate TLS pin failures. Docker/Compose/Kubernetes version
markers also now match dev54. Five deterministic regressions have four failures
before repair and five passes after. Final Compose and kind before/after restart
checks pass; B's underlying transient 503 cause is not inferred from this repair.

Native profiles retain eight original processes through A/B/A and reconnect,
an unanswered untimed prompt and twenty matched DSS stages for four commands.
Four installed-IDE terminal cases, sixteen terminal cases, twenty-four fresh
startup/settlement cycles and twenty authenticated observers across ten advancing
executions and thirty unchanged PIDs pass. All nineteen artifact digests and ZIP
checks pass. All recorded source hashes match the exact candidate and CI merge
trees agree. Twelve native headers are verified, including the changed
`admission_channel.H`; the 144-unit C++ inventories match the prior recorded
source inventory, without claiming fresh local reconstruction. Python registry
audit exclusions remain explicit.

[The final receipt](evidence/fault-reproduction/qualification-summary.json) and [fault report](FAULT_REPRODUCTION.md) preserve
the source identities and limits. The release preflight exits 1, all eleven
full-release gate groups remain false, and no merge, stable release or production
migration occurred. Historical DSS deadline and native startup causes remain
unestablished.

## Dev54 DSS lifecycle qualification follow-up

Exact candidate **`f1ea0337c89838a637c5e58896aaae09994be86c`** changes only test/harness inputs from the
qualified dev54 runtime. The paired IDE stays **`1ac0b8a` / 1.2.1.dev4**.
[Run 40275195710](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40275195710) **fails overall**: twelve of fourteen first-attempt
core jobs pass; native terminal/startup jobs time out in the initial child
cohort. All five ancillary workflows pass. **1,193 service tests**, **55 overlapping fault probes**
and **241 portable tests** pass without failures/errors/skips. Lint, format,
types and installed-package checks pass. All nineteen archives match GitHub
digests, ZIP integrity and recorded source hashes; candidate/CI merge trees agree.

The eighteen new cases exercise three failures after each of five real DSS stage
commits, restart on the same database/endpoints, scenario-reset refusal and ten
independent execution grants. Original Context/driver receipts and uncertainty
holds survive; old/new-key retries cannot send. Exact ingress counts stay one
per admitted stage. Nine unaffected executions complete in 370 ms while
one RELEASE receipt stalls. This ten-grant case calls the real gate directly;
the single-execution lifecycle cases use actual worker mTLS. No new native
identity, Pod identity, broad network-partition or historical-cause claim is made.

The initial `3802e73` fault run failed with three failures and seven setup errors
from test-only unclosed SQLite readers. The corrected helper explicitly closes
the readers and reaps failed children. [Original failed evidence](evidence/dss-lifecycle/initial-attempt.json)
and its JUnit/logs remain retained; no warning suppression or timeout relaxation
was used. [The final receipt](evidence/dss-lifecycle/qualification-summary.json) and [lifecycle report](DSS_LIFECYCLE.md)
record the full result. Native/IDE handoff/reconnect, four IDE terminal cases
and twenty authenticated observers pass. The separate sixteen-case terminal
and twenty-four-cycle startup profiles never reach those scenario cases in
this run. [Their failure receipt](evidence/dss-lifecycle/native-blockers.json)
retains four late binding replies and one fork-to-login stall; causes remain
unproven and no failed operation is replayed. The release preflight still exits 1:
all eleven full-release gate groups remain false, with no merge or publication.

## Dev55 controller/network and native spawn qualification

Exact candidate **`81b8b41be71a3420241ed8163535e65518987226`**, server **0.8.0.dev55**, with unchanged
IDE **`1ac0b8a` / 1.2.1.dev4**, passes [run 40278694435](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40278694435):
**1,210 service tests**, **71 overlapping fault probes**, **241 portable tests**,
fourteen core jobs and five ancillary workflows. The three suites have zero
failures/errors/skips; their counts overlap and are not additive. Lint, format,
types, development package and installed CLI checks pass. All nineteen archives
match GitHub SHA-256, ZIP integrity and recorded source inventories; the candidate
and CI merge trees match. No standalone full IDE suite is newly claimed.

Seven new real TLS cases retain the durable fence after lost close/rebind replies,
preserve uncertainty after lost activation and refuse automatic recovery from a
blackholed transport. A real client PID is killed after close commits. Host proof
in these fault cases is a fixture; abrupt death before close is not automatically
detected by the current protocol. The [recovery report](CONTROLLER_NETWORK_RECOVERY.md)
states this remaining blocker explicitly.

Nine compiled checks compare the exact frozen composed spawn method with the
actual patched method. An inherited atfork callback stalls the original child;
posix_spawn completes. Shell, environment, descriptors, current directory, parent
and child identity, exit/signal status and ported signal unblocking are preserved.
The changed SPELLprocess.C source was freshly reconstructed locally and matches
hosted native compilation. Twelve headers match candidate sources; among the
144 compiled units only SPELLprocess.C differs from the prior corresponding
composition. Historical CI causes remain unproven.

Native profiles pass eight-original-process A/B/A handoff/reconnect, twenty matched
DSS stages, sixteen terminal cases, twenty-four fresh-family cycles, four
installed IDE terminal cases and twenty authenticated observers across ten
advancing executions and thirty preserved PIDs. Bounded admission phase timings
are retained for future binding-deadline diagnosis. Original admission and
driver deadlines remain unchanged.

The initial `d86c9ed` attempt rejected an unported source preimage in six native
builds and twenty-one full-suite fixture setups; two diagnostic assertions also
expected the old one-record output. The corrected `bf9e6bb` fault tests all
passed (71/0/0/0), but its harness still required 69 and its two old diagnostic
assertions remained failing. A third failure exposed the polling handoff test reading
an invalid epoch during an in-place rewrite. The final test-only correction uses
the native host atomic replacement pattern, with a deterministic before/after
regression and no production deadline or read validation change. [Initial](evidence/controller-network/initial-attempt.json)
and [second](evidence/controller-network/second-attempt.json) failed results and
JUnit/logs remain retained. The final correction requires exactly 71 cases and
checks both diagnostic records; no failure is relabelled or warning suppressed.

[The source-bound receipt](evidence/controller-network/qualification-summary.json) records the component result and limits.
The publication preflight still exits 1: development version, all eleven full
gate groups unqualified, no merge/tag/release or production migration.


## Dev56 automatic controller liveness — 2026-10-25 Pacific/Honolulu

1,234 service tests, 95 overlapping fault tests and 241 portable tests pass with zero failures/errors/skips. All fourteen core jobs and five ancillary workflows pass. The paired IDE passes 282 tests with one Windows-only skip. Nineteen server archives plus one IDE archive, source inventories and wheel contents are verified. All eleven full-release gates remain unqualified.

Candidate `bad5f984e5be852dba70ed959fa73203d16b5639` and IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` match their tested merge trees. Four TLS cases kill the client or disrupt heartbeat delivery before any explicit close; native and installed-IDE cohorts preserve eight original processes and require host-proven resume. The unchanged C++ composition matches dev55 (144 units and twelve admission headers). High cgroup memory pressure and late native-binding replies remain open; earlier failed attempts are retained. No full release gate was promoted. [Source-bound receipt](evidence/controller-liveness/qualification-summary.json); [workflow](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40283981575).


## Dev68 bounded message allocation follow-up — 2026-10-27 UTC

Executable candidate **`2972f5fbd5c7c6c54478dfe4ad70c687fdc72c0d`** has tree
`4a9cd8a1bd9852780fb8cc52a5d2e020bdc05b42`, identical to tested merge
`23d06c59690283299269efce21e58d6104e14dd8`. The IDE remains `c5edbda`.
[Core run 40537014171](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40537014171):
**12/14 core jobs pass; the two recovery memory jobs fail**. All five ancillary workflows pass. **1,512 foundation,
95 overlapping fault, 241 portable and 268 local regression tests** pass with
zero failures/errors/skips; these suites overlap and are not additive. Twenty-four
fresh root/child startup families and all sixteen terminal cases also pass.

The implementation retains at most 32 joined, cleared message processors and
32 empty collector nodes per process. Existing dedicated message threads and
request behavior remain. Read-only notification fields are borrowed only during
the synchronous callback; model setters retain owned copies. Component tests
measure 10,000 processor constructions falling to one, 2,500 collector-node
allocations falling to one, and at least 40,000 long-field copies falling to zero
after warmup. Concurrent, cancellation, exception, missing-field and ownership
regressions pass under ASan/UBSan. This does not establish a runtime memory fix.

| Current mandatory profile | Peak MiB | Growth MiB | Growth limit | Result |
| --- | ---: | ---: | ---: | --- |
| Original-family handoff | 1117.77 | 90.58 | 64 MiB | Fail |
| Installed IDE recovery | 1339.64 | 81.78 | 64 MiB | Fail |

Both preserve eight original processes and advancing counters throughout the
45-second window. Peak budgets pass. The separate diagnostic records
87.95 MiB growth and also fails resource acceptance;
its successful workflow means diagnostic evidence was collected. Sanitizers,
memory budgets, workload, deadlines and acceptance thresholds are unchanged.

Failed candidates remain retained: `70205ab` thread pooling measured
103.33/96.14 MiB handoff/IDE growth; `e0841d4` combined pooling and processor reuse
measured 70.58 MiB IDE growth, while handoff failed before measurement after a
5.38-second member-registration RPC. Its startup stress also timed out waiting
for a worker exit. `23dbec3` removed pooling and measured 75.47/83.67 MiB growth.
No historical startup cause is established. Initial local fixture compile errors
and their corrected 268-pass rerun remain in the evidence archive.

The earlier `1612600` optimized one-hour handoff/IDE runs preserve their families
but fail growth at 129.39/134.73 MiB. ASRUN output reaches 131,272,704 allocated
bytes on 134,217,728-byte tmpfs. Per-record completeness and durable audit storage
remain unproved; no records were intentionally discarded or moved out of memory
accounting. Current [comparisons/endurance](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40537014003)
are still running or queued, and are diagnostic profiles rather than full acceptance.

All **20 archives** match GitHub SHA-256 and ZIP CRC, and all
**16 recorded source inventories** match this executable candidate.
[The component receipt](evidence/message-allocation-20261027.json) binds source identities, jobs, metrics
and artifact hashes. Full all-763/native compatibility, deployed recovery/storage,
production-like cluster identity/security, public GUI/browser/debugger and stable
joint packaging remain incomplete. All eleven full-release gates remain false.
No merge, tag, release publication or production migration occurred.


# Measured Context callback follow-up — 2026-10-27

Remote PR #4 was verified open at documentation commit `db94cf61ef80a4a2d0212363993ed4e183b17896`; executable checkpoint `2972f5fbd5c7c6c54478dfe4ad70c687fdc72c0d` and paired IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` remain the last fully collected mandatory attempt. Its 90.58/81.78 MiB failures are preserved.

Eight newly downloaded five-minute comparison archives have matching GitHub SHA-256 digests and ZIP CRCs; 1,088 executed source hash comparisons and every recorded evidence digest verify. The tested merge has the same tree as the executable checkpoint. Sanitizer/O1 handoff and IDE grow 551.56/553.39 MiB; optimized comparisons grow 14.61/14.98 MiB. All are diagnostic profiles. Sanitizer/O2 and swap comparisons also fail growth; swap remains unused. Observed first/last thread medians remain 110. Last allocator records show about 9–10 MiB live in each active rebuilt native participant while retained heaps are much larger. These observations distinguish accounting classes but do not establish absence of leaks. File/shmem counters overlap. The one-hour jobs were still running at collection and require their actual final artifacts.

The sampled Context stack at executable offset `0x99ba5a` resolves in its recorded function inventory to `SPELLexecutor::processMessageFromExecutor`. Its owned message-ID copy is replaced by six synchronous in-place comparisons. No reference escapes, cache is added, callback is queued, request is changed or concurrency is limited. An exact method preimage rejects drift and duplicate application. A compiled original-versus-candidate harness covers every branch, error forwarding and concurrent independent callbacks; 10,000 notification calls allocate 10,000 ID strings before and zero afterward.

The opt-in allocation diagnostic now observes sampled frees using fixed storage and eight bounded pointer probes. Dropped allocation/free observations are explicit. A missed free invalidates earlier pointer generations to prevent attributing a reused address to an old allocation. Unmatched samples are conservative upper bounds, not proof of live objects. The single-thread compiled lifetime regression distinguishes held allocations from their subsequent frees. Numeric-only host parsing remains compatible with old receipts. No mandatory assessor, sanitizer configuration, resource limit, workload, deadline or sample selection changes.

Local component validation: 125 tests pass, zero failures/errors/skips. Local Python is 3.12.14 and cannot qualify the required CPython 3.13 native family. The first new component attempts requested LeakSanitizer, which fails in this container when it cannot inspect `/proc` task directories; those original failures are retained. The new component tests use the existing suite's ASan/UBSan policy (`detect_leaks=0`), with address/undefined-behavior instrumentation and fail-fast behavior intact. This is not a leak-acceptance result. Hosted native handoff and installed-IDE acceptance must run on the resulting commit.

Receipt: `evidence/memory-attribution-20261027.json`. All eleven full-release gates remain open. Durable ASRUN storage, unresolved startup failures, all-763 native compatibility, public UI/debugger/browser/Git, deployed failures/security and stable joint packaging remain mandatory blockers.


# Timestamp, record ownership and durable-audit component follow-up

The fully collected `c344dbb` mandatory attempt remains failed: handoff growth 86.29 MiB and installed-IDE growth 85.14 MiB, limit 64 MiB. Both keep the original resource limits and original-family workload. Its 1,516 foundation tests and 95 overlapping fault tests pass without failures/errors/skips. Core outcomes are 12/14; the two resource jobs fail. The checkpoint's previously outstanding optimized one-hour jobs now finish and fail at 127.86/127.32 MiB over 3,600.60/3,601.17 seconds. They retain stable observed thread counts and eight original processes. Handoff ASRUN reaches 131,272,704 allocated bytes on 128 MiB temporary storage; IDE ASRUN reaches 127,348,736 bytes. Successful control transitions do not prove audit completeness on the full temporary filesystem. These results supersede earlier pending descriptions, and preserve their failures.

The source-verified `65add6c` diagnostic uses DWARF stack walking only at sampled allocations, preserving the mandatory sanitizer options. It identifies remaining timestamp and ASRUN formatting copies and `SPELLipcMessage::requestId` peer/concatenation copies. Its sampled free observations support a transient-allocation attribution for the named paths, with explicit missed-free counters; this is not proof that every growth cause is resolved. The source-bound receipt is `evidence/qualification-resume-20261027.json`.

The new correction formats timestamps into caller-owned storage, preserving current-time reads and all original time formats. CIF owns the timestamp property while it is formatted. ASRUN retains only a small timestamp/sequence prefix, streams the existing payload directly and serializes each public record operation, including multi-record groups and resets. Retained prefix capacity above 1,024 bytes is released. No procedure/audit record is discarded. The request-ID method still returns a distinct owned string but avoids copied peer IDs and growing intermediate strings. No thread-pool, concurrency cap, artificial warm-up, swap use, sample omission, deadline or acceptance-limit change is introduced.

The compiled formatter checks 70 original-format cases, including signed integer extremes and fallback formats. Across 10,000 record operations, its original-versus-candidate allocation counter drops from at least 20,000 to zero after ordinary buffer initialization, with identical record bytes. It verifies 800 concurrent ordered records, exception unwinding, deterministic cancellation inside the record lock, a succeeding owner after cancellation and a large record without retained payload growth. The native codec harness retains original request IDs across peer strings, Unicode/NUL, keys and stored sequence boundaries and measures a single owned allocation per returned ID. These are component results; fresh whole-native handoff and installed-IDE acceptance remain mandatory.

A synchronous disk ASRUN writer, retained-generation behavior, explicit write/sync failure exit and a real ext4 ENOSPC/restart qualification workflow are prepared separately. The native builder does not activate that writer in this candidate. Its component tests cannot substitute for memory acceptance or deployed durable-audit integration. See `DURABLE_AUDIT_STORAGE.md`. No full release gate is closed and no stable publication is performed.


# One idle worker component candidate

`58e6f6c` native handoff still fails growth at 78.74 MiB against 64 MiB. Its named live-allocation counters remain nearly flat while retained free allocator memory and anonymous memory grow. The earlier eight-worker failure is retained. A controlled component comparison against the current processor cache now records 85,983,232 bytes of dedicated-thread heap growth versus 524,288 bytes with one idle reusable worker over all 10,000 callbacks from a fresh component process; live allocations finish 78,652/78,684 bytes. No initialization callbacks are excluded. A fixed thread-ID array avoids adding observation allocations during the comparison. Eleven ASan/UBSan component tests pass, including 24 simultaneous blocked callbacks, cancellation, requests, object reuse and listener rebind. No callback queue or concurrency limit is added. Joined pool tickets are reset before objects re-enter the existing cache. Requests and busy fallback remain dedicated threads. Fresh mandatory native and installed-IDE acceptance is pending; no full release gate is promoted. See `ONE_IDLE_MESSAGE_WORKER.md` and its source-bound component receipt.


# Mandatory memory pass and durable native audit activation candidate

At executable `7d716d970f3919a5b40fac16c035d75205d202a8`, PR core run 40554351561 finishes 13/14 jobs successfully. Foundation passes 1,554 tests with zero failures/errors/skips. Both **mandatory, non-diagnostic** memory jobs pass: controller handoff 63,899,648 bytes (60.94 MiB) and installed-IDE recovery 66,064,384 bytes (63.00 MiB), below 67,108,864 bytes (64 MiB). Peak use is 1,068,724,224/1,072,562,176 bytes. Durations are 45.57/45.58 seconds; all 47 samples are retained in each job. Sanitizers, deadlines, concurrency, cgroup accounting and the no-swap policy are unchanged. Their 136 recorded source hashes each verify against the candidate, and the tested merge has the exact candidate tree. Companion IDE remains `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. The passing diagnostic is separate and does not substitute for these jobs. The margin is narrow; every affected subsequent candidate must be retested.

The same run's listener-survival job fails with `Expected distinct real native Listener/Context/Executor`, before proving its native identity matrix. Its 72 source hashes and archive digest/CRC verify. Later startup/terminal passes do not explain this failure or the historical delayed-registration and worker-exit failures. All previous resource failures remain retained.

This follow-up activates durable disk-backed ASRUN and mounts a private retained host directory for every rebuilt native worker, including consumption probes and failed attempts. Each acknowledged record is synchronously written and synchronized; buffering is bounded. Prior generations and uncertain tails are retained. The unchanged whole-cgroup resource oracle continues to include charged file-cache pages. Raw byte hashes, completeness and sequence checks run after all worker teardown. The separately verified ext4 component run at `58e6f6c` reaches actual ENOSPC and explicit exit 74, preserves every acknowledged record and recovers after releasing only a disposable fixture reserve. Fresh native integration, full-disk/crash behavior and both mandatory memory jobs on the activated source remain pending. Local validation passes 157 focused component/integration-composition checks without failures/errors/skips, plus Ruff lint. Local CPython is 3.12.14; this does not qualify the installed CPython 3.13 native runtime.

Receipt: `evidence/memory-audit-activation-20261027.json`. All eleven full-release groups remain open. No stable merge, tag, publication or production migration has occurred.


# Durable native ASRUN acceptance and retained lifecycle failures

Executable `dbdfd539bea2cd61611bef6c43be00cbdefda321` with IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc` passes all 14 jobs in core run 40556778211. Foundation passes 1,554 checks without failures/errors/skips. The unchanged mandatory handoff and installed-IDE resource jobs pass at 60,911,616/60,895,232 bytes growth (58.09/58.07 MiB), below 64 MiB; peak values are 1,317,564,416/1,314,586,624 bytes, with no swap. The full 47 samples each are retained. Each verifies 137 source hashes, raw audit sizes and SHA-256 values; the handoff/IDE artifacts retain 23/27 native audit files totalling 2,791,280/2,584,826 bytes. No charged file-cache usage is subtracted. The run also passes 24 fresh startup families and 16 terminal cases.

Its independently collected real-ext4 disk component passes actual ENOSPC and explicit exit 74 with 2,467 ordered, uniquely numbered, acknowledged records (10,104,832 bytes) and restart; all recorded sources, raw retained bytes and compiled harness identity verify. This is a component disk-full result, separate from the actual native normal-disk integration above. Live full-native full-disk/crash/restore and long-duration qualification remain required.

The new local follow-up passes 122 ASan/UBSan component and diagnostic checks, including actual SIGKILL after 128 acknowledged records, recovery, actual SIGKILL between two controlled partial writes, preserved uncertain tail, append rejection and retained previous generation. Its first crash-fixture build failed Werror on an unchecked read; the fixture now checks that return value and the full affected suite passes. Raw failed and corrected logs are retained.

Failure reports now preserve the bounded call-site stack and observed native PIDs for identity mismatch. All profiles collect bounded read-only process/task diagnostics and native log tails before teardown. Three independent Listener-survival, startup and terminal attempts are scheduled without changing the native workload, deadlines, concurrency, sanitizer options or acceptance limits. No later success establishes the cause of the prior `7d716d9` Listener identity failure or historical delayed registration/worker exit. Repeated hosted outcomes remain pending. All eleven full-release groups stay open. Receipt: `evidence/durable-audit-native-20261027.json`.


# Actual native disk-full candidate

The new independent-host disk-full profile is implemented with the same native binary builder, original owner RUN/PAUSE/RUN grants, deadlines and worker isolation. It uses a dedicated 8 MiB ext4 loop filesystem, complete prefix snapshots, physical pidfd exit observation, bounded fixed audit stage/errno diagnostics and unchanged durable hold checks. It retains both raw prefix/final records and the entire image, including disposable fault filler and any uncertain tail. Its actual hosted outcome is pending. The affected local suite passes 182 tests without failures/errors/skips; descriptor copying/mutation/symlink refusal and diagnostics are separate from actual native full-disk qualification. The normal mandatory handoff/IDE profiles and their unchanged resource oracle run again on this candidate. Full v0.8 remains unqualified.


The first `cc443241` full-native disk probe fails before injection: `native-owner-paused` is not observed. The earlier ordinary owner-resume probe passed and deliberately left its release marker open; the new probe inherited the same control directory. A deterministic separate-process marker regression demonstrates premature continuation with that old directory and a held fresh execution with a new private control directory. The correction gives this separately admitted probe its own start/release markers. It preserves the earlier marker, all audit files, the complete 8 MiB disk image and the failed archive 12760693266. All 74 recorded source hashes and the archive digest/CRC verify. No ENOSPC or disk-full pass is claimed for that attempt; fresh hosted execution is pending. The affected local suite passes 183 checks without failures/errors/skips.


The next `929db846` actual-native attempt passes the corrected PAUSE boundary and preserves its 813-byte prefix, then fails in host fault setup before writing filler. Artifact 12762830814 has matching SHA-256/CRC and all 74 source hashes verify. Its retained 8 MiB ext4 image has 2,048 blocks, 1,156 overhead clusters and 4,096-byte blocks; no filler entry exists. The previous guard incorrectly treated usable filesystem capacity as physical image size. The replacement checks the exact 8 MiB regular backing file and a distinct mounted device, and accepts the smaller usable data area. Each disposable filler block is synchronized so delayed allocation cannot stand in for actual disk exhaustion. An independently approved fault-only continuation emits enough original LINE records to require a new audit block after resume, instead of possibly fitting inside the existing final block. Ordinary owner-resume and mandatory memory workloads are unchanged.

The affected local suite passes 188 checks without failures/errors/skips, including a recorded-metadata capacity reproduction, refusal to fill an unmounted host directory, explicit privileged-helper failure rejection and actual helper CLI byte preservation. Fresh actual-native ENOSPC remains pending. The optional memory-comparison workflow now serializes by branch without cancelling running experiments; superseded unstarted pending workflows contain no native samples. Mandatory per-commit CI and all acceptance oracles are unchanged.


# Verified native disk failure, fresh checkpoint and measured cache correction

Exact executable `3c1951ef0365ed4c1dc4dc56f39ffce0bca2e5a0`, tested merge `ae6214d429a4fabf3a193e81f82d46026d5ca858` with the identical tree, and IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`: [core run 40566308562](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40566308562) passes all 14 jobs. Foundation has 1,569 tests, zero failures/errors/skips; the separate 95 fault tests overlap. Handoff growth is 59,367,424 bytes (56.62 MiB), IDE growth 62,861,312 bytes (59.95 MiB), limit 67,108,864 bytes. All 47 samples each are retained; peaks 1,321,496,576/1,321,488,384 bytes. Both receipts verify all 139 source hashes and all 23/27 raw audit-file hashes. No memory accounting or acceptance limits changed.

[Repeated run 40566308457](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40566308457) passes all nine independent jobs: three Listener-survival attempts, 72 fresh startup families and three 16-case terminal matrices. Every recorded source inventory, audit-file hash and archive digest/CRC verifies. This does not explain the historical late registration, worker exit or earlier native identity failure. The prior ce6dfd1 repetition run also passed; neither erases failures.

[Actual native disk-full run 40566308362](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40566308362), artifact 12763427499, now passes actual native `stage=write errno=28`, original Executor pidfd exit, worker failure without false completion, unchanged owner/epoch, two retained holds and one spent worker. Its entire 8 MiB image, complete 875-byte prefix and 8,192-byte final uncertain tail are retained. Offline extraction from the image matches the final raw record SHA-256. No audit records were deleted. The component artifact 12763208370 separately passes 14 tests and actual ext4 ENOSPC/exit 74/restart with 2,466 ordered acknowledged records. A fresh writer process on copies of the actual native records rejects the incomplete tail without mutation and restores the complete prefix while preserving the uncertain generation. That last result is file-component evidence, not recovered execution authority, IDE or cluster state. The first two pre-injection failures remain unchanged in their receipts.

Completed hour comparisons have now been retrieved and source/overlay/evidence hashes verified: 58e6f6c handoff growth 130.61 MiB; 7d716d9 handoff/IDE 130.95/128.62 MiB; dbdfd53 durable-disk handoff/IDE 123.78/124.19 MiB. All fail the original 64 MiB growth criterion. These optimized profiles never replace mandatory sanitizer acceptance. The separate 58e6f6c IDE attempt ended early with `endurance_original_process_exited`, not a completed hour or a memory pass. Its missing process cause remains unresolved.

For the dbdfd53 hour, matching first/last windows show file growth 123,002,880/120,426,496 bytes, anonymous growth 3,022,848/4,038,656 bytes and retained audit output 122,190,068/119,952,764 bytes. The new correction synchronizes records, then asks the same filesystem to release only completed clean pages in 64 KiB batches. Required disk bytes, cgroup membership, sanitizers, concurrency, deadlines and the whole-cgroup oracle are preserved. Cache advice refusal is explicit failure. Restore retains its 4 KiB userspace buffer and releases consumed input/completed output pages. No global cache drop, record deletion or resource subtraction occurs.

The final paired ASan/UBSan component writes identical complete 64 MiB/1,024-record files: the prior writer retains 16,384 pages, the changed writer zero pages before verification readback. All bytes match; actual large restore, concurrency/order/restart, SIGKILL, uncertain tail, I/O failure and cache-policy-refusal checks pass. The affected local suite passes 157 checks with warnings as errors on CPython 3.12.14. An initial new wrapper fixture failed to compile because `%::` formed a C++ digraph; the corrected fixture and original failed JUnit are retained. This local result does not qualify the CPython 3.13 native runtime. Fresh mandatory handoff/IDE, native disk failure and separate original-sanitizer/no-swap one-hour jobs must run on the new commit; they are pending at this record.

`SPELL_COMPATIBILITY_MATRIX.md` now maps all 763 original IDs to four unchanged historical dimensions and 47 reports. The normalized JSON retains 555 distinct top-level source bindings. Nine paths differ or are absent at 3c1951e; nested raw recovery still has 57 unresolved hashes. Every current row remains NOT_FRESHLY_QUALIFIED. No historical/static/mock/portable result is promoted to fresh native acceptance.

Source-bound receipt: [audit-cache-native-checkpoint-20261027.json](evidence/audit-cache-native-checkpoint-20261027.json). All eleven release gates remain open. No stable merge, tag, release or production migration has occurred.


# Cache-only checkpoint failure and measured REQUEST worker correction

At exact `910c8418336f7d26d61e43d2e4035974a0abf5ef`, core run 40571287735 passes all 13 native/fault jobs and fails foundation: 1,572 tests, one deployment-version assertion failure, zero errors/skips. Package dev69 was inconsistent with three prelaunch marker files still at dev68. This introduced regression is preserved in artifact 12765549293 (SHA-256 `8dab799938db7dbb7b9d6c19cc719613741d2a876324707956bfb58f9ec9b748`), not waived. All markers, Docker label and package metadata are aligned to dev70 in this correction. The existing deployment-version and release-guard suites pass 17 local checks; the next hosted core must pass afresh.

The same exact source passes unchanged mandatory handoff/installed-IDE growth at 62,218,240/59,375,616 bytes (59.34/56.62 MiB), with 48/47 retained samples, peaks 1,306,595,328/1,312,636,928 bytes and all 139 source hashes each verified. Their 23/27 raw audit files match every hash. Native disk-full and the 17-test ext4 component pass; the complete native image is independently extracted and matches the uncertain final file. No required record is deleted. Nine lifecycle repetitions pass in CI, with raw receipt retrieval tracked separately. Both original-sanitizer/no-swap hour jobs remain in progress at this record and cannot be assumed successful.

Thirty-one further completed comparison artifacts are now downloaded and fully source/overlay/evidence/raw-audit-hash verified: eight diagnostic passes and 23 failures, without promotion to mandatory acceptance. In the durable five-minute sanitizer runs, the native Context and two Executors dominate heap growth; the five reported native IPC participants together retain roughly 30.3 MiB live while their reported mapped allocator heap reaches about 996 MiB; anonymous memory rises by roughly 0.5 GiB, with stable kernel stack/thread counts and much smaller file growth. This is distinct from the hour-long clean audit-cache growth. The sampled real Context paths include request-ID creation and `SPELLipcIncomingRequest::run`/GUI admission; the final reported top-site samples at those paths were freed, subject to the explicit bounded sampler limitations.

A paired request-thread component measures every one of 10,000 callbacks, with no excluded warmup: dedicated threads retain 85,852,160 heap bytes versus 393,216 bytes with one shared idle worker, live allocation totals 78,270/78,294 bytes. The full ASan allocator statistics and binaries are retained. This demonstrates a retention mechanism; it is not a full-runtime pass or proof of the historical lifecycle causes.

The new compilation shares the existing one idle worker between REQUEST and MESSAGE. A busy slot, nested request or thread-creation failure uses the original dedicated path without queueing or a concurrency cap. Request objects remain one-shot and are never cached. Cancellation preserves callback completion, join precedes disposal, and idle storage retains no payload, listener or ticket. All three original request allocation sites are in the rebuilt common-runtime inventory. Scoped legacy process/recursion TLS and unchanged CPython GIL guards were inspected; this is implementation review, not independent security approval.

The affected suite passes 127 component/strict-overlay checks. The final 11 request regressions overlap that set and add original collector disposal and exception completion; they also cover a nested synchronous request, 24 simultaneous blocked callbacks, cancellation/join and listener lifetime. Local CPython is 3.12.14 with ASan/UBSan compilation. Fresh exact-source native handoff, installed IDE, all lifecycle/core and original-sanitizer hours are pending. No acceptance limit, deadline, sanitizer, audit record or ownership check was removed. Receipt: [request-idle-worker-20261027.json](evidence/request-idle-worker-20261027.json). All eleven full-release groups remain false; no stable merge/tag/publication or production migration has occurred.


## 2026-10-27: dev70 bounded acceptance and failed sanitizer endurance

Executable `3a970c45718d9af7c7de553ea3d6508a9ec3d423` and tested PR merge `872026dee7700c4ca9765bd483603ad16fcf1b54` have identical tree `4ed64ec134f3a2d0ec9e2fd230f2c1918cc1fdf0`. Paired IDE remains `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. [Core 40574714388](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40574714388) passes all 14 bounded jobs and 1,583 foundation tests without failures/errors/skips. The 95 fault tests overlap. Original sanitizer/no-swap whole-cgroup handoff growth is 61,321,216 bytes over 48 samples; installed-IDE growth is 60,837,888 bytes over 47 samples, both below 67,108,864 bytes. Peaks are 1,324,302,336 / 1,063,411,712 bytes. All 139 source hashes each and retained raw audit files verify. Real rebuilt-native ENOSPC and 17 separate audit component cases pass; the complete 8 MiB fault image and all records remain retained. Sixteen core/audit artifacts verify 1,750 overlapping source bindings and 230 raw audit files.

[Repeated run 40574714317](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40574714317) passes all nine jobs: 72 startup families, three Listener attempts and three 16-case terminal matrices. All 1,059 overlapping source hashes and 324 raw audit files verify. Listener-survival uses the frozen original native image; rebuilt candidate profiles are identified separately. The historical 7d Listener failure therefore cannot be attributed to its new callback pool. Its actual cause, delayed 5,382 ms registration against a 4,000 ms deadline, and a 90-second worker-exit failure remain unresolved.

**Endurance remains failed.** Both 910c8418 original-sanitizer hours stop early with OOM kills. Current 3a970c45 handoff also stops early after 1,091.78 seconds of observation and 520 samples, with one OOM kill and 2,147,487,744 bytes peak. No completed growth receipt exists. Final file charge of 3,506,176 bytes includes 3,465,216 bytes shmem; anonymous memory of 1,196,376,064 bytes dominates after the loss. All 142 overlay-bound source hashes and 23 audit-file hashes verify. Current 3a installed-IDE hour is still pending at this checkpoint. All 38 historical longer comparisons are exact-overlay/source/evidence verified; the newly retrieved optimized hours and ASan-O2 comparisons also fail growth. Diagnostic profiles cannot replace mandatory acceptance. The earlier 58e6f6c optimized IDE early exit has no demonstrated cause and is not explained by these later OOMs.

The 910c8418 IDE OOM retains all 27 raw audit files, 33,149,716 bytes, with every evidence hash verified, including a 49-byte incomplete tail. The old collector rejected that tail before writing its manifest; this was an additional audit-retention validation failure. A corrected collector hashes and inventories all retained generations before failing validation, including oversized records with bounded reads. Eleven focused tests and twelve release-guard tests pass. Running it on copies of all 27 real files preserves every original byte/hash and explicitly rejects the incomplete tail. A fresh ASan/UBSan process using the unchanged 3a writer also rejects append with exit 74, then preserves the entire 17,022,828-byte uncertain generation when creating a new generation. No uncertain record is discarded or acknowledged. Native/IDE/cluster recovery remains unqualified.

Actual native callback reuse/fallback/concurrency counters are being collected on separate diagnostic branch `qualification/v08-callback-metrics` at `0b2fd53558b23f3cb8a5e3fb0f52b7215facba71`, leaving the PR runtime unchanged. The first 92f8c5cd diagnostic failed before native execution because the shallow checkout lacked baseline 3a970c45; six component tests passed, failed evidence is retained, and full history is now fetched. Further capacity optimization requires actual measurements.

Receipt: `evidence/memory-endurance-20261027.json`. All eleven full-release groups remain false; no stable merge, tag, release or production migration has occurred.


## Measured five-slot candidate

The separate callback diagnostic completes successfully at `0b2fd53558b23f3cb8a5e3fb0f52b7215facba71` (run 40579917700, artifact 12770300420). Its exact overlay, all 139 native inputs, four diagnostic inputs, all samples and 23 raw audit files verify. The Context observed peak is five active callbacks; its latest cumulative sample records at least 2,345 MESSAGE and 39 REQUEST dedicated fallbacks from one reusable slot. Latest snapshots can precede process exit and can capture an attempt before classification; these are observed lower counts, not complete final totals.

The candidate lazily reuses up to five idle workers, matching that measured peak. The original immediate dedicated fallback remains, with no queue, concurrency ceiling or deadline change. Thirteen nested requests and 24 simultaneously blocked callbacks complete. A controlled ASan/UBSan component replays all 10,000 callbacks in five-way blocked waves from a fresh process, reducing observed OS threads from 8,001 to five. Initial affected tests pass 43 cases; the measured-burst/deep-request suite passes 13 and collector/release guards pass 23, with overlap. Native memory/endurance acceptance for this changed candidate remains pending. Prior eight-worker, one-worker, OOM and audit-tail failures remain retained. Version and deployment markers advance together to `0.8.0.dev71`.


## Dev82 integration — 2026-10-29 UTC

Exact executable16982c4dd698a937ce2ae4e37f4736055de9a2ce integrates dev81 plus native audit-generation identity fencing and bounded per-connection bridge-line reuse. The audit correction reproduces two historical-header races, then passes52 component checks. The bridge selection passes58 ASan/UBSan checks;10,000 short line reads fall from40,000 allocations/4,540,000 bytes to zero after component warm-up with unchanged digest. Counts overlap other suites and are not unique aggregate coverage. These do not establish whole-family sustained qualification.

GitHub writes recovered. Corrected observer47921d18/tree4d07383d is running in40828138175; results require complete collection. Fresh candidate CI, original45-second checks, sanitizer hours, ENOSPC and paired installed recovery remain pending. All eleven release groups remain false. Prior failure bodies and histories remain preserved. Current Qt6.10.3 attribution binds70/70 top libraries to exact upstream SDK bytes;12/230 Qt ELF files remain unbound and license/source/advisory review remains open. The qualification cluster and independent security reviewer remain unavailable.

Details: `evidence/qualification-dev82-integration-20261029.json`.
