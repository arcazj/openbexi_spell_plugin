# Private Context driver write boundary

This is a source implementation of the F3 write/receipt seam, not a public
runtime service or a completed v0.8 execution path. `runtime_enabled` remains
false. No worker, native bridge or IDE Run command can invoke it over RPC.

`server/src/openbexi_spell_server/effects.py` belongs to the Apache-2.0 Context
package. `driver_plugin/src/openbexi_spell_dss/fenced_transport.py` is a separate
GPL-3.0-or-later adapter derived from the original DSS transport. The original
`transport.py`, including its immutable telemetry patch preimage, is unchanged.
The fenced adapter requires an explicit `EffectAdmission` argument; the legacy
adapter remains for existing v0.7 source composition only. A future native
Context integration must select the fenced adapter exclusively.

## Admission and linearization

Only trusted Context driver code constructs an admission using an original
consumed `StartGrant`, fixed driver binding and UUID operation ID. Validation
binds the original execution and logical procedure to the actual DSS packet's
execution/procedure/operation fields. Workers cannot select another endpoint,
replace an epoch, acquire a new grant or pass a replacement admission object.
Those restrictions still require enforcement in the future native RPC adapter.

Each binary command stage independently:

1. Acquires the same per-execution mutex used by start, handoff and final
   disconnect fencing.
2. Checks the original provenance, current owner/session, control and start
   permissions, execution lifecycle and immutable configured driver binding.
3. Reserves a non-replayable authority intent and separate driver intent.
   Both ledgers retain operation ID, stage, original provenance including a
   token hash, and packet hash. Capacity is bounded; no entries are evicted.
4. Rechecks live authority, then performs the actual `socket.sendall` while
   retaining the execution mutex. The total send timeout is 200 ms and the
   packet bound is 64 KiB. SQLite transactions never span socket I/O.
5. Records SENT in both ledgers and releases the execution mutex. The original
   timeout is restored. Receipt waiting and full binary decoding happen outside
   the execution mutex, driver ledger mutex and authority database transaction.
6. Correlates the response and persists its hash under the original operation.
   ACKED means a correlated definitive response, not necessarily command success.
   Unknown/missing/indeterminate responses remain uncertain.

A failed or partial write, missing receipt or ledger commit gap retains the
logical/worker holds and fences the execution for manual recovery. Persistence
failure poisons the authority if uncertainty cannot be recorded. No automatic
replay, synthesized receipt or capacity/worker reclamation exists. Denied forged
requests cannot fence a legitimate operation. Rejected replays do not overwrite
previously settled receipts. An operation UUID cannot cross execution/provenance
bindings across its stages.

Authority schema 5 is installed when the driver gate is created. Old schema-4
binaries reject that state. The driver SQLite database has its own exclusive
process lock, DELETE journal and FULL synchronous mode. Startup marks unresolved
driver INTENT/SENT records UNCERTAIN; authority startup independently fences all
retained executions. A mismatch is preserved, never reconciled to success.
Supported target storage remains operator-provisioned local Linux ext4; these
tests do not qualify storage devices, backups or node fencing.

## Test scope and remaining blockers

`server/tests/test_effects.py` uses the actual binary DSS transport against a
separate DSS subprocess. It exercises five stages, ten independent driver
operations, receipt-wait isolation, handoff between send and receipt, live role
revocation, forged/stale provenance, endpoint/resource denial, capacity denial,
wire-identity substitution, real socket backpressure, lost release receipt,
restart and actual process death after a TCP write but before SENT commit.
Ten driver operations are not ten native procedures or Executors.

The test runner records hashes for the server, driver sources and DSS source/
data, plus separate DSS process IDs. Full G5 remains pending: the original
native bridge, Context driver lifecycle, TC/TM resource ACLs, driver journal
integration, driver-process identity and recovery across deployed services are
not qualified. The low-level seam trusts the Context driver to encode packets
and decode receipts; it is not an untrusted-worker interface. Native quiescence,
child admission and safe controller handoff after launch remain mandatory gates.
