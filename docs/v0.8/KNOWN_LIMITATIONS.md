# Current limitations

SPELL `0.8.0.dev46` and the paired IDE `1.2.1.dev2` are development candidates.
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
is qualified as a component; real mTLS service tests cover the eight-transfer
capacity and reject a ninth without revoking current authority. See
[LIVE_HANDOFF.md](LIVE_HANDOFF.md) and its exact-source receipt.

The paired installed IDE can send Run/Continue, Step, Pause, Abort and Close for
an existing native execution through an explicitly enabled Listener route. The
client retains original delivered proofs, sends once and has no local fallback.
Headless native-client qualification and real Qt panel tests are separate;
neither establishes full graphical debugger or browser acceptance. See
[IDE_NATIVE_CONTROLS.md](IDE_NATIVE_CONTROLS.md).

## Native and recovery work still required

Transfer with an open prompt, new children after transfer,
controller reconnect recovery and Kubernetes host attestation are unqualified.
The accepted handoff profile deliberately seals the admitted child roster;
native qualification covers two transfers, with the eight-transfer bound tested
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
unreproduced failure. Earlier failed workflow and concurrency
receipts remain historical failed evidence.

There is no automatic worker reuse, uncertain-command replay or authority
relocation. Single-authority storage, node fencing, backup/restore and
upgrade/rollback require deployed fault qualification. Certificate and fixed
identity configuration changes require process restart.

## Joint product, compatibility and deployment

Public worker launch, complete debugger variables/breakpoints, browser/WSS gap
recovery and Git collaboration remain unfinished or unqualified. The installed
observer Listener-loss/reconnect component preserves advancing native processes;
it does not establish active-controller fault recovery or twenty-viewer browser
acceptance.

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
