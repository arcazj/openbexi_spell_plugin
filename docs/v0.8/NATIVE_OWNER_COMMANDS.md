# Fresh owner commands: private development profile

`0.8.0.dev32` adds the opt-in Context setting `native_commands: owner-queue`.
It requires `native_controls: run-journal` and the retained native child/member
profile. The default public Listener/gateway method inventory is unchanged.
Only the trusted certificate-authenticated listener-to-Context RPC can enqueue
`execution.command`; the public runtime remains disabled.

The current owner supplies its execution, connection, connection generation,
expected control epoch and capability, plus `target_admission_id` (null for the
root) and exactly `CMD_STEP` or `CMD_PAUSE`. STEP requires current start and
control permissions. PAUSE requires current control permission. Live policy,
connection, ownership and capability checks precede idempotency replay. The
member must already have its original durable registration. Unknown children,
argument-bearing commands and redirects are not admitted.

The authority commits an immutable intent before delivery. It issues a separate
256-bit command token once, valid for 30 seconds, bound to the exact original
worker identity, member binding, owner, epoch, connection and command digest.
Only token hashes and canonical grant bindings are persisted. The startup grant
and memory-only consumption-winner capability authenticate the original worker
channel; they cannot create an interactive command. Original startup epochs and
connections are never restamped. A future new-owner runtime protocol is still
required; this profile deliberately cannot resume under a transferred owner.

Delivery, native Context forwarding and actual Executor consumption each have
separate single-attempt transitions. Live owner/session/policy/expiry and member
checks are repeated at forwarding and consumption. The agent records attempts
before RPC/IPC; response loss, forged replies and send uncertainty do not retry
or redeliver a command. Restart fences all retained rows. Queue bounds are 64
pending and 512 retained per execution, 4096 per Context; reaching capacity
rejects new intents without discarding old ones.

The rebuilt native candidate carries both the immutable ID and an external-
command marker through command value copies and the mailbox. Final admission
precedes STEP/PAUSE processing. Internal native safety pauses retain their
original behavior. A nonempty native `ParentId` is rejected for the admitted
RUN/STEP/PAUSE set because it could redirect a member-specific grant.

`EXECUTION_UNPROVEN` means permission was granted at the final admission point;
it does not acknowledge native completion. A disconnect after that point cannot
retroactively cancel an effect. A safe handoff therefore still requires a real
all-participant barrier and disposition of all in-flight commands/prompts. An
IPC send acknowledgment, PAUSED status or PID inventory cannot prove this.
Commands may be discarded by the original native mailbox after admission.
No reservation release, worker reuse, quiescence or effective transfer follows
from a command receipt or diagnostic. Other native mutations remain outside
this increment and must be fenced before exposing public control.

## Qualification

The new real-mTLS test module has **54 passing tests**, including concurrent
idempotency, current-owner and worker identity checks, copied credentials,
expiry, disconnect at every phase, audit rollback, restart, exact child targets,
queue capacity, lost delivery/forward/consume replies and uncertain native send.
These tests use controlled native callbacks and do not substitute for the real
native Executor probe.

The private native cohort now also provisions isolated Context C with one
worker and an unstarted witness. An actual owner STEP must execute `FIRST = 1`
and leave `SECOND` absent, checked through native read-only variable retrieval.
The next fresh STEP is held inside C++ before final consumption and before the
ordinary socket deadline starts. The host waits five seconds, durably closes
the original controller, then releases that hold. The oracle requires actual
HTTP 403 at consumption, exactly one consumed STEP, unchanged native PIDs,
original owner/epoch, retained member/holds/spent worker, absent second effect,
and unchanged unrelated executions. Context A's 21-member family and Context B's
initial RUN stale-consumption tests remain required. Host teardown is independent.

Dev32 at `644730d` passed the push native cohort, including the actual owner
STEP/stale-consumption oracle, 21 original family members, 41 PIDs and 42 real
lifecycle events. All 31 repository inputs and 144 compiled source units match.
The hosted service suite passed **544 tests**, zero failures/errors/skips,
including the mandatory process-isolation controls. See `dev32-family.json` and
`dev32-foundation.json` in `evidence/native-child-start/`.

The same-source PR native family failed before reaching the owner probe:
Docker recorded an OOM kill in worker 0 at its inherited 768 MiB limit. The
failed receipt is retained. Dev33 assigns bounded family-test limits of 1536 MiB
for the three-Executor nested worker and 1024 MiB for the other two-Executor
workers, verifies actual cgroup peak/limit/OOM counters, and checks the final
Docker memory configuration. This is a qualification-resource correction, not
production capacity qualification. Hosted dev33 requalification is pending.
Deadlines, single-attempt commands, logical holds and authority checks do not
change. Native PAUSE effects and reliable full-family operation remain unqualified.
All eleven full-release gate groups remain false.
