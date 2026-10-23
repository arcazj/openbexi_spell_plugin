# SPELL v0.8 internal server foundation

The `openbexi-spell-server` package provides independent internal Listener and
Context processes, authenticated routing and durable Context blackboards.
It has **no procedure execution, worker, driver, control-transfer, browser
session or WSS route**. This is initial C/D implementation, not a v0.8 release.
Published v0.7 packages and entry points remain unchanged.

Use Linux and CPython 3.13. TLS 1.3, an operator-provisioned CA and registered
leaf certificate fingerprints are required. The Listener accepts only the
configured edge certificate plus a registered client fingerprint. The edge
must validate client certificates and strip client-selected identity headers.
Do not place this internal service directly on a public browser endpoint.

See [the wire/ACL contract](../docs/v0.8/SERVER_CONTRACT.md) and
[approved G1 resolutions](../docs/v0.8/G1_REVIEW_RESOLUTION.md).

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
do not qualify native SPELL, driver effects, worker pause/reuse, browser UI,
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
alone cannot grant blackboard write permission. Configuration/identity changes
require restart in this first implementation. Only Listener's outbound client
uses its certificate to delegate to a configured Context. It never starts,
signals or stops Contexts or workers. Health always reports
`runtime_enabled: false`.
