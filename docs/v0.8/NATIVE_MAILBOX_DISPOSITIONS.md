# Native mailbox disposition evidence — v0.8 development

This candidate adds an authenticated, durable **native Executor mailbox observation**
for original initial RUN and independently owner-admitted RUN, STEP and PAUSE.
It is **not** an execution-completion, driver-settlement or quiescence protocol.
Public execution and ownership transfer remain disabled.

## Origin and scoped protocol

1. The immutable original StartGrant authenticates one worker incarnation.
   Each initial RUN has a one-shot immutable operation identifier. Interactive
   actions need a *separate* original owner-issued command grant, bound to the
   user, connection, epoch, runtime origin and registered native member.
2. The original Executor CIF propagates `ExecutorCommand.v08Request` and
   `v08External` across mailbox/deferred command copies. Unsupported external
   commands are rejected before effects, including the original controller's
   STOP short-circuit. Original internal safety STOP remains unchanged.
3. At `SPELLcontroller::executeCommand`, one of two **observations** is made:
   `DISCARDED_PENDING` when a busy command is discarded before its handler,
   or `HANDLER_RETURNED` after the normal command handler returns and the
   original command-processing marker is cleared.
4. The real native Executor sends `openbexi.native-disposition/1` over the
   protected agent-owned Unix socket. The worker agent authenticates native
   PID, parent and executable using pinned live process identities, and
   verifies exact member, command ID, command type and a previously admitted
   final consumption.
5. The worker issues a certificate-authenticated Context RPC:
   `control-disposition` for original RUN and `command-disposition` for
   explicit owner commands. Context checks the immutable operation digest,
   original grant and, for owner commands, independently issued command token.
6. A single SQL transaction records one immutable disposition and one
   corresponding audit event. Identical reports are idempotent; conflicting
   outcomes fail with a conflict. The agent never retries after response loss.

## Security invariants and limits

The original initial RUN journal state remains `DISPATCH_UNCERTAIN`, and
the owner-command journal remains `EXECUTION_UNPROVEN`, **even when a
HANDLER_RETURNED receipt exists**. Neither report upgrades an execution to
`QUIESCENT` or `COMPLETE`. Responses always assert:

```json
{
  "quiescence_proven": false,
  "effective_transfer": false,
  "hold_retained": true,
  "runtime_enabled": false
}
```

The handler return **cannot prove** completion of background Python threads,
native callbacks, pending prompts, child procedures, deferred tracing events,
driver writes or terminal lifecycle events. A busy discard likewise cannot
prove that earlier admitted work has settled. Crashes, exceptions, process
loss, unauthorized commands and work discarded elsewhere may never produce
a disposition; missing evidence is uncertainty, not retry permission.

The original grant is **never restamped** after owner handoff. These reports
do not release reservations, issue new worker identities, authorize commands,
switch owners or establish a family barrier.

## Qualification and pending work

The local focused real-mTLS tests exercise pre-consumption rejection,
original versus owner origin, copied tokens, forged IDs, bad disposition
labels, conflicting and duplicate reports, post-disconnect safety reports
and one physical agent attempt despite a lost acknowledgment.

The checked original SPELL 2.6.10 archive must have exactly one insertion
site for the busy-discard case and one for the normal handler-return case.
The exact-code hosted original-native cohort must still verify actual
receipts and all retained negative oracles. This component does **not**
qualify native STOP/ABORT/CLOSE/BLOCK positive actions, prompt handling,
queue-wide terminal disposition, full family closure, new-owner runtime,
public Run/Debug/WSS/Git, all legacy compatibility, Kubernetes/Compose
deployment, recovery, security review or stable release packaging.

The exact original-native child-gate qualification now requires all 21
`HANDLER_RETURNED` observations in both the original worker callbacks
and the Context's durable `native_control_dispositions` table, joined to
exactly the 21 consumed original RUNs. The isolated actual same-owner
RUN/PAUSE/RUN probe requires three matching `native_owner_command_dispositions`
rows joined to the three original grants. Every one of these observations
continues to be explicitly **not full effect settlement**. Failure of any
receipt is a failed native qualification, not a reason to replay its operation.

All eleven full-release groups in `RELEASE_GATES.json` remain false.
