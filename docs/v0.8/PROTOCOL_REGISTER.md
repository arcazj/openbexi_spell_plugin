# Protocol register

Status column is part of the contract. Target protocols are not claims of an
implemented or qualified endpoint. No illustrated port is silently assigned.

| Edge | Status | Protocol, authentication and ordering | Timeout/retry/recovery |
|---|---|---|---|
| Browser/Qt → local procedure service | VERIFIED-v0.7 | REST/JSON, bearer role, host/origin checks; polled revision snapshots | Existing client deadlines; reconnect to service |
| Durable client → session authority | VERIFIED-v0.7 | JSON HTTP loopback or mTLS identity plus bearer; one session controller epoch | Lease expiry and restart fence; no automatic replay |
| Service → native worker | VERIFIED-v0.7 | DAP Content-Length JSON over private pipes; container image/labels checked | Bounded requests and private watchdog; uncertain effects hold |
| Native adapter → native Listener/Context/Executor | VERIFIED-v0.7 | Native bridge via private framed messages and TCP; named REQ_* routes inspected in native.py | Connection setup may retry before send; never replay a sent request |
| Native facade → Driver | VERIFIED-v0.7 | Original-schema protobuf gRPC on loopback, bounded 64 KiB/4 requests | Explicit deadlines and capability failures |
| Driver → GENERIC DSS | VERIFIED-v0.7 | Binary TC TCP packets and HTTP TM/state; optional configured Kafka immutable outbox | Correlated intent/receipt; uncertain TC never retried automatically |
| Legacy 2.4.4 wire parity / vendor GCS | UNKNOWN | Architecture/manual categories only | Site/protocol qualification required |
| Browser → edge/Listener | TARGET-v0.8 | HTTPS JSON `/v1`; WSS JSON events; registered certificate identity, secure session; exact Origin allowlist | Bounded request size/deadline; reconnect with cursor; snapshot on gap |
| Edge → Listener | TARGET-v0.8 | mTLS; strip external identity headers; bind client identity/session to trusted edge | Fixed upstream identity; unavailable edge does not stop Contexts |
| Listener → Context | TARGET-v0.8 | mTLS HTTP/JSON RPC, schema `openbexi.context/1`; authenticated short-lived delegation, Context scope | 5s ordinary request deadline, explicit longer launch receipt polling; no blind mutation retry |
| Context → worker | TARGET-v0.8 | mTLS versioned JSON RPC: preflight `openbexi.worker/1`, retained launch `openbexi.worker/2`; immutable original grant plus memory-only proof from the single consumption winner; bounded driver payloads | Heartbeat/health; ambiguous start/command holds reservation; no lease-based replacement |
| Development → Git | TARGET-v0.8 | Local isolated worktrees; configured HTTPS/SSH remote, credentials outside snapshots | Expected-base compare, explicit conflicts; no force push |

## Proposed common envelope

Requests carry schema version, request ID, ContextID, optional ExecutionID,
authenticated/delegated subject, deadline, idempotency key and canonical payload
hash. Execution mutations additionally require current control epoch and
connection-bound capability; worker messages require generation. Context is
the only issuer of execution authority. Reject unknown versions/fields, duplicate
JSON keys, nonfinite numbers, oversized bodies and mismatched scope/identity.

Do not put bearer secrets, control capabilities, certificates' private keys or
credentials in URLs, event logs or audit payloads. Browser WSS is authenticated
by the established secure session with Origin validation, not a token query
string. Service certificates are per role/Context; worker credentials cannot
impersonate Listener or Context.

All mutating commands use persisted idempotency keyed by subject, execution,
operation and key; same key with a different canonical payload is a conflict.
Duplicate acceptance returns the recorded outcome without a new epoch. Bounded
idempotency storage must reject new admissions at capacity rather than erase
uncertain intents. Document retention and late-request behavior in the final
OpenAPI contract before client implementation.

Events carry ContextID, ExecutionID, monotonically increasing Context sequence,
type, server timestamp and redacted body. Persist owner/claim transitions and
their events atomically. Each WSS client has bounded queue/replay; a gap returns
an explicit resync requirement and a consistent snapshot sequence. Slow viewers
are disconnected without blocking execution. No automatic command resend on
WSS reconnect. Viewer counts are observational, not execution authority.

## Initial implementation profile

[SERVER_CONTRACT.md](SERVER_CONTRACT.md) fixes the internal TLS 1.3/leaf-pin,
edge identity, Context-local ACL, strict RPC envelope and route matrix for C/D.
EXECUTION_AUTHORITY.md adds the explicit internal prelaunch reservation and
controller route matrix. Worker network/native launch, effects and WSS/browser
sessions remain disabled. F1-F10 bind the remaining worker/driver integrations.


The dev3 single-host worker preflight uses pinned mTLS JSON challenge/verify
routes defined in WORKER_PREFLIGHT.md. It authenticates an assigned credential
and source digest, never a start/driver operation. The full target worker
protocol and Kubernetes Pod identity remain pending.


The optional private fenced-pause profile adds protocol-2 worker pause-poll and
pause-report routes (NATIVE_PAUSE.md). They preserve original binding and the
single consumer's memory-only proof after controller fencing, solely to report
safety state. They can never admit effects, mint authority or prove quiescence.
Schema 9 adds the bounded durable barrier; positive native handoff is pending.

The separate private dev15 background-thread qualification component adds
one worker-local JSON-line helper at **127.0.0.1:36991**, with bounded `pause`
and `snapshot` actions bound to a single barrier UUID. It accepts no resume,
grant, driver or ownership action. It is not a Listener/Context/IDE route or an
authentication service; it can only hold observed cooperative Python threads.
See [NATIVE_THREAD_BARRIER.md](NATIVE_THREAD_BARRIER.md) for its explicit scope,
limits and candidate-SHA qualification. Whole-family proof remains unavailable.
