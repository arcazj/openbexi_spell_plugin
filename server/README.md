# SPELL v0.8 internal server foundation

The `openbexi-spell-server` package provides independent internal Listener and
Context processes, authenticated routing and durable Context blackboards.
It also provides durable prelaunch reservations and consent-based ownership
transfer. An optional approved Git catalog and pinned single-host worker
preflight verify the source binding. Native execution, worker launch, driver effects, browser
sessions and WSS remain disabled. This is staged implementation, not a v0.8 release.
Published v0.7 packages and entry points remain unchanged.

Use Linux and CPython 3.13. TLS 1.3, an operator-provisioned CA and registered
leaf certificate fingerprints are required. The Listener accepts only the
configured edge certificate plus a registered client fingerprint. The edge
must validate client certificates and strip client-selected identity headers.
Do not place this internal service directly on a public browser endpoint.

See [worker/source preflight](../docs/v0.8/WORKER_PREFLIGHT.md),
[the prelaunch authority contract](../docs/v0.8/EXECUTION_AUTHORITY.md),
[the wire/ACL contract](../docs/v0.8/SERVER_CONTRACT.md) and
[approved G1 resolutions](../docs/v0.8/G1_REVIEW_RESOLUTION.md).
The private [driver write boundary](../docs/v0.8/DRIVER_WRITE_GATE.md) adds
actual-send fencing and separate receipt ledgers for trusted Context adapter
code. It is not exposed by any service or connected to native workers.

## Development checks

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-test.lock
.venv/bin/python scripts/qualify_v08_server.py
```

Qualification executes lint, formatting, type checks and pytest with warnings
as errors, real TLS sockets, concurrent clients, exclusive state locks and
separate Listener/Context process crashes/restarts. OpenSSL is needed to create
temporary test certificates. Private keys/configuration stay in the test
temporary directory; no credentials belong in Git or retained evidence.

Each qualification invocation creates a new `.qualification/v08-server/run-*`
directory, preserves failures, and records exact source hashes, Python/OpenSSL
versions, tool commands, JUnit and a credential-free process trace. These checks
qualify the private driver seam only; they do not qualify native SPELL,
worker/driver integration, worker pause/reuse, browser UI,
Compose, Kubernetes or production storage fencing.

## Run an internal process

```bash
python3.13 -m pip install ./server
openbexi-spell-server context --config /secure/context-a.json
openbexi-spell-server listener --config /secure/listener.json
```

Configuration is an exact JSON object. Common fields: `ca`, `certificate`,
`key`, `bind`, `port`, `allowed_hosts`, `max_handlers`. Paths refer to injected
files outside Git. The example below uses placeholders, not usable secrets:

```json
{
  "ca": "/secure/ca.pem",
  "certificate": "/secure/context-a.pem",
  "key": "/secure/context-a.key",
  "bind": "127.0.0.1",
  "port": 9441,
  "allowed_hosts": ["context-a.example:9441"],
  "max_handlers": 16,
  "context_id": "A",
  "state_directory": "/secure/state/context-a",
  "listener_fingerprint": "<64 lowercase hex characters>",
  "subjects": {
    "operator-1": ["context:read", "blackboard:read"],
    "administrator-1": ["context:read", "blackboard:read", "blackboard:admin"]
  }
}
```

Listener-specific fields replace the four Context-specific fields:

- `edge_fingerprint`: registered edge certificate SHA-256.
- `identities`: client fingerprint to stable user ID mapping.
- `scopes`: stable user ID to allowed ContextID list.
- `contexts`: ContextID to exact `{"url": "https://...", "fingerprint": "..."}`.

Each Context independently checks its local `subjects` ACL; Listener scopes
alone cannot grant blackboard or execution permissions. Optional Context field
`worker_slots` maps up to ten slot identifiers to unique operator-provisioned
incarnation identifiers for the prelaunch registry. It enables reservations,
not a native worker or network launch endpoint. Existing slot incarnations
cannot be replaced automatically. Controller ACL permissions are `execution:read`,
`execution:start`, `execution:control` and `execution:request_control`; see the
route matrix before assigning them. Configuration/identity changes
require restart in this first implementation. Only Listener's outbound client
uses its certificate to delegate to a configured Context. It never starts,
signals or stops Contexts or workers. Health always reports
`runtime_enabled: false`.


## Approved sources and worker preflight

Development package `0.8.0.dev4` accepts optional Context `approved_sources` and
`worker_credentials` fields. See WORKER_PREFLIGHT.md for the exact schema and
bounds. Only operator-approved aliases/revisions/images/driver bindings can be
reserved when a catalog is configured. Without one, earlier metadata-only
reservations remain available but cannot pass Context's private start guard.

Run the non-executing worker check with:

```bash
openbexi-spell-worker-preflight --config /secure/worker-preflight.json
```

It verifies a mounted source directory, authenticates to the pinned Context
with its individual certificate, and prints a preflight receipt. It never
imports procedure code, starts native processes, consumes a worker slot or
sends driver effects. Native launch still has no network route. A receipt does
not establish read-only mounts, runtime-image attestation or Kubernetes Pod UID.

## Disconnect barrier (development package 0.8.0.dev4)

`session.close` durably changes the connection to CLOSING before waiting for the
same execution mutexes used for controller transfer and private start admission.
CLOSING rejects new reservations, grants and controller proofs. Final close
fences executions still bound to that connection after all affected mutexes are
held; a rebind to another active connection is preserved. SQLite transactions
never include mutex waits. A busy execution returns `execution_busy`, retains
the admission barrier, and requires a retry with the original idempotency key.
Live permissions are checked again on completion and replay. Restart retains
execution recovery holds and never restores a closing connection.

Authority schema 4 prevents older dev3 binaries, which treat a nonzero session
flag as active, from opening this state. Upgrades are one way; no automatic
rollback or downgrade is supported. This barrier establishes ordering for future
bounded driver writes but does not implement those writes or prove native pause.

## IDE certificate gateway (0.8.0.dev5)

Use the paired IDE commit and installed-source hashes in
`docs/v0.8/IDE_PAIR.json`. The new IDE **SPELL server** tab and
`openbexi-spell-client` CLI use a dedicated certificate gateway. They do not
connect as the privileged edge or supply identity headers. The old IDE Session
tab continues to speak v0.7. This integration supports metadata, reservations,
observation and explicit prelaunch handoff; no native execution is enabled.

`openbexi-spell-server gateway --config private-gateway.json` accepts the same
required `ca`, `certificate`, `key`, `bind`, `port`, `allowed_hosts`,
`max_handlers` fields as other roles, plus exactly:

```json
{
  "listener_url": "https://listener.internal:9444",
  "listener_fingerprint": "<Listener certificate SHA-256>",
  "clients": ["<Alice certificate SHA-256>", "<Bob certificate SHA-256>"]
}
```

Use the gateway's service certificate as the Listener's configured
`edge_fingerprint`. Put each desktop certificate pin in both gateway `clients`
and Listener `identities`, with its canonical subject and explicit Context scope.
Do not give desktop users the gateway/Listener/Context private keys. The gateway
extracts the actual TLS peer pin, rejects supplied identity headers, forwards only
a fixed path/method allowlist and sends no user data before the Listener's CA,
hostname and leaf pin are verified. Listener and Context reauthorize each call;
Context health returns only that authenticated subject's effective permissions.

The IDE connection file uses the gateway URL/leaf pin and the user's own CA,
certificate and key paths. Full instructions are in the companion IDE's
`docs/v0.8/SPELL_SERVER_INTEGRATION.md`. All connection files and credentials
belong outside repositories. Qt network work runs in a bounded background queue.
Use **Disconnect** for logical controller closure; window detachment alone is
not a server close or native pause. Browser/WSS sessions remain unimplemented.

Qualification now needs the paired IDE wheel and PySide6-Essentials 6.10.3 in
the test environment; neither is a dependency of the installed server package.
Hosted CI checks out the exact IDE commit, verifies installed source hashes and
exercises three independently certified IDE clients plus the actual Qt panel.
The separate native-boundary CI diagnostic downloads the frozen v0.7 archive,
verifies its SHA-256 and image ID, then observes real native processes inside a
read-only, non-root container with no external network. This diagnostic is not
v0.8 native launch, descendant quiescence, driver or deployment qualification.

The explicitly configured `worker_launch: "retained-single-use"` profile adds
original-grant admission directly at Context and certificate-bound one-time
worker consumption/checking. Default Listener/gateway/IDE execution remains
disabled. The separate GPL native agent and its ten-worker Docker test are
specified in [NATIVE_LAUNCH.md](../docs/v0.8/NATIVE_LAUNCH.md). Procedure-scoped audit events in
this narrow profile are acknowledged only after durable Context journalling;
other native driver calls remain denied. No ExampleDriver fallback is permitted.

The separate optional GPL [Context-owned DSS profile](../docs/v0.8/NATIVE_DSS.md)
adds five bounded original TC/TM methods through the real effect gate, with
fixed endpoints and explicit resource permissions. The Apache server and public
gateway/Listener/IDE retain their defaults. Local original-protobuf/mTLS/DSS
checks are distinct from the mandatory native Docker matrix and full v0.8
qualification. The single consumption winner receives a separate memory-only
runtime proof; copied original configuration alone cannot call the driver.
Authority schema 8 prevents opening the runtime-proof and RPC ledgers with older
binaries; no automatic state downgrade or recovery is supported.
