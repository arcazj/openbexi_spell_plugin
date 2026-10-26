# Full v0.8 publication qualification

The full release is **not qualified**. Server `0.8.0.dev47` and the pinned IDE
`1.2.1.dev3` remain development packages. The current component checkpoint is
recorded in [the native reconnect receipt](evidence/native-reconnect/qualification-summary.json).
Earlier exact-source receipts and failed attempts remain in `evidence/` and
`TEST_REPORT.md`.

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

## Mandatory work before publication

| Full gate | Outstanding acceptance |
| --- | --- |
| Services | Abrupt controller/network faults, production routing and complete deployed isolation/fault coverage |
| Native family | Startup reliability, open-prompt transfer, later children, broader controller fault recovery/child semantics and wider native coverage |
| Compatibility | All 763 requirements and native compatibility; original archival Windows captures remain missing |
| Driver faults | Lifecycle/reset/partition/recovery and bounded load, with uncertain effects never replayed |
| IDE/browser | Public launch, full debugger, twenty observers, WSS gap resynchronization and Git conflicts |
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
later pass as proof that either historical startup failure is fixed.

## Publication preflight

`RELEASE_GATES.json` records all eleven mandatory groups. The clean dev47
[executed preflight](evidence/release-readiness/publication-preflight-dev47.json)
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
