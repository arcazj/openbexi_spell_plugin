# Step 1: private native ABORT/CLOSE candidate

This is a terminal-command implementation and bounded qualification cohort,
not completed Step 1, whole-family quiescence, worker reuse or release approval.
The public gateway still cannot route execution.start or execution.command.

## Effect boundary

Fresh owner grants now admit CMD_ABORT and CMD_CLOSE through the existing private
owner queue. The immutable original worker, member, user, session, epoch, command
identity and expiry are rechecked at native CIF consumption. That check occurs
before ABORT can cancel a prompt, before CLOSE can setClosing(), and before either
can insert a controller command. Native CLOSE requires an observed terminal
FINISHED/ABORTED/ERROR state; ABORT requires a nonterminal state. The authorization
RPC must acknowledge before any effect. Missing identity, copied receipt, timeout,
closed/revoked controller or lost acknowledgment is not permission to retry.

An admitted ABORT cancels the current prompt of its exact member as part of
aborting that member; it is not a standalone prompt answer/cancel capability.
MSG_ANSWER, MSG_CANCEL, BLOCK and other unsupported external paths remain denied.
A private in-process marker accompanies the copied ExecutorCommand; a bounded,
mutex-protected continuation set rejects duplicate mailbox consumption. Internal
native safety operations are not reclassified as external owner grants.

Terminal consumption durably fences new RUN/STEP/PAUSE, initial RUN, child
admission and driver sends across the original execution family. Existing driver
receipt handling and audit reporting remain available. Terminal commands for
other members and CLOSE after ABORT are separately admitted; old operations are
never restamped. The driver final-send lock and terminal consumption use the same
per-execution authority lock. No reservation, spent slot or ownership is released.

## Executed tests required

The C++ regression compiles the actual composed original processMessageCommand
function against the new guard and controlled dependencies, checking that denied
ABORT cannot call cancelPrompt and denied CLOSE cannot call setClosing. A separate
concurrent C++ test races 64 copies and requires one accepted continuation. These
are native handler/component tests, not full-interpreter qualification.

Real-mTLS Context tests cover owner/observer isolation, stale sessions, copied and
altered grants, concurrent final consumption, lost response without retry,
post-terminal new-work fencing, separate ABORT/CLOSE grants and retained holds.

The hosted --native-child-gate profile rebuilds the original candidate Executor
and retains the existing 21-member family and owner-denial oracles. Six additional
single-member scenarios use fresh isolated Context/worker grants: paused ABORT,
running ABORT, prompt ABORT, normal completion, deliberate exception, and native
prompt timeout choosing its original default. Each requires fresh owner CLOSE and
waits on the original Executor pidfd before any supervisor teardown. The host
independently checks stopped container identity/exit code, unrelated witness,
exact durable grant-consumption rows, zero startup RUN use and retained holds.
No finished audit event is invented for ABORTED/ERROR: the original runtime only
emits its finished lifecycle event for FINISHED.

## Remaining acceptance limits

These fixtures intentionally have no child/thread/driver-effect work beyond the
specific case. EXIT is not proof of external effect settlement, and supervisor
shutdown of Context/Listener is not native procedure completion. Full background
thread/descendant teardown, outstanding effects and uncertain I/O, crash/storage
fault recovery and safe resource reclamation remain separately required.

Positive owner-bound MSG_ANSWER/MSG_CANCEL integration is still a Step 1
prerequisite and is not bypassed by ABORT. The historical LOADED timeout cause
is not established by a new passing run. No all-Step-1 acceptance, A/B/C handoff,
full release gate, stable version, merge, tag or production migration is granted.
