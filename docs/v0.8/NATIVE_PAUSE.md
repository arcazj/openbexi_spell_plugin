# Fenced native pause probe (development)

Development server `0.8.0.dev14` adds an explicit private Context option:
`"native_pause": "fenced-probe"`, alongside `worker_launch: retained-single-use`.
The operator-provisioned native agent additionally requires `pause_probe: true`.
Defaults and the previously qualified native audit/DSS profiles are unchanged.
This is a safety barrier and negative qualification profile. It **cannot grant
an effective native control transfer or claim whole-family quiescence**.

## Acceptance and fencing

The current controller accepts an existing claim using its original live owner
proof. Under the same per-execution mutex as final driver check/actual send,
Context atomically journals a bounded ten-second barrier, changes control state
to `PAUSING`, removes the controller capability, and records the claim as
`PAUSING`. Owner, epoch, original start identity, spent slot and logical hold
remain unchanged. Acceptance returns immediately; no worker/network wait occurs
inside that mutex or a database transaction. Other executions are unaffected.
The durable acceptance replay is historical `PAUSING`; read execution.list for
the current redacted `pause_barrier` result. No replay mints a capability.

The assigned single-consumption winner polls Context over existing pinned mTLS.
Only it can use the following exact worker-protocol-2 endpoints:

| Endpoint | Additional fields beyond schema/context_id/ORIGINAL grant/runtime_capability |
|---|---|
| POST /v1/worker/pause-poll | none |
| POST /v1/worker/pause-report | barrier_id, provider, native_status, quiescence_proven, reason |

The original certificate, grant binding, authority incarnation, worker assignment
and memory-only consumption proof remain mandatory. These **safety-only** calls
can operate after the old controller has been fenced or its role revoked, so
revocation cannot prevent a worker reporting a safety failure. This exception
confers no driver/event/start/rebind/recovery permission. Those paths still
require live controller authority and reject the old grant during PAUSING.
Copied original configuration, forged grants or guessed consumption proofs do
not acquire this reporting channel.

## Main pause is not family quiescence

The frozen native provider exposes main-Executor status and a pause command.
It has no qualified acknowledgment covering all background threads, native child
procedures and control/prompt queues. Source inspection shows a per-thread
Python trace and a main execution-model command wait; that is insufficient for
whole-family proof. The qualification probe must independently exercise this
boundary, not infer it from `PAUSED` or a PID inventory.

For RUNNING only, the agent attempts one native CMD_PAUSE and observes status.
It never automatically resumes, interrupts a prompt/WAITING state, kills a
procedure because a controller disconnects, or rewrites a grant. Its report has
fixed provider `legacy-status-only/1` and `quiescence_proven: false`. A supplied
true/invalid proof is rejected, even from a registered worker. PAUSED therefore
settles the barrier as `UNPROVEN`, not ownership transfer. A missing worker
expires to `EXPIRED`; a late report does not extend the deadline. Both leave
RECOVERY_REQUIRED with the original owner/epoch and all holds retained.

The agent retains its original consumption proof in memory. Lost report replies
can repeat the same diagnostic without redoing pause/consumption/TC; changed
reports conflict. An unavailable authority causes one local pause attempt and
retention, never automatic kill or resume. The current fixture agent's existing
180-second qualification deadline is not a production lifetime policy.

Schema 9 protects the new barrier ledger. Context restart fences original grants
and pending barriers, invalidates claims and retains all reservations/spent
slots. No state restore, worker replacement or capacity reclamation is added.
Audit/capacity failure rolls back the attempted state change. No new management
service, Docker socket, host privilege or delegated cgroup freeze is introduced.

## Required real native negative test

`scripts/qualify_v08_native_launch.py --native-pause-probe` is separate from the
positive audit/DSS cohorts. Ten real native procedures reach RUNNING. Procedure
B starts a real background Python thread updating an atomic counter in /tmp.
While all are running, its owner accepts a claim; Context must return promptly,
fence B, request native pause, and record UNPROVEN while main status is PAUSED.
The host must observe that B's background counter still advances, while A/C and
the other seven procedures remain owned and responsive. This demonstrates why
main status cannot authorize handoff. The nine unaffected procedures must finish
with original durable lifecycle receipts. Independent host teardown ends B only
after this evidence is collected; every slot/logical hold remains retained.
That teardown is qualification cleanup, not runtime pause proof or recovery.

The hosted pause-probe job must pass at the candidate SHA, retaining source/image
identities, failed attempts and redacted evidence. Local RPC/unit tests do not
satisfy it. `native_pause_qualified` and full v0.8 stay false even if this negative
probe passes.

## Confirmed hosted result

At code **34f201d**, [PR run 40010794562](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794562)
passed all five jobs: 290 scoped tests/package checks, native-boundary, audit,
DSS, and the new pause probe. The [241-test portable compatibility run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794672)
also passed. This remains a named subset, not all-763 or full release coverage.

The native probe observed main B **PAUSED** while its background counter advanced
**89 to 99**. The barrier reported UNPROVEN/BLOCKED, preserved owner/epoch and
ten holds/spent slots, and the other nine native procedures completed. Maximum
observed unrelated-controller latency in ten reads was **12.8 ms**. Independent
host teardown then ended B; it was not a native completion or quiescence proof.
Thirty distinct running native PIDs were observed before the barrier. All 17
captured runtime hashes matched the candidate. The downloaded artifact was
CRC/digest checked. See the [redacted receipt](evidence/native-pause-probe/qualification-summary.json).

This confirms the provider gap and the safe barrier behavior. It does **not**
qualify positive native family pause, transfer/resume, children or recovery.

## Work still required

A supported native provider must acknowledge all participating threads/children,
settle admitted effects, and drain control/prompt queues before Context can CAS
owner/epoch. Unknown/uncooperative participants must keep the barrier failed.
After proven transfer, the new owner must explicitly resume with a separately
admitted immutable operation grant; old autonomous requests cannot be restamped.
That provider, successful live handoff/resumption, native child admission and
full recovery remain unfinished. G1 F2/F3/F4/F8 remain mandatory release gates.
