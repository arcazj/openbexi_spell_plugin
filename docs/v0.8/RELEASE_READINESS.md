# Full v0.8 publication qualification

The full release is **not qualified**. Dev58 candidate `9e954de` completed its
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
