# Proposed per-execution ownership protocol

`TARGET-v0.8`, Gate F not executed. Binding review resolutions F2/F3/F7 in
[G1_REVIEW_RESOLUTION.md](G1_REVIEW_RESOLUTION.md) specify the transfer barrier,
actual-send ordering and reconnect completion rules. Each execution stores owner user ID, owner
connection binding, increasing control epoch, hashed capability, control state
and grace deadline. Execution lifecycle and ownership state are separate.

Control states: `OWNED`, `CONTROLLER_DISCONNECTED`, `UNOWNED`,
`RECOVERY_REQUIRED`. Pending claims are separate durable records with server
UUID, execution, requester, expected current owner/epoch, created/expiry time,
idempotency binding and status. Policy: **one pending claim per execution**;
a competing request returns conflict. There is no global owner-per-user limit.

## Request → accept → transfer

1. A Context-authorized observer with `request_control` permission posts a claim.
   A read-only-only account cannot obtain this permission by changing UI fields.
   Validate execution, current owner, expiration and idempotency; persist
   `CONTROL_CLAIM_REQUESTED`. Requester remains an observer.
2. Current owner receives a nonblocking Accept/Reject notification. Accept
   carries claim ID, current epoch, connection capability and idempotency key.
3. Under the same per-execution serialized transaction used for control
   admission, check authenticated current owner, live connection binding,
   expected epoch, pending unexpired claim and requester eligibility. Expire
   using server time inside the transaction, not only a background timer.
4. Prove the transfer barrier (F2) before acknowledging effective acceptance.
   CAS owner+epoch; increment epoch; revoke old capability; create a fresh
   capability bound to requester's authenticated connection. Persist
   `CONTROL_CLAIM_ACCEPTED` then `CONTROL_OWNER_CHANGED` atomically. Only after
   commit expose the new capability privately to its recipient. Failure before
   commit grants nothing. Reconnect rotates capability and fences old sessions.
5. Broadcast redacted claim/owner events to all viewers. Former controller
   remains connected as observer; no other execution's row or epoch changes.

Reject, requester cancel or timeout persists a decision event, leaving owner
and epoch unchanged. Accept/reject replay returns the recorded decision, never
another transfer. A controller switch/release/restart invalidates pending
claims; a claim against a former epoch cannot be accepted.

## Mutation boundary

Every execution-affecting request, including RUN/restart, pause/resume, step,
abort, skip/goto, breakpoints, debugger evaluation/variable changes, prompt
answer and procedure-specific blackboard writes, passes Context authorization.
Observers may read bounded state/snapshots/events and request permitted claims;
they cannot call an alternate DAP/worker/driver path. Development Git writes
have a separate scoped permission; operational blackboard writes require
execution authority or a separately defined administrative action.

Driver effect admission rechecks the current execution epoch and procedure
fence at each external write. Transfer and final check/actual write linearize under
the same per-execution admission mutex; SQLite transactions remain short and
never contain network waits. An immutable original grant is carried end to end;
delayed requests are never stamped with the current epoch. A command already admitted
before transfer may have an external effect; an epoch cannot undo it. Record
its actual correlation/outcome and block any later write using old authority.
Never resend an uncertain command to make UI state agree with the new owner.

## Disconnect, release and recovery

Loss of a single viewing socket does not imply user disconnect if another
valid controller connection is active. Server heartbeats define a configurable
grace period. During grace retain owner; do not promote a pending claimant.
After grace fence new mutations/effects and request a proven safe pause/freeze;
execution is not automatically terminated. If pause cannot be proven, expose
uncertainty and keep reservations. Resume needs explicit resolved authority.

Voluntary release requires a confirmed safe pause and current owner proof;
increment epoch, clear owner, cancel claims and emit `CONTROL_RELEASED`.
Acquisition of deliberately UNOWNED state requires explicit scoped permission,
fresh atomic claim and capability; it is never a takeover of an active owner.
Recovery-required or expired/disconnected ownership cannot use that route.

On Context restart, keep owner identity for audit but advance epoch, revoke
connections/capabilities, expire pending claims and mark active executions
`RECOVERY_REQUIRED`. Do not reconstruct a valid token from an old browser or
silently resume a worker. Offline authorized recovery requires proof of old
worker shutdown and effect settlement. Emergency override is disabled by
default and, if later enabled, requires separate privilege, reason and audit.

Mandatory tests: accept/reject/expiry/cancel; simultaneous claims/accepts;
forged identity/epoch/capability; transfer vs prompt/driver write/command;
duplicate idempotency key with changed payload; disconnect/reconnect; server
crash before/after commit; restore with old token; U1 owns A/B/C and transfers
only B. No test may accept two effective controllers or unconsented takeover.
