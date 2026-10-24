# Approved Git source and single-host worker preflight

`0.8.0.dev3` adds source validation and an authenticated **preflight**, not a
native worker launcher. `runtime_enabled` remains false. Full native,
driver, Compose and Kubernetes gates remain pending.

## Approved catalog

Context may load optional `approved_sources` at startup:

```json
{
  "procedure-id": {
    "repository": "/secure/approved-procedures.git",
    "revision": "<40 lowercase hex commit SHA>",
    "entrypoint": "main.py",
    "runtime_image": "sha256:<64 lowercase hex>",
    "driver_binding": "simulator",
    "aliases": ["old-procedure-name"]
  }
}
```

The local repository and catalog are operator-controlled; Git must be installed
on the Context host. Context reads exact
Git commit/tree/blob objects, verifies their object hashes and constructs a
canonical `openbexi.snapshot/1` inventory of all files, sizes, executable modes
and SHA-256s, plus revision and entrypoint. It never checks out, imports or
executes source; Git replace refs and global configuration are disabled.
Subprocess output and total Git-read time are bounded. Partial/promisor clones
are rejected before object reads and lazy fetch is disabled. No network fetch occurs.

The initial small-repository profile allows ten logical procedures, ten aliases
per procedure, 64 files, 64 KiB per file, 1 MiB total and 16 path components.
Only regular Git files with normalized ASCII relative paths are supported.
Symlinks, submodules, special files and traversal are rejected. Git filters/LFS
materialization, larger repositories and broader filename support are not
qualified; there is no silent truncation or dependency-download fallback.

`GET /v1/contexts/{id}/procedures` (Context RPC `source.catalog`) requires
`execution:read` and returns approved IDs, aliases, entrypoint and binding
metadata, excluding repository paths and source bytes. An unconfigured catalog
returns 404. Controllers can use these approved digests in reservation requests.

`execution.reserve` retains its existing fields. `source_sha256` must equal the
SHA-256 of the complete canonical manifest. Revision, image digest and driver
binding must match catalog policy. Aliases normalize to the catalog's stable
ProcedureID **before reservation**, while idempotency still hashes the original
request. A catalog revision or entrypoint rename under that same ID cannot
evade a retained reservation. The same revision/entrypoint cannot receive two
catalog identities, even through two clones. Unknown IDs and metadata mismatch
are denied. Image/driver entries are approved configuration; they do not attest
an actual runtime image or authorize an external driver operation.

Catalog policy loads once at startup. Reload and dynamic Git development are
not implemented. Context restart fences all previous authority as before.
Without a catalog, earlier metadata-only reservations remain explicitly
unverified; Context's private start guard denies them.

## Worker identity and routes

Optional Context `worker_credentials` requires a catalog and configured
`worker_slots`:

```json
{
  "profile": "single-host-preflight",
  "identities": {
    "<64 lowercase hex worker leaf certificate fingerprint>": {
      "slot": "one",
      "incarnation": "operator-provisioned-worker-incarnation"
    }
  }
}
```

TLS 1.3 requires CA validation, hostname verification and registered leaf pins.
Each worker pin maps to exactly one configured slot/incarnation. A Listener
certificate cannot also be a worker identity; duplicate slot assignments fail
startup. CA membership alone never assigns this role. Profile `kubernetes` is
rejected: API-verified Pod UID and workload credential issuance are not present.
The operator must provision a distinct credential for each single-host worker
incarnation; credential cloning and workload/image attestation are not solved
by a name in configuration.

Worker peers can only POST directly to the Context routes below. They cannot
use Listener delegation, user identity headers, blackboard or controller RPC,
launch, consume, driver or recovery routes. Listener/user peers cannot call the
worker routes. There is no worker endpoint in the public Listener route matrix.

| Route | Exact JSON fields |
|---|---|
| /v1/worker/challenge | schema, context_id, execution_id, request_id |
| /v1/worker/verify | schema, context_id, execution_id, challenge_id, source_sha256 |

Schema is `openbexi.worker/1`; IDs are canonical UUIDs. Context derives worker
identity from TLS and rejects caller-supplied identity/role fields. A challenge
is restricted to that worker's assigned execution. Its durable binding includes
authority incarnation, execution, canonical procedure, worker incarnation and
generation, controller epoch/connection/generation, and inventory digest.
The response includes the approved manifest and a 30-second challenge ID.
A repeated request UUID returns the same valid challenge without extending it;
a different binding conflicts. It is not a start grant or control capability.

The worker CLI reads its own source directory through no-follow directory/file
descriptors. It compares every file's bytes, size and Git executable mode and
rejects missing/extra files/directories, symlinks, hardlinks, special files and
changes detected during reading. Directory/file counts and data are bounded.
It sends the observed manifest digest over mTLS. Context checks the original
challenge, current permissions/connection/epoch, source binding and expiry,
then atomically records verification and audit. Replay does not append another
verification event. No slot is spent and no user code is run by this protocol.

This is a self-report from the trusted, approved pre-execution agent. A malicious
agent possessing a registered private key could report the expected digest
without reading files. TLS does not attest the binary, image or mount policy.
Actual native launch must additionally qualify image identity, read-only mounts,
credential isolation and unchanged source at the final launch boundary.

## Worker CLI

`openbexi-spell-worker-preflight --config /secure/worker.json` (or
`python -m openbexi_spell_server.worker`) takes exactly:

- `ca`, `certificate`, `key`: injected credential file paths outside Git.
- `context_url`, `context_fingerprint`, `context_id`: fixed Context trust/routing.
- `execution_id`, `worker_slot`, `worker_incarnation`: expected assignment.
- `snapshot_directory`: absolute local pre-mounted source root, with no parent traversal or symlink ancestors.

It pins Context before sending metadata, verifies assignment/source, and prints
only a bounded receipt or error. It has no procedure import, subprocess runtime,
Docker socket, Kubernetes API token or driver path. The snapshot must eventually
be a qualified read-only mount for native launch; preflight itself cannot prove
that it stays immutable. This first filesystem profile is Linux/local storage.

## Fencing, capacity and recovery

Context's private start admission and consumption both require a matching,
unexpired verified preflight when using the server service. A late failure
rolls back consumption, including the worker's spent flag. The original start
grant still comes from authenticated controller admission; worker preflight
cannot mint or restamp it. Actual network start/consume remains absent.

Transfer, rebind, disconnect, permission revocation and Context restart make
old bindings unusable. Restart invalidates stored preflights and preserves all
execution/worker holds. Expiry never frees a slot, grants a claimant control or
authorizes replacement. The ledger retains at most 128 challenges and eight
per worker certificate; no automatic capacity reclamation is exposed. Audit or
storage failure rolls back a challenge/verification and denies admission.

Schema 3 adds the preflight table without changing published v0.7 data. Schema
versions never silently decrease; earlier dev2 code rejects schema 3. Rollback
needs a separately qualified offline procedure, not a live downgrade.

Evidence is in TEST_REPORT.md and `evidence/worker-preflight/`. Real mTLS and a
separate preflight client process are tested. Neither that PID nor its receipt
is a native Executor, container identity, Kubernetes Pod or driver receipt.
