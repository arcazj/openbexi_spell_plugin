# Private same-owner native reconnection

Server `0.8.0.dev47` and IDE `1.2.1.dev3` add an explicit reconnection path to
the private `host-freeze-candidate` profile. The original native family keeps
its owner and ownership epoch. Only the controller connection and generation
change. Public provisioning remains disabled.

## Admission and host proof

The current owner opens a new authenticated session and calls the existing
`execution.rebind` operation with the execution ID, new connection ID and
expected ownership epoch. The owner must still have `execution:control` and
`execution:start`. The original Context incarnation and sealed family must
match, and all known prompt, native handler, driver and effect outcomes must
be settled. Uncertain effects block admission; they are never replayed.

The service accepts either the current live controller or an explicitly closed
controller session. It rejects the old connection as the replacement. Admission
atomically fences the old capability, invalidates pending ownership claims and
records a reconnection request. Its response has `rebind_pending: true`, no
controller capability and no effective ownership transfer. The IDE drops only
the selected execution's cached proof on this response.

The separate pinned host freezes the exact original container and proves cgroup
freeze completion, original pidfd liveness and unchanged member bindings through
the existing host handoff API. Root, child and background-thread counters must
remain stationary. A disconnect or native main-thread PAUSED status alone is
never accepted as whole-family quiescence.

At completion, Context rechecks the original owner, epoch and generation, the
new session's liveness, current roles and all journals. It keeps the owner and
epoch unchanged, increments connection generation once and enters
`HANDOFF_PAUSED`. No ownership claim is manufactured or accepted. A read-only
observer sees the same owner, new generation and paused state.

## Explicit continuation and failure behavior

The new controller calls Reconnect control again to receive its capability,
then explicitly requests whole-family Run/Continue. The host rechecks the
freeze evidence before authorizing thaw. The original consumed worker receives
fresh runtime credentials once, using the prior single-consumer proof. The
activation identifies its kind as `rebind`; the runtime checks an unchanged
ownership epoch and a new connection with generation increased by one.

Captured native packets carry the original runtime request marker. A packet
from before reconnect stays invalid even though its ownership epoch matches.
Fresh DSS commands carry the new connection generation in both independent
effect ledgers. Native member and child records retain their original family
identity. No process is substituted or startup grant replayed.

Schema 21 retains each reconnection request and distinguishes it from ownership
transfer history. Transfers and reconnects share the eight-rotation capacity.
A ninth request is rejected before revoking current authority. A late close of
the old session cannot fence the replacement controller.

Context restart, expired barriers, a closed replacement session, role revocation,
forged host proof, unresolved journals and lost activation replies never grant
automatic continuation. Lost activation is not retried. Recovery-required
families retain reservations, and workers remain single-use.

## Qualification boundary

The service tests exercise real mTLS admission, replay and stale-proof denial,
live and explicitly closed controllers, transfer/reconnect/transfer ordering,
capacity, audit rollback, expiry, role/session changes, malformed activation,
lost replies and independent DSS receipts.

The native and installed IDE cohorts extend the original A→B→A family with an
explicit `session.close`. They observe advancing root, child and background
counters and the same eight process handles during disconnect. Host freeze and
explicit resume then restore the same owner at epoch 3, generation 4. A valid
packet captured before reconnect is denied; a fresh command with the same
payload completes. Both ledgers must contain twenty matching ACKED stages for
four commands across three ownership epochs and four connection generations.
Final terminal settlement must release only the original family's reservations.

This is a bounded explicit-session reconnection component. It does not qualify
every abrupt network/controller fault, generic worker error path, open-prompt
recovery, later child creation, Context relocation, backup restore, Kubernetes
host attestation or complete deployed recovery. Exact executed outcomes belong
in the source-bound component receipt; full release gates remain separate.

The component passed at `82dc4cb99201d2f96ff02b023331a6c32b0502f7`, paired
with IDE `faf2052ba764cbc147ef05f261164853e08489c8`. All thirteen hosted
service/native jobs passed on their first attempt; 1,087 service tests passed
without skips. The IDE suite passed 266 tests with one Windows-only skip.
Both native reconnect cohorts, sixteen terminal cases and 24 fresh-family
stress cycles passed. [Exact evidence](evidence/native-reconnect/qualification-summary.json)
retains artifact digests, source checks, process counters and release limits.
