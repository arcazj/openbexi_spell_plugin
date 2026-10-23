# Proposed execution admission and supervision

`TARGET-v0.8`. Binding F1/F4/F6/F8 decisions are in
[G1_REVIEW_RESOLUTION.md](G1_REVIEW_RESOLUTION.md). Context owns the transaction, worker registry and reservations.
There is no independent execution-manager process.

Identity is `(ContextID, ProcedureID)` for logical exclusion. ExecutionID is a
new server-generated UUID per attempt; immutable Git SHA, full source inventory,
runtime image digest, driver binding and procedure fence are recorded alongside
it. File rename, branch switch or changed code cannot evade a live logical
reservation. Different Contexts may run the same ProcedureID unless a future
explicit site policy introduces a shared external-resource lock.

Under `BEGIN IMMEDIATE`, reserve a logical procedure and worker slot, persist
launch intent, source digest, generation and initial owner/epoch, then commit
before launch. Enforce a unique active reservation in the database as well as
the in-process authority lock. An ambiguous worker-start response retains the
reservation; do not launch a second worker on timeout. Context startup obtains
an OS authority lock before recovery.

Lifecycle: `RESERVED → STARTING → PAUSED/RUNNING → STOPPING → terminal` with
explicit pause/prompt/debug substate. Any ambiguous launch, worker disappearance,
external effect or shutdown becomes `RECOVERY_REQUIRED` and remains reserved.
Only confirmed whole-worker quiescence releases a run slot. Terminal and logical
identity histories remain auditable. No stale lock has a TTL that can authorize
another copy. Restart creates a new ExecutionID only after safe reconciliation.

Compose assigns one active execution to each static worker container. Each
worker supervises the native adapter and all descendants using a private run
directory and generation. The initial worker is single-use: automatic reuse is disabled. Only operator
recreation after descendant shutdown and effect reconciliation replenishes its
slot. A future reuse mechanism needs independent qualification. Container-level CPU/memory/
PID/filesystem bounds apply per active execution. No unrestricted Docker socket
is needed. Kubernetes uses idempotently named Jobs plus one durable authenticated
worker-incarnation start grant. Job/Pod status, names, labels and heartbeat
timeouts never authorize replacement. A node partition is not proof of termination.

Each Context owns a concurrency-safe blackboard, deliberately shared by its
procedures. Reads/subscriptions and owner-authorized writes have a revision
contract; compare-and-swap prevents silent lost updates. Context B cannot read
Context A's data or driver credentials. Source snapshots are read-only and
unique per execution, and parallel developer branches never modify them.

Qualification requires 10 concurrent distinct procedures and unique executor
PIDs/Pod IDs, at least two Contexts, 100 concurrent duplicate starts producing
one reservation, aliases/revisions/renames, worker crash, blocked-driver pause,
abort, lease/owner transfer, Context/Listener restart and uncertain-effect holds.
No v0.8 result has been collected yet.

Native children reserve their logical identities in this same Context namespace
before native RUN and inherit the execution-family grant; see F8.
