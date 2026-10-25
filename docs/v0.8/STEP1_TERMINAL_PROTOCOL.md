# Step 1 private native terminal-command protocol

This candidate extends the existing original-worker/owner-command chain; it does
not use the earlier isolated Boolean ABORT/CLOSE prototype. It enables terminal
commands only in an explicitly configured, prompt-enabled private native build.
Default native builds, public Gateway/Listener mutations, v0.7 and all eleven
full-release gates remain unchanged. Passing a component test is not Step 1
acceptance or ownership-transfer permission.

## Cryptographic and single-use authorization

The Context issues the existing `OwnerCommandGrant`: a random 256-bit secret,
stored only as a SHA-256 hash and verified with constant-time comparison, plus an
exact canonical binding. It binds the original authority/worker incarnation,
execution, registered native member, owner, connection/generation, epoch, operation
ID/digest and expiry. It is **not a self-verifying JWT or an offline signature**.
The real certificate-pinned mutual-TLS Context verifies it online. The native
Executor holds no authority minting secret and receives only the immutable request
ID in original IPC; its pinned local agent resolves that ID to the delivered grant.

Original native Context forwarding still requires the independent owner grant.
The new CIF check runs before prompt cancellation, `setClosing`, resetting the IPC
interruption indicator, or enqueueing the native command. SO_PEERCRED, pinned
pidfds, parent identity and exact native executable bind the local callback. The
Context atomically commits consumption and a retained terminal intent before
returning ALLOW. The prior late mailbox-consume endpoint refuses terminal commands.
A missing reply does not authorize retry, alternate IDs or restored authority.

A bounded, process-local ticket carries that committed decision from the earliest
CIF check into the original controller mailbox. It is **not a new authorization
source**. A ticket is attempted before the RPC and retained on every failure.
Only one queue/claim transition is possible across native translation units and
threads; the Context ledger supplies durable replay protection across restarts.

## Native semantics

ABORT uses the original `cancelPrompt` and controller `doAbort`, retaining the
original scheduler/GIL/condition-variable ordering. An active prompt must match
the exact registered generation at Context consumption and again at native
selection. A timeout or new generation that wins during authorization cannot be
silently cancelled by an old permit. Prompt CANCEL also records a terminal effect
fence before its original scheduler abort transition.

CLOSE is permitted only after an actual native FINISHED, ERROR or ABORTED status
and no open prompt. Running/paused/unknown close requests fail before `setClosing`.
After authorization it invokes the original `doClose`/finalization path. Internal
native STOP remains an internal safety marker; no external STOP grant is added.

An admitted terminal intent immediately fences subsequent driver actual-send,
initial RUN, child-start and ordinary owner-command admission for that execution.
Unrelated executions are unchanged. Original started/finished audit messages have
a narrow safety-only report path so fencing cannot erase termination evidence.
That reporting path is restricted to registered native members and cannot send a
command, restore an owner, start a worker or acknowledge an external effect.

## Outcomes and cleanup are separate evidence

CIF admission, IPC acknowledgments and handler returns do not prove termination.
A native terminal status does not prove all background work or remote effects have
settled. The original process identities, native lifecycle receipts, driver-stage
receipts, single-use container exit and independent host process absence are
checked separately. Uncertain operations retain holds/spent workers, even after
host cleanup. No automatic worker reuse, replacement, epoch restamping or positive
ownership transfer is introduced.

`scripts/qualify_v08_step1_native.py` rebuilds the actual original Context and
Executor with `--native-prompts --native-terminals`. It provisions fresh private
contexts, immutable synthetic procedures, original worker grants and real native
processes for normal/error, answers/cancellation/defaults, prompt races, active
and terminal CLOSE, ABORT, live children/background processes, forced worker loss
and independent DSS cases. Its result is executed evidence only after its exact
candidate run completes. The Step 1 acceptance decision additionally requires all
mandatory cases and the outstanding startup investigation; it cannot be inferred
from compilation or the unit suite alone.
