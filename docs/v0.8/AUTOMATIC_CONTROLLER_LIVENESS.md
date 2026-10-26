# Automatic controller-loss fencing

Server development candidate 0.8.0.dev56 and paired IDE 1.2.1.dev5 add authenticated controller leases. This is a component of v0.8 qualification, not a completed release gate.

Every Context constructed with the retained native launch profile requires a lease. Its default is 30 seconds; `controller_liveness_seconds` accepts integers from 5 through 300. False, zero and out-of-range values are rejected. Prelaunch-only profiles retain their previous behavior unless explicitly configured with a lease. The authority database advances to schema 23, so an older binary cannot silently reopen this state.

`session.open` delivers a one-use heartbeat challenge. `session.heartbeat` requires the same authenticated subject, connection and current challenge, and returns the next challenge. Deadlines use a monotonic clock. Replayed, delayed or cross-subject challenges cannot extend a lease. A lost acknowledgement is not retried. Only challenge hashes are persisted; open-request replay omits the secret and requires a new session. One lease row per retained session bounds storage; beats do not append audit or idempotency rows.

The authority checks the deadline at control admission and final grant validation, independently of the cleanup thread. Expiry first closes admission for all overdue sessions, then takes execution mutexes outside SQLite transactions to finish durable fencing. An execution rebound to a newer connection is protected against late cleanup. Audit/storage failure fails the authority closed. Store and Context shutdown stop the watchdog.

Expiry removes control permission. It does not prove native quiescence, terminate a family, free a reservation, replenish a worker, promote an observer or resume an execution. Recovery still requires a fresh session, the original host-attested family freeze, a new connection generation and explicit resume. Cleanup of an already expired session acknowledges its completed fence without changing a successor connection.

The IDE renews at one-third of the lease interval on a background worker. Heartbeat TLS requests are independent of ordinary request I/O. If renewal fails, it discards only that connection's local controller proofs and stops renewing it. Closing a panel stops heartbeats; one already in-flight request can still commit, so server expiry is measured from the last accepted renewal. Explicit reconnect opens a new session for a disconnected live execution or reservation. There is no automatic command retry, epoch repair or resume.

## Qualification scope

The deterministic authority tests cover challenge rotation, replay and late denial, live permissions, monotonic time, restart, mutex contention, rebind races, bounded storage, audit exhaustion, watchdog shutdown, expired-session cleanup and mandatory native-profile defaults. Four hosted TLS cases cover actual client PID death, lost heartbeat replies, stalled replies and a TCP endpoint that accepts but never completes TLS. Host freeze evidence in those service cases remains an explicit fixture.

The native handoff and installed-IDE cohorts detach heartbeat delivery without sending `session.close`. They wait for automatic fencing, check independent observers and denied old traffic, and require host-proven recovery of the original family. Their controller-loss injection is heartbeat transport detach, not a claimed deployed node partition. The existing explicit-close/rebind/activation fault cases continue to run.

The longer initial native runs hit the old 768 MiB probe cap and Docker reported OOM kills. The two-executor recovery probe now uses the primary two-executor profile's 1 GiB cap, with cgroup current/peak/limit/events recorded at counter observations. This resource-profile correction does not establish bounded memory over an indefinite execution or resolve historical startup/DSS failure causes.

Full deployment partitions, browser/WSS behavior, long-duration load, restore/upgrade/rollback and the other full-release criteria remain unqualified. All eleven release gates remain false. Source-bound results and failed attempts are retained in `evidence/controller-liveness/`.

## Executed qualification

1,234 service tests, 95 overlapping fault tests and 241 portable tests pass with zero failures/errors/skips. All fourteen core jobs and five ancillary workflows pass. The paired IDE passes 282 tests with one Windows-only skip. Nineteen server archives plus one IDE archive, source inventories and wheel contents are verified. All eleven full-release gates remain unqualified. Candidate `bad5f984e5be852dba70ed959fa73203d16b5639` pairs IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. See [the receipt](evidence/controller-liveness/qualification-summary.json) and [the hosted run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40283981575).

Both native cohorts record a cgroup memory peak of 1,073,750,016 bytes against a 1,073,741,824-byte limit (8,192 bytes above the reported limit), with 3,369 and 2,957 limit events and zero OOM/OOM-kill events. This is evidence of substantial pressure, not a long-duration resource qualification. Automatic detection took 27.47 seconds in the native route and 24.90 seconds through the installed IDE.
