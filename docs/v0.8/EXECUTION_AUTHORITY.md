The default prelaunch contract below remains applicable. The explicitly enabled
retained native profile adds the admission/consume/check/event routes described
in [NATIVE_LAUNCH.md](NATIVE_LAUNCH.md). It does not enable general public runtime,
prove native quiescence or release any hold. Historical dev2 claims below refer
to that original subset.

# Durable prelaunch execution authority

The original dev2 subset below is extended by dev3
[WORKER_PREFLIGHT.md](WORKER_PREFLIGHT.md): configured approved source catalogs
and pinned single-host worker preflight. Metadata-only reservations stay
unverified and cannot pass the Context start guard. Native launch remains absent.

Implementation: `server/`, development package `0.8.0.dev2`. This implements a
bounded prelaunch registry and controller protocol. `runtime_enabled` remains
**false**. No native procedure, driver effect or worker network endpoint is
launched by this package. Passing these tests does not pass G2/E or G3/F.

## Public internal routes

All requests retain SERVER_CONTRACT.md's pinned TLS roles, Context scope and
Context-local ACL. The term "session" below means an explicit logical internal
controller connection; it is not a browser cookie, TCP connection or WSS lease.
Closing an ordinary HTTP request does not close this logical connection.

`GET /v1/contexts/{id}/executions` requires `execution:read`. It returns bounded
redacted execution/owner/epoch/control-state records and pending claim ID,
requester and expiry. It exposes no capabilities, worker credentials or source.

`POST /v1/contexts/{id}/authority` carries exactly `method` and `payload`, plus
one `Idempotency-Key` header. The internal Context RPC uses the same method and
payload in its existing envelope. Only the methods below are exposed.

| Method | Context-local permission | Exact payload fields |
|---|---|---|
| session.open | execution:control | none |
| session.close | execution:control | connection_id |
| execution.reserve | execution:start and execution:control | procedure_id, connection_id, source_revision, source_sha256, runtime_image, driver_binding |
| execution.claim | execution:request_control and execution:control | execution_id, connection_id, expected_epoch |
| execution.decide | execution:control plus current owner proof | execution_id, connection_id, expected_epoch, connection_generation, capability, claim_id, decision |
| execution.cancel | execution:request_control plus requester binding | execution_id, connection_id, claim_id |
| execution.rebind | execution:control plus stable current owner | execution_id, connection_id, expected_epoch |

IDs are canonical server-generated UUIDs; logical ProcedureIDs and driver
bindings are bounded identifiers. Epoch/generation fields are positive bounded
integers, excluding booleans. Decision is `accept` or `reject`. Capabilities
are 256-bit random secrets, represented as 64 lowercase hex characters.
Source revision is a 40-character Git SHA, source digest 64 lowercase hex and
image `sha256:<64 lowercase hex>`. Extra owner, role, worker-slot or Context
fields are rejected. Existing ACLs receive no new permission implicitly.

Source/image/driver fields are **declared metadata**, stored immutably with the
reservation. This increment does not fetch/verify Git, inventory actual files,
resolve logical aliases, authorize a driver resource, or attest an image.
The native launch route stays absent until those checks and worker integration
exist. A caller-supplied digest alone is not a trusted source snapshot.

## Reservation and handoff linearization

A Context transaction selects one configured unused worker slot and atomically
reserves ProcedureID, creates ExecutionID, stores metadata, initial owner,
epoch, connection binding and hashed capability, and appends its event.
The reservation table has a database primary key on logical ProcedureID.
Changed revision/digest does not bypass that key. Contexts have independent
namespaces; this is not cross-Context external-resource exclusion.

A claim binds the requester to its active authenticated logical connection,
current owner and expected epoch. One pending claim per execution is enforced
by a partial unique index. Server time enforces the 60-second expiry during
decisions and replacement claims. Reject, cancel and expiry preserve ownership.
Acceptance rechecks the requester's current permissions and active connection.

Start admission, start consumption, rebind and claim acceptance use the same
per-execution mutex, followed by a short SQLite transaction. The mutex has a
250 ms acquisition bound and is never created for unknown execution IDs.
No network wait occurs in a SQLite transaction. Unrelated executions continue
when another execution's admission mutex is held.

A prelaunch barrier is proven only while lifecycle remains `RESERVED`: no
start grant has been consumed, and the future worker must not enter user code
before successful consumption. Acceptance revokes any unconsumed grant, then
changes only that execution's owner/epoch/connection and appends both decision
and owner events in one transaction. Once consumption has reached `STARTING`,
acceptance cannot prove native quiescence. It returns durable `BLOCKED`, keeps
the old owner/epoch and reservations, clears the capability and sets control
state `RECOVERY_REQUIRED`. It does not report PAUSED or grant the claimant.

Acceptance returns a redacted durable decision to the old controller. The new
owner must authenticate and explicitly rebind to obtain its own fresh secret;
there is no secret delivery to the accepting old owner. This is the qualified
initial delivery protocol, not a browser push notification. Rebind increments
connection generation and invalidates old capabilities, claims and unconsumed
grants. It does not transfer ownership or increment the control epoch.
Rebind is allowed only before consumption, never as a recovery shortcut.

## Immutable start-grant integration seam

There is deliberately **no** RPC for `execution.start`, worker consumption,
native control, driver sends, reservation release or recovery. The module's
private integration API is tested independently:

1. `admit_start` checks a current authenticated controller proof and issues an
   immutable grant **before** any worker request. It binds authority incarnation,
   execution, configured worker slot/incarnation/generation, controller epoch,
   logical connection/generation, server request UUID and operation digest.
   Only a token hash and canonical binding are stored; repeated admission fails.
2. `consume_start` takes that exact grant plus an independently authenticated
   worker identity. Under the same mutex/transaction it checks original binding,
   marks the worker incarnation spent and records STARTING once. It cannot mint
   or restamp a grant. A duplicate or mismatched worker cannot consume again.
3. `validate_start_grant` checks original provenance and current fencing. It
   does not authorize a driver effect or prove that native code has started.

The original dev2 protocol tests call this private seam directly. They **do not authenticate
a worker certificate or Kubernetes Pod UID**. The future network adapter must
provide that authentication; labels, worker-supplied UID and shared ServiceAccount
are insufficient. No code outside the tests currently calls this seam.
Configured slots are a development registry, not proof of deployed containers.

A delayed old grant remains invalid after transfer and new-owner rebind. Only a
new owner-authorized operation can issue new provenance. Lost consumption
responses retain a spent slot and logical hold; no timeout, TTL, heartbeat,
Job status, certificate change or restart clears them. Initial workers are
single-use. Replacing an existing slot's incarnation is refused at startup.

## Durability, replay and recovery

Schema 2 adds authority tables to the separate foundation database in one
transaction; existing blackboard state is retained. Published v0.7 state is
untouched. Old foundation code rejects schema 2; downgrade is unsupported.
On each Context startup, existing executions retain owner/history and logical
and worker holds, advance epoch and connection generation, lose all capabilities
and grants, and become `RECOVERY_REQUIRED`. Sessions close and claims invalidate.
Listener restart does not change Context authority or logical connections.

Live permission checks precede idempotency lookup. Keys are scoped to subject,
method and execution, or Context for connection/reservation creation. Changed
payload conflicts; recorded decisions are historical and carry `replayed: true`.
Read current execution state separately. Plaintext capability outputs are never
stored or returned on replay. A lost prelaunch capability response requires a
fresh explicit owner rebind and key. A Context restart cannot recover authority
by replaying an old response, presenting an old token or opening a new session.

Explicit connection close fences associated controllers without terminating a
runtime or promoting a claimant. Late close of an old connection cannot fence a
rebound one. Automatic WSS heartbeat/grace handling remains unimplemented.
Native release, UNOWNED acquisition, emergency override and manual reconciliation
have no exposed operation. Old-worker/node/egress fencing and external-effect
settlement remain prerequisites for a future qualified recovery mechanism.

Bounds are retained, not silently recycled: ten worker slots, 64 execution
records, 256 claims, 128 logical connections with 16 per subject, and the
configured audit/idempotency capacities. This initial profile exposes no
capacity-reclamation operation. Restart does not replenish spent slots or
reservations. Full capacity or SQLite failure denies further mutations; audit
failure rolls back state, ownership and worker-consumption changes atomically.

## Evidence and remaining gates

See TEST_REPORT.md and `evidence/execution-authority/`. Tests include 100-way
reservation/start-consumption races; ten distinct slots (not native processes);
claim/accept and start/transfer races; A/B/C isolation; forged capabilities and
generations; expiry/rejection/cancellation; permission revocation; response loss;
late disconnect; bounded mutex waits; audit/SQLite failure; restart; and real
process death after start-consumption commit. Real service processes also prove
Listener restart preserves ownership and Context restart retains holds/fences.

Native processes/descendants, source inventory/alias policy, prompt/debug queues,
actual-send ordering and uncertain-effect settlement, mTLS worker/Pod identity,
Docker Compose, Kubernetes admission/RBAC/network/storage, browser/WSS and
v0.7 compatibility qualification remain pending. Those require their own real
boundary tests; this ledger cannot satisfy them by changing a status label.
