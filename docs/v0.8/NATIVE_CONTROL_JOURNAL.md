# Private native RUN journal

Dev23 adds final one-shot admission at native `executeCommand` for the initial
RUN of each admitted member, including hidden automatic children. It preserves
unproven in-flight outcomes and does not implement whole-family quiescence,
positive handoff or new-owner resume. Public execution and all full release
gates remain disabled. Hosted qualification must identify the exact source SHA.

## Implemented behavior

The optional Context configuration `native_controls: run-journal` requires the
retained launch profile. All worker routes require the pinned worker identity,
original consumed StartGrant and the consumption winner's memory-only capability.
The Listener and gateway cannot delegate these worker operations.

`control-admit` checks current policy/session/epoch under the execution mutex,
then atomically commits a bounded `native_control_attempts` row and audit event
before native IPC. Only `CMD_RUN`, with no arguments, is supported. The target is
either the original root or a consumed child admission from the same original
family. The tuple `(execution_id, target_id)` is unique: changing a request UUID
does not create retry permission. No network wait holds the SQLite transaction.
There are at most 65 attempts per execution and 4096 per Context.

The worker wrapper keeps its attempt before contacting Context. A lost admission
response prevents IPC; an unknown IPC result or lost report response never
repeats RUN. Invalid or type-substituted receipt fields prevent progression.
The private profile now adds a `V08ControlRequest` UUID to the native message;
the native Context sends that ID and its actual model instance to the owned
agent over the existing authenticated Unix helper. The original v0.7 binaries,
driver wire protocols and immutable patch preimages remain unchanged.

`control-forward` independently rechecks live original authority and records a
single `native_control_forwards` row before returning permission to the helper.
The helper requires the exact journal request/member identity and a verified
admission receipt. It records the attempt before the RPC: a lost receipt cannot
retry or forward. Replay, unknown IDs and substituted targets fail closed. The
native C++ hook denies missing or rejected IDs before `m_ipc.sendMessage`.
Only RUN is covered; the other mutation paths listed below remain pending.

The private native Context also binds each admitted instance to its actual
spawned Executor PID after login. The helper checks that process's exact
read-only candidate executable and owned Context parent, opens a pidfd, and
rechecks executable, parent and starttime. Bindings cannot be replaced or reused.
Each callback uses Linux SO_PEERCRED and the stored pidfd. An Executor can only
consume for its own bound instance; it cannot spawn, bind, or forward a member.
The native transport independently authenticates the agent PID/UID.

`V08ControlRequest` is copied into `ExecutorCommand` and retained by the native
mailbox/deferred-command value copies. Before RUN effects, `executeCommand`
contacts the helper, which requires the original verified forwarding receipt.
`control-consume` rechecks live authority under the execution mutex and atomically
records `EXECUTION_UNPROVEN` plus an audit event. Admission requires the original
forwarded operation; it cannot be retried after response loss, even if no RUN
happened. Consumption before a fence remains an unresolved in-flight interval;
consumption after a fence is denied. Neither result proves completion or pause.
Schema 14 fences attempts, forwards, consumptions and durable member records on authority restart.

Hidden automatic startup previously called `setAutoRun` without an external
command. The explicit private candidate defers that path to its normal initial
pause. The private agent issues exactly one admitted RUN when a visible or
hidden automatic child becomes PAUSED. Manual modes and recovery are still
unqualified. The default v0.7 child-client behavior is preserved by an opt-in
`admit_hidden` flag, and the published original binaries remain intact.

`control-report` accepts only `IPC_SEND_ACKNOWLEDGED` or `UNCERTAIN`. It can record
a diagnostic after controller fencing using the original immutable identity,
but cannot issue a command. Exact diagnostic replay is read-only; conflicting
reports fail. Both outcomes retain `DISPATCH_UNCERTAIN`: an IPC send acknowledgment
does not prove mailbox acceptance, execution, completion or queue settlement.
Neither report releases a reservation or spent worker. The journal preserves the
rows and marks them `RESTART_FENCED` on startup, with original hashes/outcomes
intact; the original worker proof becomes unusable after authority restart.

The dev23 child cohort requires 21 matching original attempts, forwards and
Executor consumption rows: ten roots, ten visible/hidden children and one visible
grandchild. It also requires ten real unregistered-RUN forwarding denials and
21 exact member bindings. Only the explicit audit/compute profile uses the
rebuilt 74-unit Context and 112-unit Executor graphs. Exact-source hosted build
and execution remain pending until a verified receipt is recorded below.

## Remaining native boundaries

Review used the source archive `docs/reference/SPELL2.6.10-src.zip` (SHA-256
`2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed`), with the
frozen v0.7 recipe at `109a47af47951e2fa54b60cb408a543b117f7f15`. The reconstructed
Context `SPELLexecutor.C` matched the before-spawn builder's required preimage.
Native paths below are inside that archive, after the frozen composition patches.

| Native path | Consequence for positive handoff |
| --- | --- |
| `lib/SPELL_EXC/src/SPELLcontroller.C`: `command`, `run`, `executeCommand` | Initial RUN now carries immutable identity and final admission. Other queued/direct commands and deferred SKIP/GOTO still need admission and explicit settlement. |
| `lib/SPELL_EXC/src/SPELLcommandMailbox.C`: `push`, `pull`, `reset` | Full queues and repeated non-repeatable commands can be discarded silently. Clearing a queue must produce explicit terminal dispositions for every command. |
| `lib/SPELL_EXC/src/SPELLexecutorImpl.C`: `command`, `pause` | Direct high-priority pause is separate from ordinary queued dispatch; a main-thread pause does not settle the family. |
| `lib/SPELL_CIFS/src/SPELLserverCif.C`: message/request processing and prompt handling | Client messages, variable requests and prompt responses are distinct admission paths. A prompt timeout is not settlement proof. |
| `lib/SPELL_CIFS/src/SPELLrequestProcessor.C`: variable mutation | Direct variable/container writes bypass the controller mailbox and need the same fencing contract. |
| `lib/SPELL_SYN/src/SPELLthread.C`, IPC workers and CIF buffers | Native infrastructure and user execution participants need an explicit inventory; Python line monitoring or process enumeration cannot establish it. |

A fence can occur after Context commits an attempt but before native IPC sends.
The journal deliberately does not claim to close that interval. The regression
test injects it and requires transfer to remain BLOCKED with the original owner,
epoch and holds. Positive transfer requires complete authenticated native command/direct-
mutation checks plus barrier acknowledgment for every active command, deferred
trace command, prompt, child, user thread and effect. Unknown command outcomes
cannot be cleared by timeout, status `PAUSED`, or worker termination. A new owner's
resume must have a fresh explicit grant; old commands keep their original identity.

## Qualification

`server/tests/test_control.py` exercises actual worker-to-Context mTLS, 100
concurrent admissions, copied-config denial, revoked policy, original child
binding, audit rollback, durable restart, single-attempt transport failures and
conflicting/forged reports. Native IPC is a test boundary in these tests; the
hosted child cohort supplies the real native execution check and exact journal
cardinality. Neither result qualifies the remaining native boundaries above.

At `ec9ad5d94022a8915970f0e5ac5c5c2a44e11f60`, both hosted native child jobs
passed. The push artifact's digest, CRC and all 25 source hashes were verified:
ten workers journalled exactly 16 agent RUNs, with six child targets matching
their original consumed family admissions. All outcomes remained unproven.
See [the component receipt](evidence/native-child-start/dev19-child.json).
Both foundation jobs also passed 409 tests without skips; the PR foundation
artifact's digest/CRC and all 122 source hashes were checked. The PR workflow
as a whole failed a separate DSS telemetry refresh and is not labelled green.

Implementation: `server/src/openbexi_spell_server/control.py`,
`host_runtime/python/control_journal.py`, and the explicit routing/configuration
in `launch.py`, `services.py`, `transport.py` and `__main__.py`.

Dev22 runtime **bfa4a7f07c5c2289c7329bd1da10ee08c5e69932** passed every service/native
job in both PR 40120586927 and push 40120582247. The native Context was actually
rebuilt and the cohort verified **ten unregistered-RUN denials**, sixteen matching
forward admissions, eleven child admissions and retained holds. The downloaded
native artifact digest/CRC and all 26 source hashes were checked. Foundation
passed 424 checks without skips, with digest/CRC and 124 source hashes verified.
[Native forward receipt](evidence/native-child-start/dev22-forward.json).
Executor dequeue, other mutation paths, whole-family settlement, live transfer
and new-owner resume remain unqualified.


Dev23 `944ed1e` passed 434 hosted service/paired checks without skips, including
all kernel identity controls, but the native family job failed at link time;
no native consumption pass is claimed. The retained failure and exact source
hashes are recorded in [TEST_REPORT.md](TEST_REPORT.md). Dev24 restores the
frozen common-runtime graph and its two supplemental CPython support objects,
registers the candidate DTA initializer before Python startup, and explicitly
selects the candidate Executor. The real cohort checks one native singleton.

Dev24 also requires a separate fresh-worker race probe: hold RUN before final
admission, durably close its own controller, then require HTTP 403, no
consumption row, no procedure-body marker and the same three live native PIDs.
Termination still retains the probe's hold and spent worker. It adds no
quiescence, queue-settlement, resume or release permission. Exact hosted
validation is pending.


Dev24's native programs built, but its eleven-slot harness was correctly denied.
Dev25 keeps the primary ten-worker Context A unchanged. The actual stale-RUN
probe uses independent Context B, one fresh worker and one unstarted reserved
witness. B must retain two holds/one spent worker and preserve its witness; A
must retain 21 holds/ten spent workers. No worker is reused or limit enlarged.
The C++ hold is before opening the helper channel; five seconds of host delay
exceeds its ordinary four-second network deadline without consuming that budget.
The subsequent callback must receive HTTP 403 from the live authority. Status,
marker absence and PID continuity alone cannot substitute for that check.
Exact-source native validation remains pending.


At f14749f, foundation passed 444 checks and all six other native jobs passed in
both PR and push. The new native family had ten admitted/running roots but no
consumed children; it stalled before the independent stale-controller probe.
The failure is retained. Dev26 moves singleton validation into trusted native
Executor bootstrap, before user tracing, while preserving Context's separate
metadata graph. All 21 consumptions, exact bindings, child modes and the final
HTTP-403 probe are still mandatory. This candidate remains unqualified until
its actual native execution passes.


At **05aff1c525dca5ecd9d15ba322166b871c9ec024**, both hosted family jobs
passed. The PR receipt verifies 21 final consumptions/bindings, 11 children,
41 native PIDs and exactly 42 lifecycle records. An isolated actual Executor
held before channel creation received HTTP 403 after its owner disconnected,
with no body execution or consumption row, unchanged native PIDs, original
owner/epoch and retained holds. The separate reserved witness was unchanged.
Archive digest/CRC, 30 repository and 144 compiled source hashes were verified.
See [dev28 consumption](evidence/native-child-start/dev28-consumption.json).
All remaining mutation, queue, full-family barrier and positive transfer
requirements above remain unqualified. The PR workflow failed a separate DSS
deadline check; only the push workflow was fully green.


## Durable member registration (dev30 candidate)

`member-bind` is a private protocol-2 worker operation available only with the
RUN-journal profile. The pinned original worker identity, consumed grant and
memory-only winner capability are required. Live authority is checked again
under the execution mutex. Context persists the original target admission,
native instance, worker-namespace PID/parent PID/start ticks, executable digest,
origin and binding hashes before native registration is acknowledged. Numeric
and instance forms are strict; root identity must match its immutable approved
manifest. Children require consumed admissions, unchanged approved source,
registered original parents and the same native Context parent/executable.

A target, instance or PID cannot be replaced within the execution. Bounds are
65 members per execution and 4096 per Context; rows are never recycled. Actual
RUN forwarding and final consumption require the corresponding durable member.
The helper pins and verifies the exact process first, commits one registration
attempt, checks the exact receipt and rechecks the process pins before local
registration/ALLOW. Reply loss, substitution, dead process or RPC failure leaves
no local authorization and never retries. The local pin is closed on failure;
any already committed row/hold remains retained. Subsequent authentication
rechecks Executor/Context pidfds after identity reads to reject an incarnation
that died during validation, including the PID-reuse interval.

Records are **REGISTERED_UNPROVEN**, never host attestation or a quiescence
acknowledgment. PIDs refer to the worker namespace and are agent-observed; a
remote Context does not independently attest a Pod, image or mount from them.
They cover registered Executor processes, not every native/user thread, prompt,
queue, extension or autonomous I/O participant. No member count can authorize
transfer, resume, recovery or release. Restart preserves all original metadata
and changes state to RESTART_FENCED; older binaries reject schema 14.

The native family oracle now additionally requires 21 durable member rows joined
to their exact original RUN targets/origins. The stale-consumption probe must
retain its one original member through controller disconnection. Existing native
counts, actual HTTP 403, no-body/receipt, unchanged-PID and retained-hold checks
are preserved. Hosted qualification of this candidate is pending.
