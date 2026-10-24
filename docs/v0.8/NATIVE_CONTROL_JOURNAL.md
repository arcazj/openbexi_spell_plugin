# Private native RUN journal

This dev19 component records one agent-issued initial RUN per admitted native
member. It does not implement native dequeue fencing, whole-family quiescence,
handoff or new-owner resume. Public execution and all full release gates remain
disabled. Hosted native qualification must be tied to the exact candidate SHA.

## Implemented behavior

The optional Context configuration `native_controls: run-journal` requires the
retained launch profile. Both worker routes require the pinned worker identity,
original consumed StartGrant and the consumption winner's memory-only capability.
The Listener and gateway cannot delegate either worker operation.

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
The original native request implementation and wire bytes remain unchanged.

`control-report` accepts only `IPC_SEND_ACKNOWLEDGED` or `UNCERTAIN`. It can record
a diagnostic after controller fencing using the original immutable identity,
but cannot issue a command. Exact diagnostic replay is read-only; conflicting
reports fail. Both outcomes retain `DISPATCH_UNCERTAIN`: an IPC send acknowledgment
does not prove mailbox acceptance, execution, completion or queue settlement.
Neither report releases a reservation or spent worker. Schema 11 preserves the
rows and marks them `RESTART_FENCED` on startup, with original hashes/outcomes
intact; the original worker proof becomes unusable after authority restart.

The private child cohort wraps ten root RUNs, five visible child RUNs and one
visible grandchild RUN. Five hidden children run through native internal startup;
their existing before-spawn admission remains in force, but their internal RUNs
are explicitly outside this agent journal. Other private profiles are unchanged.

## Remaining native boundaries

Review used the source archive `docs/reference/SPELL2.6.10-src.zip` (SHA-256
`2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed`), with the
frozen v0.7 recipe at `109a47af47951e2fa54b60cb408a543b117f7f15`. The reconstructed
Context `SPELLexecutor.C` matched the before-spawn builder's required preimage.
Native paths below are inside that archive, after the frozen composition patches.

| Native path | Consequence for positive handoff |
| --- | --- |
| `lib/SPELL_EXC/src/SPELLcontroller.C`: `command`, `run`, `executeCommand` | Queued and direct dispatch both require immutable command identity and a final epoch check. SKIP/GOTO can move to a separate trace-command slot. |
| `lib/SPELL_EXC/src/SPELLcommandMailbox.C`: `push`, `pull`, `reset` | Full queues and repeated non-repeatable commands can be discarded silently. Clearing a queue must produce explicit terminal dispositions for every command. |
| `lib/SPELL_EXC/src/SPELLexecutorImpl.C`: `command`, `pause` | Direct high-priority pause is separate from ordinary queued dispatch; a main-thread pause does not settle the family. |
| `lib/SPELL_CIFS/src/SPELLserverCif.C`: message/request processing and prompt handling | Client messages, variable requests and prompt responses are distinct admission paths. A prompt timeout is not settlement proof. |
| `lib/SPELL_CIFS/src/SPELLrequestProcessor.C`: variable mutation | Direct variable/container writes bypass the controller mailbox and need the same fencing contract. |
| `lib/SPELL_SYN/src/SPELLthread.C`, IPC workers and CIF buffers | Native infrastructure and user execution participants need an explicit inventory; Python line monitoring or process enumeration cannot establish it. |

A fence can occur after Context commits an attempt but before native IPC sends.
The journal deliberately does not claim to close that interval. The regression
test injects it and requires transfer to remain BLOCKED with the original owner,
epoch and holds. Positive transfer requires authenticated native dequeue/direct-
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
