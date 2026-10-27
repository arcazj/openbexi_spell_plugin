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

The installed-IDE sanitizer hour fails; the handoff hour is still running. The IDE archive retains all
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

# Full v0.8 publication qualification

Candidate `1612600` completes core run `40523170281`: **13/14 core jobs**,
all five ancillary workflows and **1,490 foundation tests** pass with no test
failures/errors/skips. All 24 startup-stress families and 16 terminal cases pass.
Twenty archives and all recorded source inventories are verified; the tested
merge and candidate trees match. See [complete checkpoint](evidence/native-input/qualification-summary.json).

| Recovery profile | Peak MiB | Growth MiB | Result |
| --- | ---: | ---: | --- |
| Handoff | 1,130.40 | 84.19 | Fails 64 MiB growth |
| Installed IDE | 1,378.38 | 47.51 | Passes this scoped recovery check |

Both retain eight original processes for 45.62 seconds with every interval
advancing. Limits, sanitizers and deadlines are unchanged. The earlier startup
GUI-admission failure did not recur; its cause remains unproved. Current longer
comparisons are pending, while prior endurance file/audit growth and broader
native/compatibility/browser/deployment/security/packaging gates remain open.
All eleven full-release gate groups stay false; no publication is eligible.

Historical checkpoints follow.

The latest decoder follow-up reuses owned fields when incoming LINE/ACK layouts
alternate; its measured 200,000 allocations fall to zero in 10,000 cycles.
See [implementation and qualification limits](NATIVE_INPUT_FIELD_REUSE.md).
The preceding `bea8f4f` candidate passes 1,489 foundation tests, 11/14 core jobs
and all five ancillary workflows. Handoff/IDE growth improves to 84.18/89.21 MiB
but still exceeds 64 MiB. Terminal qualification also fails before child-running
on late native GUI admission; its root cause is unproved. All 15 core/diagnostic
artifact digests and recorded source inventories are verified in the
[receipt](evidence/native-input/prior-candidate.json). Fresh hosted evidence for
the decoder follow-up is required. All eleven full-release gate groups remain false.

Historical checkpoints follow.

The metadata-reuse follow-up is documented in [NATIVE_METADATA_REUSE.md](NATIVE_METADATA_REUSE.md).
Its preceding candidate `3823fe0` passes 1,485 foundation tests, but both mandatory
recovery profiles still fail memory growth (114.56 MiB handoff, 112.05 MiB IDE).
Both preserve eight original processes and pass peak memory. The verified
source-bound archives are retained in [the receipt](evidence/native-metadata/prior-candidate.json).
The follow-up reuses bounded message metadata storage and removes temporary
ID copies in the synchronous routing filter. Fresh whole-runtime evidence is
required; all eleven full-release gate groups remain unqualified.

Historical checkpoints follow.

Candidate `0a14360` resumes hosted qualification in core run `40456278980`.
All five ancillary workflows and the allocation diagnostic pass. Its explicit
incoming-message completion correction is validated by 143 focused checks and
a compiled 10,000-completion benchmark (90,000 allocations before, zero after).
The actual Context diagnostic confirms a substantial reduction in copy
allocations, but this does not resolve whole-runtime resource acceptance.

The source-verified mandatory handoff preserves all eight original processes
and progress through 45.46 seconds, passes the 1,792 MiB peak ceiling at
1,418.34 MiB, and fails the unchanged 64 MiB growth limit at 109.29 MiB. Its
archive digest and all 132 source inputs match the candidate. Installed IDE
also preserves eight processes through 45.60 seconds, passes peak at 1,398.77
MiB and fails growth at 91.23 MiB; its archive and 132 source inputs are verified.
Remaining core jobs are still in flight. The independent diagnostic also fails growth
at 99.04 MiB. See [current implementation and receipts](FRESH_MESSAGE_STORAGE.md).

Earlier optimized one-hour comparisons complete with eight original processes
but fail growth at 129.34/132.96 MiB (handoff/IDE). Approximately 123 MiB of each
window is file/shared-memory growth, an unresolved separate endurance blocker.
Their overlaid source inventories are verified; they do not qualify the current
candidate. The earlier encrypted-swap and same-optimization ASan comparisons
also fail resource acceptance. An optimized-IDE comparison recorded uncertain
driver effects before child-running and did not reach its soak.

All eleven full-release gates remain unqualified. Current memory stability,
57 missing historical capture hashes, fresh all-763/native compatibility,
full IDE/browser/debugger coverage, deployed workload/fault/restore checks,
independent security review and stable joint packaging remain unfinished.

Historical qualification records follow.

Dev67 `93dad41` completed hosted run `40397729336`. All 1,290 service tests,
95 overlapping fault tests and 241 portable tests pass with no failures/errors/skips.
Twelve of fourteen core jobs and all five ancillary workflows pass. All 24 fresh
startup cycles, 16 terminal cases and 21 prompt outcomes pass. Nineteen archive
digests, ZIP checks and every recorded source inventory are verified; the CI
merge tree matches the candidate.

Both recovery families complete the unchanged 45-second soak, preserve all eight
original processes and pass the fixed peak limit. Memory growth still fails:

| Profile | Peak MiB | Window growth MiB | Required peak / growth MiB |
| --- | ---: | ---: | ---: |
| Handoff | 1,662.8 | 224.9 | 1,792 / 64 |
| Installed IDE | 1,671.0 | 238.8 | 1,792 / 64 |

Deployment version markers are corrected. Buffer reuse reduces peak memory but
does not establish stable full-family allocation behavior. The earlier prompt
scope denial did not recur; its root cause remains unproved. All eleven full-release
gates remain unqualified. See [dev67 receipt](evidence/native-codec/dev67-hosted/qualification-summary.json)
and [implementation details](NATIVE_BUFFER_REUSE.md).

The v0.6 archive recovery verifies 1,525 selected blobs, including 245 of 302
referenced hashes. The previously missing child-argument capture and two failed
harness captures are recovered byte-for-byte. Review against 131 frozen source
inputs restores all ten historical checks and rejects eight altered-evidence cases.
Seven source files differ from current v0.8; this historical review cannot qualify
the current runtime. Fifty-seven referenced hashes remain unresolved by the v0.5
and v0.6 manifests. See [archive recovery](COMPATIBILITY_ARCHIVE_RECOVERY.md).

Historical qualification records follow.

Dev66 `596701b` completed run `40395297987`: 10/14 core jobs and all five ancillary
workflows passed. The 1,286 service tests had one version-marker failure; 95 fault
and 241 portable tests passed. All 24 fresh startup cycles and 16 terminal cases
passed. Nineteen archive digests, ZIP integrity checks and every recorded source
inventory were verified. The native and IDE peaks were 1,747.4 and 1,754.2 MiB,
below the 1,792 MiB ceiling, but their 224.6 and 234.4 MiB window growth still
exceeded 64 MiB. Both complete 45-second soaks preserved all eight processes.
The prompt job also failed after a rejected non-procedure-scope RaiseEvent;
all 21 prompt outcomes completed. Scope authorization remains unchanged. See
[the retained receipt](evidence/native-codec/dev66-hosted/qualification-summary.json).
No full-release gate is promoted.

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

Dev59 `5d0d64f` removes measured IPC allocation overhead and passes 1,267 service,
95 overlapping fault and 241 portable tests. Both original recovery families
now complete the fixed soak and terminal settlement without OOM, but both fail
the unchanged resource acceptance. Twelve of fourteen core jobs and all five
ancillary workflows pass; all 19 artifacts and their recorded source inventories
are verified. Dev60's diagnostic build failed native startup. Dev61 corrects
the hook registration/visibility and restores native startup, but resource
acceptance still fails in both recovery profiles. Dev62 retains the stack
metadata that the earlier host filter omitted. See [native IPC correction](NATIVE_MESSAGE_CODEC.md) and
[dev59 evidence](evidence/native-codec/qualification-summary.json).

The full release is **not qualified**. Previously, dev58 candidate `9e954de` completed its
first hosted qualification with **1,259 service tests**, **95 overlapping fault
tests** and **241 portable tests** passing without failures/errors/skips. Twelve
of fourteen core jobs and all five ancillary workflows pass, including 24 fresh
root/child startup and settlement cycles and all 16 terminal cases. Both the
native handoff and installed-IDE extended recovery jobs fail: the fixed 2 GiB
resident/no-swap profile reaches its cap and OOM-kills the original Context.
The 45-second soak does not complete. Resource limits and acceptance thresholds
have not been relaxed after observing these failures. Nineteen artifact archive
digests/ZIP checks and recorded source hashes are verified; the candidate and CI
merge have identical trees. See [the current receipt](evidence/native-resources/qualification-summary.json)
and [resource acceptance](NATIVE_RESOURCE_ACCEPTANCE.md).

Dev58 corrects empty native audit-event compatibility and adds explicit no-swap
resource acceptance after a 45-second original-family recovery soak. Dev57 run
`40367729648` passed 13 of 14 core jobs; startup-stress failed after its prompt
cohort because worker 0 recorded a denied RaiseEvent (HTTP 400), despite native
FINISHED and no OOM. The event shape was not retained, so the empty-event
regression is a proven compatibility defect but is not yet a proven cause of
that historical failure. New diagnostics retain only validation booleans.

The last all-green scoped component checkpoint follows; it does not supersede
the current failed extended recovery result. Server `0.8.0.dev56` and paired IDE
`1.2.1.dev5` remain development packages. Candidate `bad5f98` passes
**1,234 service tests**, **95 overlapping fault tests** and **241 portable tests**,
all fourteen core jobs and five ancillary workflows. IDE `c5edbda` passes
282 tests with one documented Windows-only skip. Nineteen server archives and
one IDE archive, recorded sources, wheel contents and matching candidate/CI
merge trees are verified. [The component receipt](evidence/controller-liveness/qualification-summary.json) records the identities.

[Automatic controller-loss fencing](AUTOMATIC_CONTROLLER_LIVENESS.md) now uses
monotonic leases and rotating challenges. Four actual TLS loss cases complete
explicit recovery with fixture host proofs. Both native and installed-IDE
cohorts detect absent heartbeats without `session.close`, preserve eight original
processes and require independent host freeze and explicit resume. Detection was
27.47 and 24.90 seconds after heartbeat detach under the 30-second lease policy.

Initial longer native probes were OOM-killed at 768 MiB. The corrected 1 GiB
resident-memory profile passes, but both cohorts still reach that cap with
thousands of memory-limit events. Long-duration memory behavior remains a
blocker. A second-attempt primary cohort also reproduced two late native member
replies beyond the unchanged four-second deadline. Its timing and failures are
retained; later passes do not establish their root cause. All eleven full-release
gates remain unresolved.

The owner request **"Qualify and release full v0.8"** authorizes implementation,
qualification, merge, tag and GitHub publication once all mandatory criteria
pass. Another routine publication confirmation is not required. Production
migration is not authorized, and G1 F1-F10 remain binding.

## Verified component scope

The private native profiles now cover retained launch, immutable child/member
admission, owner Run/Step/Pause, prompts, Abort/Close, host-proven terminal
settlement, two successive live-family A→B→A transfers and an explicit
same-owner reconnect. Real mTLS tests cover eight combined runtime rotations,
preserved history and denial at the capacity bound.
The paired IDE route
controls an existing execution through gateway, Listener and Context with the
original certificate identity and controller proof. Native-client receipts and
Qt tests are distinct from full browser/debugger qualification.

Before host freeze, the native agent now drains in-flight transport and holds
new RPCs. This fixes the captured-query and interrupted-TLS handoff failures;
the drain itself never proves family quiescence. The separate host still proves
the original family's cgroup freeze and process identity. Twenty separately
authenticated installed IDE observers have also passed concurrent reads and
control denial before and after Listener loss; all thirty native PIDs and ten
advancing executions survive. These are native-client components, not browser
WSS or full Compose workload qualification. See
[NATIVE_HANDOFF_DRAIN.md](NATIVE_HANDOFF_DRAIN.md).

The separate host freezes the original family for each transfer; B and then A
at epoch 3 explicitly resume those same processes. Earlier packets retain their
original identity and are denied even after ownership returns to A. Explicit
controller-session reconnect then preserves owner/epoch and advances connection
generation after another host freeze and explicit resume.
Terminal settlement releases only known-settled family reservations. Workers
remain spent, unknown outcomes remain held and public launch remains disabled.
See [LIVE_HANDOFF.md](LIVE_HANDOFF.md),
[IDE_NATIVE_CONTROLS.md](IDE_NATIVE_CONTROLS.md) and
[TERMINAL_SETTLEMENT.md](TERMINAL_SETTLEMENT.md).

Dev49 additionally qualifies an unanswered native prompt with exactly zero timeout across handoff. Its original identity and definition survive; only a fresh reply from the resumed owner is accepted. Timed/unclassified prompts and queued or uncertain replies remain blocked. The pinned installed IDE uses authenticated request transport through Listener; prompt GUI/browser support is not claimed. See [NATIVE_PROMPT_HANDOFF.md](NATIVE_PROMPT_HANDOFF.md).

Dev50 corrects interrupted native admission waits and transient I/O on the same original connection, packet offset and four-second deadline. Eleven compiled transport cases and all available component workflows pass. The dev49 follow-up still records two lost acknowledgements after member binding; the synthetic interruption reproducer does not establish that historical cause. Bounded native/agent timing diagnostics now distinguish future transport failures. See [NATIVE_ADMISSION_CHANNEL.md](NATIVE_ADMISSION_CHANNEL.md).

Desktop reconnect now opens a fresh authenticated session and retains other execution sessions until explicit Disconnect. Completed-session cleanup cannot refence a new controller or adopt an unfinished close under a new key. The actual Qt/TLS integration passes among 1,144 dev52 service tests. The independent native terminal cohort stopped with ten uncertain DSS commands before child admission; its cause remains open. Dev53 records bounded phase timings to distinguish command delays without increasing deadlines or replaying effects. See [IDE_RECONNECT_SESSIONS.md](IDE_RECONNECT_SESSIONS.md).

## Mandatory work before publication

| Full gate | Outstanding acceptance |
| --- | --- |
| Services | Deployed controller/node partitions, production routing and complete workload isolation/fault coverage |
| Native family | Startup reliability, timed/default and queued/uncertain prompt transfer, later children, broader controller fault recovery/child semantics and wider native coverage |
| Compatibility | All 763 requirements and native compatibility; original archival Windows captures remain missing |
| Driver faults | Stage reply loss, same-DB DSS restart and reset denial now checked; historical dev52 timeout, broader partitions, authority/driver recovery and deployed bounded load remain |
| IDE/browser | Public launch, full debugger, browser observers, WSS gap resynchronization and Git conflicts |
| Compose | Full ten-execution/twenty-viewer runtime workload, negative egress, process/storage failure and restore |
| Kubernetes | Production-like cluster, runtime Pod identity, RBAC/admission/network denial, node partition and storage recovery |
| Recovery | Full deployed shutdown/fencing/settlement plus backup restore, upgrade and rollback |
| Security | Independent implemented-system review, bounded load, native/OS SBOM, licenses and vulnerability disposition |
| CI | Complete clean-candidate runtime/driver/browser/deployment workflows |
| Packaging | Stable versions, final checksums, clean installed acceptance and release runbooks |

Compose and kind prelaunch smoke results establish only their executed service
checks. The Python supply-chain result explicitly retains the unpublished local
package's registry-audit exclusion. Neither is a full release receipt. The
historical non-OOM LOADED startup failure remains unresolved. The bd85c635
terminal recheck also timed out before its case matrix when one admitted child
never reached native member binding. All ten roots and the other nine children
were live, and no worker was OOM-killed. Its exact cause remains unresolved;
[the failed receipt](evidence/native-ide-controls/terminal-recheck-failure.json)
is retained separately from successful component results. Bounded startup-stage
diagnostics and fresh-family stress now increase coverage without treating a
later pass as proof that either historical startup failure is fixed. The
`5ec9429` stress recheck again failed after one child's binding request. Its
cleanup error masked the original exception. Dev48 preserves the primary
failure, records bounded transport error categories and attempts all cleanup;
this diagnostic repair is not a startup reliability fix.

## Publication preflight

`RELEASE_GATES.json` records all eleven mandatory groups. The clean dev56
[executed preflight](evidence/controller-liveness/publication-preflight.json)
reports `full_v08_qualified: false`, `eligible_for_publication: false`, and
`publication_performed: false`.

`python scripts/check_v08_release.py --output <report.json>` exits nonzero until
every group has a complete, checksummed, source-bound receipt and the server
version is `0.8.0`. Partial component receipts cannot qualify full gates.
Receipts use `openbexi.v08.acceptance-gate/1`, exact SPELL and IDE commits,
all required checks and actual execution evidence. Hand-edited flags are not
executed tests.

`--candidate <exact-code-SHA>` permits later evidence-only commits without a
self-referential receipt hash. Runtime, workflow and IDE-pin changes require
qualification for their new sources. This preflight validates evidence; it
does not execute missing tests or create a release.

## Inherited compatibility evidence

The retained bounded inherited diagnostic ended after 16 passes and three
failures, initially in `tests/test_child_arguments_report.py`, referencing
historical Windows `obspell_v06_resume/.qualification` captures. The broader
diagnostic was interrupted and is not a completed suite. The published v0.7
raw archive SHA256 is
`9db68109972848d7dd38634c421c1aad94bb75103df9e65432e0e58e99dd9357`.
Historical captures require their original immutable sources. The 241 portable
checks are a named subset; they do not substitute for all-763 coverage.

No stable release, merge or production migration is justified by the current
component checkpoint.

## October 26, 2026 — verified memory comparison and release disposition

This section supersedes the *diagnostic comparison status* above, not the
mandatory release-gate results. The isolated 300-second comparisons were
executed on the exact PR candidate and are not release qualification.

- GitHub run [40418928585](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40418928585):
  optimized/no-swap controller handoff and installed IDE both passed.
  Observed peak resident memory was approximately 150.34 MiB; measured
  growth was 15.48 and 15.19 MiB respectively. Eight original processes
  remained alive. Both ASan/no-swap cases failed: peaks 2000.78/2030.09 MiB
  and growth 605.51/627.83 MiB (handoff/IDE).
- GitHub run [40420500650](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40420500650):
  both optimized/no-swap cases passed again; both ASan/no-swap cases failed.
  The ASan/swap cases did not execute because the disposable runners already
  had swap enabled and the host guard refused to modify or use it.
- GitHub run [40420500775](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40420500775):
  foundation and other preflight jobs passed; the two mandatory native
  handoff/IDE recovery jobs failed. They are **not** cleared by the
  experimental optimized comparison.

### Required sequence before any release promotion

1. Preserve the pinned native source and IDE revision. Promote the optimized
   experimental build to a *separately named reproducible release candidate*
   only after verifying Listener, Context, both Executors, shared library,
   bridge, launcher and Python shim hashes/dependencies. Keep the existing
   ASan/UBSan build available and unchanged for safety qualification.
2. Add an explicitly opt-in 3600-second optimized/no-swap endurance workflow.
   Repeat A-to-B handoff, C observing, disconnect/reconnect, pause/resume,
   ABORT/CLOSE, and procedure execution throughout the run. Record original
   process identity, per-process RSS/PSS, cgroup memory, allocation trends,
   FD/thread counts, control latency, failures and cleanup. Require
   independently verified source/binary and IDE provenance. Do not reuse
   300-second comparison receipts to claim a 3600-second result.
3. Isolate sanitizer overhead with a same-optimization-level pair:
   optimized + ASan/UBSan versus optimized without sanitizers, identical
   workloads, no swap, identical binary provenance except instrumentation.
   Capture live allocation and allocator-retained memory separately.
   Preserve sanitizer error detection and all existing mandatory limits.
4. Run optional encrypted-swap experiments only on a dedicated disposable
   runner with an explicitly proven safe swap baseline. Report setup failure
   as setup failure, retain evidence, and never treat swap as satisfying the
   mandatory no-swap recovery oracle.
5. Repeat the unchanged 45-second mandatory native-handoff and installed-IDE
   sanitizer acceptance checks. Both must meet 1792 MiB peak and 64 MiB
   growth with all eight original processes and no swap/OOM events.
6. After both mandatory gates pass, execute fresh all-763 historical
   compatibility, driver/native recovery, browser/debugger/public-launch,
   Docker Compose and Kubernetes recovery, independent security review,
   and joint IDE/plugin package and publication checks.

**Release decision: HOLD.** This is a verified comparison finding and
an execution plan, not evidence of full v0.8 qualification or publication.

## Latest hosted release gate check — run 40428613683

At commit `084e58593d242857bd8e56d5b4ec364ed9d3240d`, 12/14 core jobs passed, including foundation,
startup stress, terminal, prompt, pause, listener, DSS, fault and boundary checks.
**Mandatory native handoff and installed IDE recovery failed**; both remain
blocking. The separate memory comparison run 40428613772 passed the optimized
five-minute handoff and IDE scenarios but did not replace mandatory sanitizer
acceptance. Its 60-minute endurance and controlled sanitizer comparison jobs
were still in progress at this check. Encrypted-swap experiments failed.

**Qualification: FAILED / INCOMPLETE. Release: HOLD.** No merge, tag,
publication or production deployment is authorized by this receipt.
