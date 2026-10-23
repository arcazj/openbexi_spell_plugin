# Internal Listener and Context foundation contract

Status: internal services and prelaunch authority contract. Browser sessions/WSS,
native procedure execution, worker network launch and driver effects remain
separate qualification gates. The bounded reservation/claim/handoff extension is
specified in [EXECUTION_AUTHORITY.md](EXECUTION_AUTHORITY.md). Optional approved
source catalogs and single-host worker preflight are specified in
[WORKER_PREFLIGHT.md](WORKER_PREFLIGHT.md).

## Trust profile

TLS 1.3 is mandatory. Both directions verify a configured CA, server hostname,
and registered SHA-256 leaf-certificate fingerprints. CA membership alone never
assigns a role. Revocation is an explicit policy/configuration update followed
by service restart; all requests independently consult the loaded policy.
Live certificate rotation/reload is not implemented in this first profile.

The only caller of Listener is the configured TLS edge, identified by its
pinned certificate. The edge validates the user's certificate and strips all
incoming identity headers before setting exactly one
`X-OpenBEXI-Client-Fingerprint` header. Listener maps this registered fingerprint
to a stable subject and local Context permissions. It rejects browser Origin,
cookies, bearer credentials and unknown/duplicate identity headers in this
internal qualification profile. Do not expose it as a browser-facing service.
There is no trusted forwarded role or user-provided Context URL.

Listener calls only configured HTTPS Context addresses. It checks the Context
certificate pin before transmitting a delegation. Context accepts only its
configured Listener fingerprint and looks up the delegated subject in its own
Context-local ACL; a Listener body cannot assign permissions. Worker/edge/user
certificates cannot call user-delegation Context RPC, even under the same CA.
Explicitly registered worker pins may call only the separate challenge/verify
preflight routes; that role cannot claim a user identity or consume a start grant.

## RPC envelope

Listener POSTs to `/v1/rpc`, `Content-Type: application/json`, with exactly:
`schema` (`openbexi.context/1`), server-generated `request_id` UUID,
`context_id`, `subject`, `issued_at`, `deadline`, `method`, `payload`,
`payload_sha256` and `idempotency_key` (null for reads). Timestamps are seconds
since epoch, with an at-most-five-second lifetime and one-second clock skew.
An expired/overlong envelope, wrong scope, malformed UUID/hash, unknown field,
duplicate key, nonfinite number, oversized/deep JSON or role mismatch is denied.
Authenticated TLS binds the short-lived delegation to the configured Listener
and Context; it is not a reusable bearer token and contains no client roles.

Each connection handles one request and closes. Maximum body/response is 64 KiB;
JSON depth is at most 16; handler count is bounded; TLS/read/connection deadlines
are bounded. No mutation is automatically retried. Unsupported routes fail
closed. Configuration controls Host allowlists; Host is never used for routing.
No secrets, control capabilities, source paths or private keys appear in URLs,
request logs or public health/snapshot responses.

## Initial route and permission matrix

| Listener route | Context RPC | Context-local permission |
|---|---|---|
| GET /v1/health | none | registered user, registered edge |
| GET /v1/contexts | none | contexts visible to that subject only |
| GET /v1/contexts/{id}/health | health | context:read |
| GET /v1/contexts/{id}/snapshot | snapshot | context:read |
| GET /v1/contexts/{id}/blackboard | blackboard.get | blackboard:read |
| POST /v1/contexts/{id}/blackboard | blackboard.cas | blackboard:admin |
| GET /v1/contexts/{id}/procedures | source.catalog | execution:read, configured catalog only |
| GET /v1/contexts/{id}/executions | execution.list | execution:read |
| POST /v1/contexts/{id}/authority | explicit session/execution methods only | EXECUTION_AUTHORITY.md matrix |

Context discovery reports configured scope, not cached claims of live health.
Every forwarded request re-establishes TLS/pin verification; unavailable/stale
Context endpoints return bounded 503. Registry changes are configuration and
restart only, not caller-supplied registration or automatic Context launching.

Blackboard CAS payload is exactly `key`, `expected_revision`, `value`.
Keys are bounded identifiers; new key revision is zero. Success increments
that key's revision and the Context sequence atomically with its durable event
and idempotency record. Revision mismatch returns 409. Authentication and live
permission evaluation precede returning a stored duplicate result. The
idempotency key is scoped to subject/method and canonical payload hash; changed
payload is a conflict. At ledger capacity, reject new mutations without deleting
prior records. Snapshot sequence and blackboard rows come from one transaction.

## State, lifecycle and limits

Each Context has a distinct state directory, OS lock, SQLite database, service
certificate and ACL. State records ContextID and rejects reuse by a different
Context. Initial implementation is Linux only. Read/write transactions are
short and contain no network calls. Each startup creates a fresh incarnation
and appends a durable service event; blackboard revisions/sequences persist.

The service owns only its HTTP handlers/state connection. Listener shutdown or
restart never signals, launches or terminates Contexts/workers. Context shutdown
does not control Listener. Health advertises `runtime_enabled: false`.
Prelaunch reservations and ownership are explicit routes above; there is no
native launch or effect path hidden behind this API.

The audit and idempotency limits are explicit startup limits. New operations
fail closed when capacity/storage is unavailable. Credentials and private state
never appear in snapshot responses. HTTPS framing and policy tests use actual
TLS sockets, independent service processes, private test certificates and
concurrent requests. These tests cannot satisfy native SPELL/Compose/K8s gates.

## Explicit retained native profile

NATIVE_LAUNCH.md defines the opt-in Context-only `execution.start` admission and
worker-only `/v1/worker/consume`, `/check`, `/event` routes. They are disabled by
default; the normal gateway/Listener does not route a general native start.
Admission requires live owner/start/control proof. Consumption/checking require
the registered assigned worker certificate and original grant. Native audit
writes additionally require current live control and the `context-audit`
binding; scope is procedure-only. No driver response is acknowledged before the
Context transaction commits. Native external TC/TM methods remain unavailable
in this default audit-only profile.

The separate optional GPL host in [NATIVE_DSS.md](NATIVE_DSS.md) adds
`POST /v1/worker/driver` only with an explicitly configured retained launch and
Context-owned DSS adapter. Admission requires the registered assigned worker
certificate, original consumed grant, live owner/start/control permission and
fixed inventory binding. Only the five documented original TC/TM methods and
explicit resource allowlists are accepted; all other methods/identities are
denied. Payloads are bounded original protobuf bytes, never endpoints or new
authority. This route does not enter the gateway/Listener/IDE matrix or enable
the public runtime. Native/deployment qualification remains separately gated.


## Optional fenced native pause safety routes

[NATIVE_PAUSE.md](NATIVE_PAUSE.md) defines the explicit `native_pause: fenced-probe`
profile, its protocol-2 `/v1/worker/pause-poll` and `/pause-report` routes and
schema-9 ledger. Original assigned worker identity and the single consumer's
memory-only proof are required. These two safety-only calls can report after
controller fencing/revocation; they grant no driver/control/recovery permission.
Every driver/event/check route retains live original-grant checks. No supplied
PAUSED status/Boolean can authorize transfer. This profile always retains old
ownership and holds when thread/child/queue quiescence is unproven.

The optional dev15 [background Python component](NATIVE_THREAD_BARRIER.md)
does not change those Context routes or their proof requirements. Its private
worker-local 127.0.0.1:36991 helper accepts only bounded one-shot `pause` and
`snapshot` diagnostics. It has no resume, effect or ownership authority and is
not exposed through Listener, Context or the IDE. Its observation scope cannot
qualify native children or control/prompt queues.
