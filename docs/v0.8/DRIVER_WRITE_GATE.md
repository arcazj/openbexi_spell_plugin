# Private Context driver write boundary

This is the F3 write/receipt seam used by the optional retained native audit/DSS
profiles. Public runtime and all full release gates remain disabled. The worker
route requires its pinned mTLS identity, original consumed StartGrant and the
winning agent's memory-only capability. No browser/Listener delegation can call
it. Resource permissions and endpoints are fixed by the Context operator.

The Apache Context package owns `effects.py`; `context_driver.py` and
`fenced_transport.py` remain separate GPL adapters. The original v0.7 transport
and immutable composition preimages are preserved. This component does not
qualify native family quiescence, handoff/resume or production driver lifecycle.

## Admission and linearization

Only trusted Context code constructs EffectAdmission from the original grant,
configured binding and request UUID. Packet procedure/execution/operation fields
are derived here. The worker cannot choose another endpoint, epoch or admission.
TC options remain bounded and effect-changing options remain denied.

The native RPC journal's identity reads, nonce admission and completion checks
use atomic ContextStore transactions. Each checks current authority; these
records cannot authorize a physical write. Removing them from the execution
mutex does not remove the independent final send check.

For each binary stage:

1. Enter the bounded, reentrant FIFO driver ledger writer. The queue holds at
   most 64 waiting handlers; a new stage cannot barge ahead of existing waiters.
   Receipt waiting happens after this writer is released.
2. Check live original authority and commit the authority INTENT, then the driver
   INTENT. Both store original provenance, packet hash, operation and stage;
   neither is replayable. No entry is evicted to reclaim capacity.
3. While still owning the writer, acquire the same 250 ms execution mutex used
   by final controller fencing. No holder waits behind another ledger writer.
   Recheck live owner/session/policy/start permission and binding.
4. Check the Context-owned absolute TC deadline immediately before send. The
   actual socket timeout is the smaller of 200 ms and its remaining budget.
   Perform sendall under the execution mutex. SQL transactions span no network
   I/O. An expired queued operation cannot later write.
5. Commit SENT in both ledgers before releasing the execution mutex. A partial
   send or SENT transition error records uncertainty and fences under that same
   mutex. Restore the socket's original timeout.
6. Release the writer before receiving/decoding the binary receipt. Settlement
   reacquires only the FIFO ledger writer and commits both ACKED records for the
   original SENT operation. ACKED is a correlated definitive response, including
   a definitive failure; it cannot restore control authority or release a hold.

The lock order is **ledger writer → execution mutex → store transaction**.
Settlement needs no execution mutex. Concurrent uncertainty uses this same
order and rechecks the original row under the writer, so it cannot downgrade a
receipt already committed in both ledgers. If uncertainty cannot be persisted
or fenced, the Context is poisoned and retains every hold. This conservative
failure closes all authority admission in that Context; full fault/isolation
qualification remains pending.

TC operations retain the existing maximum three-second timeout. Their absolute
budget begins in Context request preparation and includes subsequent queuing.
The worker driver RPC now has the documented five-second response budget;
previously its two-second client socket could abandon a still-permitted
operation. TCP/TLS connection timeout remains two seconds, the server/watchdog
budget remains five, and other RPC response sockets remain two seconds. The
three-second test HTTP helper was likewise inconsistent with this driver
budget; only driver tests select five seconds. This correction does not prove
the cause of every earlier stress timeout.

Any missing/uncertain response, crash gap or failed intent remains non-replayable.
No automatic worker reuse, synthesized receipt or reservation reclamation exists.
Authority restart fences old grants and retains state; ledger mismatches are
preserved. Schema 5 established these effect tables; newer authority migrations
retain their meaning and reject unsafe binary downgrade. SQLite uses exclusive
process ownership, DELETE journaling and FULL synchronous mode.

## Qualification scope

Real protobuf/mTLS tests call an independent DSS subprocess and compare both
ledgers. Tests cover five stages, ten pending streams and overflow denial,
original identity, grants/policy, endpoint/resource denial, real backpressure,
late/missing receipt, concurrent uncertainty, and actual process death after
write but before SENT commit. New regressions hold INTENT or receipt bookkeeping
while a controller fences, deny an expired queued send, and keep authority
closed if unresolved-effect fencing cannot be recorded. The old implementation
fails the three fencing/poison regressions; its two-second client also fails the
controlled delayed-response regression.

Dev25's final exact-source hosted results are recorded in TEST_REPORT.md when
available. Local scoped tests and stress do not qualify driver reset, deployed
partitions/storage, full native family control, recovery or v0.8 publication.


## Incomplete operation before a later intent

Dev29 closes a gap exposed while investigating a native deadline failure.
If a later stage expires before INTENT, prior stages with the exact original
operation/execution/provenance still require reconciliation. The gate preserves
their real ACKED receipts, creates no fictional stage, and fences that execution
with DRIVER_OPERATION_INCOMPLETE and RECOVERY_REQUIRED. Foreign and never-started
operations cannot obtain this effect; a fully settled receipt stays settled.
Failure to persist the fence/audit poisons the Context so rollback cannot leave
usable authority. Holds remain retained. Deterministic before/after tests cover
both pre-effect and post-release boundaries plus audit failure and unrelated
execution/foreign-origin controls. This does not solve native two-second
performance, driver lifecycle/reset or full deployed recovery qualification.
