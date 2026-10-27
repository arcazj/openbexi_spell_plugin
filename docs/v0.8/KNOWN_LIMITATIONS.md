# Current limitations

SPELL `0.8.0.dev53` and the paired IDE `1.2.1.dev4` are development candidates.
All eleven full-v0.8 release gates remain false. Public services still report
`runtime_enabled: false`. The private retained-worker components below do not
enable public provisioning or establish production readiness.

## Current private components

The services enforce pinned mTLS identity, Context scopes, live roles, durable
SQLite CAS, original controller grants, ownership epochs and approved source
inventories. The retained worker consumes its grant once and launches the
actual native Listener/Context/Executor. The separate Context-owned DSS subset
checks authority at actual send and records matching receipts in two ledgers.
Uncertain effects are not retried.

Native before-spawn child admission, original-member identities, fresh owner
Run/Step/Pause grants, prompt delivery/replies and Abort/Close have bounded
component qualification. Terminal settlement requires a separate pinned host,
original process-exit proof and reconciled command/prompt/effect outcomes before
releasing only that family's logical reservations. Workers remain single-use.
Forced loss and other unknown outcomes retain their holds.

The `host-freeze-candidate` profile supports bounded repeated handoff of an
existing sealed family. The host proves cgroup freeze completion and original
pidfd/member identity; Context settles the journals and moves ownership while
the family stays paused. B explicitly resumes the same processes. A's stale
commands and driver packets remain fenced; C remains read-only. Native A→B→A
and an explicit same-owner reconnect are qualified components. Reconnect keeps
the ownership epoch and changes connection generation after independent host
freeze and explicit resume. Real mTLS tests cover the shared eight-rotation
capacity and reject a ninth without revoking current authority. See
[LIVE_HANDOFF.md](LIVE_HANDOFF.md) and its exact-source receipt.

Dev48 adds an agent transport drain before host freeze, after retained dev47
failures showed a captured old-epoch query and an interrupted command-poll TLS
exchange. No new RPC enters during the hold; only a fresh one-shot activation
can resume the agent. This acknowledgement is not native family quiescence.
The host freeze and settled-journal requirements remain mandatory. See
[NATIVE_HANDOFF_DRAIN.md](NATIVE_HANDOFF_DRAIN.md).

The paired installed IDE can send Run/Continue, Step, Pause, Abort and Close for
an existing native execution through an explicitly enabled Listener route. The
client retains original delivered proofs, sends once and has no local fallback.
Headless native-client qualification and real Qt panel tests are separate;
neither establishes full graphical debugger or browser acceptance. See
[IDE_NATIVE_CONTROLS.md](IDE_NATIVE_CONTROLS.md).

Dev49 additionally qualifies an unanswered native prompt with exactly zero timeout across handoff. Its original identity and definition survive; only a fresh reply from the resumed owner is accepted. Timed/unclassified prompts and queued or uncertain replies remain blocked. The pinned installed IDE uses authenticated request transport through Listener; prompt GUI/browser support is not claimed. See [NATIVE_PROMPT_HANDOFF.md](NATIVE_PROMPT_HANDOFF.md).

Dev50 corrects interrupted native admission waits and transient I/O on the same original connection, packet offset and four-second deadline. Eleven compiled transport cases and all available component workflows pass. The dev49 follow-up still records two lost acknowledgements after member binding; the synthetic interruption reproducer does not establish that historical cause. Bounded native/agent timing diagnostics now distinguish future transport failures. See [NATIVE_ADMISSION_CHANNEL.md](NATIVE_ADMISSION_CHANNEL.md).

Dev52 repairs desktop reconnect and completed-session cleanup; its 1,144 service tests and paired 272-pass IDE suite succeed. Its native terminal cohort failed before child admission with ten uncertain DSS command calls and twenty ACKED stages. The cause is unestablished. Dev53 adds bounded phase timings while retaining the original deadlines, durable ledger requirements and no-replay behavior. See [IDE_RECONNECT_SESSIONS.md](IDE_RECONNECT_SESSIONS.md) and the [failed checkpoint](evidence/ide-reconnect-sessions/dev52-qualification.json).

The final dev53 candidate `d01fc30` passes 1,149 service tests, 241 portable checks, all thirteen core jobs and all five ancillary workflows. [The receipt](evidence/ide-reconnect-sessions/qualification-summary.json) binds the exact source and eighteen verified artifacts. This component pass does not close the unresolved DSS/startup causes or any full-release gate.

## Native and recovery work still required

Transfer with timed/default or queued/uncertain prompts, new children after transfer,
abrupt controller/network fault recovery and Kubernetes host attestation are
unqualified. The explicit `session.close` and same-owner reconnect component
is documented in [NATIVE_RECONNECT.md](NATIVE_RECONNECT.md).
The accepted handoff profile deliberately seals the admitted child roster;
native qualification covers two transfers and one reconnect, with the shared
eight-rotation bound tested
at the service/runtime layer. A native main-thread PAUSED status alone cannot
prove family quiescence; the background-thread negative control demonstrates it.

Manual/nonblocking child modes, broader nested execution, repeat/failure/return
semantics and full compatibility need further original-native coverage.
Full driver lifecycle, reset, partitions, recovery and bounded load remain open.
The historical non-OOM native LOADED startup failure has no established cause;
later passes do not constitute its fix. The bd85c635 terminal recheck also failed
before its case matrix: one admitted child never reached native member binding,
while the other nine did and no worker was OOM-killed. Its cause remains
unresolved; see the retained terminal-recheck-failure receipt. New bounded
startup-stage markers and process/task snapshots retain evidence for subsequent
failures. Successful startup stress is coverage, not an established fix for an
unreproduced failure. The `5ec9429` stress failure again stopped after one child's
binding request. Dev48 preserves its first failure separately from cleanup and
retains bounded status/code/cause categories; it does not establish that fault's
cause. Earlier failed workflow and concurrency
receipts remain historical failed evidence.

There is no automatic worker reuse, uncertain-command replay or authority
relocation. Single-authority storage, node fencing, backup/restore and
upgrade/rollback require deployed fault qualification. Certificate and fixed
identity configuration changes require process restart.

## Joint product, compatibility and deployment

Public worker launch, complete debugger variables/breakpoints, browser/WSS gap
recovery and Git collaboration remain unfinished or unqualified. The installed
observer Listener-loss/reconnect component now covers twenty distinct concurrent
certificate identities and preserves ten advancing executions and thirty native
processes. All observers fail closed during the outage and remain read-only;
the separate explicit controller-session reconnect component also preserves
the original family. Neither establishes all abrupt controller fault recovery
or twenty-viewer browser acceptance.

The passing 241-test portable compatibility subset is not all-763 qualification.
Inherited archival checks reference missing original Windows captures and older
immutable source checkpoints. Current files cannot replace or restamp those
captures. Published v0.7 bytes and legacy patch preimages remain unchanged.

Compose and kind prelaunch checks exercise service identity, isolation, durable
CAS and Context restart. They do not run the complete native workload, prove
production Pod identity, enforce every network/admission denial, or qualify
node partitions and storage recovery. A production-like qualification cluster
has not been supplied or qualified in this checkpoint.

The Python SBOM and vulnerability workflow covers the development Python package
only. The unpublished server distribution has an explicit PyPI registry-audit
exclusion; a passing inventory check is not a vulnerability audit of its code.
Full native/OS SBOM and license disposition, independent implemented-system
security review, bounded load and stable installed artifacts remain mandatory.

Vendor GCS/spacecraft integration, untrusted Python sandboxing and distributed
HA are outside the qualified scope. Publication is authorized only after the
full mandatory acceptance criteria pass. The release preflight rejects the
current candidate; qualification work, not routine owner confirmation, blocks
publication. Production migration is not authorized.


## Current memory and audit-storage qualification

Candidate `2972f5f` fixes demonstrated processor/node construction churn and
notification-field copying, but mandatory handoff and IDE memory growth still
fails at 90.58/81.78 MiB against 64 MiB. Peak budgets pass. Bounded component
reuse is not a whole-runtime memory pass. See [the current receipt](evidence/message-allocation-20261027.json).

The original-family optimized one-hour baseline accumulated about 125 MiB of
ASRUN output in 128 MiB temporary storage. Continued process activity does not
prove every audit record was stored. Durable bounded audit storage and explicit
write-failure behavior remain blockers; dropping audit records is not a fix.
Earlier delayed member-registration and worker-exit failures remain unexplained.
