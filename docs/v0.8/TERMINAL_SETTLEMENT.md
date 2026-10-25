# Private single-host terminal settlement

The optional `host_settlement` configuration selects
`single-host-terminal-candidate` and pins a dedicated host certificate. This
identity must differ from every worker and the Listener. The host private key
stays outside worker containers. The host is a trusted deployment principal,
not an authenticated browser claiming to have observed process exit.

The host binds an exact Docker container ID and approved immutable image before
worker consumption. Binding is immutable and single-use. Starting without that
binding is denied. The host records the terminal observation, obtains a durable
Context fence, then allows the worker's native cleanup. The fence removes owner
mutation authority and cancels pending transfers. Existing driver receipts and
prompt outcome reports can still settle, but no new work is authorized.

After cleanup the host inspects the same container and image, checks exit 0,
no OOM/restart, and readiness of every captured original process pidfd. Docker's
stopped private PID namespace covers descendants that appeared after capture.
No numeric PID alone is accepted as identity proof. The retained native worker
has no privileges, host PID namespace, writable cgroup mount or container daemon
socket with which to escape this boundary. This is not Kubernetes attestation.

The host returns that evidence with Context's one-use challenge and family
roster digest. Context independently checks its original member and child
journals, closed prompt outcomes, and external effects. Every external operation
must have all five ACKED stages and identical packet, provenance and receipt
hashes in the Context and driver ledgers. A partial operation, disagreement,
unknown outcome, missing member, open prompt or failed audit keeps all holds.
Checking and committing use the driver's ledger lock, execution mutex and
Context transaction in that order; network and container operations stay outside.

Verified process exit retires future native queue execution. Original command
records and mailbox dispositions are preserved: exit does not manufacture a
missing handler result or prove a particular command succeeded. Forced native
loss is recorded as UNKNOWN and stays held even when every process has exited.

The authenticated host must explicitly release a SETTLED record using its
challenge and report hash. Only that execution's logical reservations are
deleted. Worker incarnations remain spent, original runtime credentials are
revoked and the execution history is retained. A later reservation can use a
different unused worker. This does not add worker-slot recycling or unbounded
capacity. Exact replay is idempotent; changed evidence conflicts. Context
restart fences all unreleased evidence; replay cannot authorize reclamation.

Private endpoints, all POST with `openbexi.host-terminal/1`, Context ID,
ExecutionID and current authority incarnation:

| Endpoint suffix `/v1/host/terminal/` | Additional fields |
|---|---|
| `bind` | `container_id`, `image` |
| `begin` | `container_id`, `native_status` |
| `complete` | `challenge`, `evidence` |
| `release` | `challenge`, `report_hash` |

The native terminal cohort includes forced loss and all previously qualified
ABORT/CLOSE, child, thread, prompt, completion/error and scheduler-wait cases.
It now requires host binding, durable fencing, actual container/process cleanup,
Context reconciliation, exact replay, and either scoped release or retained
UNKNOWN holds. An unrelated witness reservation must survive every case.
Foundation tests use real mTLS and an independent DSS process, including complete,
partial, uncertain and contradictory receipt histories, restart, audit failure,
forged identities and delayed queued work.

This is terminal settlement only. Live-family safe pause, accepted controller
transfer, new-owner resume, deployed recovery and public release remain gated.
No full-v0.8 release gate is changed by enabling this private candidate.
