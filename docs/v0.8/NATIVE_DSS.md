# Context-owned native DSS subset (development)

`0.8.0.dev20` connects the original protobuf driver request to the private Context
effect gate. This is an optional retained, single-use qualification profile.
Default gateway, Listener and IDE execution remain disabled. It is not a full
v0.8 release or a claim of complete legacy driver compatibility.

The GPL module `openbexi_spell_dss.context_server` runs the Apache Context with
the GPL `ContextDriver`. The standalone Apache server neither imports this
adapter nor accepts its configuration. The existing v0.7 driver entry points,
legacy transport and immutable patch preimages are unchanged.

## Operator-owned configuration

Use the existing private Context configuration, `worker_launch` set to
`retained-single-use`, and an additional `native_driver` object:

```json
{
  "binding": "simulator",
  "url": "http://10.66.0.4:8085",
  "tcp": ["10.66.0.4", 4545],
  "directory": "/state/driver",
  "commands": ["CMD1"],
  "telemetry": ["TM.POWER.BUS_VOLTAGE"]
}
```

Start the source-composed qualification host with:

```sh
python -m openbexi_spell_dss.context_server context --config /secure/context.json
```

The approved procedure inventory must bind to `simulator`. The endpoints use one
fixed IPv4 host, with separate fixed HTTP metadata and binary TCP ports. No DNS,
worker-supplied URL, credentials in URLs, arbitrary mounts, Docker socket, host
manager, Kafka client or native helper port is exposed by this profile. Network
isolation must independently restrict these internal endpoints. This is a
synthetic DSS fixture, not a spacecraft/vendor GCS connection.

Both permission lists are explicit and bounded (32 command names, 128 telemetry
names). At least one resource must be listed. Unknown or critical commands are
rejected at startup. Global configuration, reset, injection, limits mutation,
command groups, scheduling and every other original method remain denied.

## Worker route and exact authority

Only a registered certificate-bound worker may POST `/v1/worker/driver`. This
route exists only when the retained profile and adapter are both configured.
The body has exactly `schema` (`openbexi.worker/2`), `context_id`, the
ORIGINAL `grant`, a separate `runtime_capability`, a canonical `request_id`
UUID, the original `path`, and a base64 `payload`. Decoded request
and response protobufs are at most 32 KiB, within the existing 64 KiB JSON bound.
The reply binds `request_id`, `execution_id` and base64 response bytes.

The single successful start consumer receives a separate random 256-bit runtime
proof. Context commits only its hash in the same transaction as spending the
worker slot and recording consumption. The native agent keeps the plaintext
proof in memory; it is absent from the original start configuration and from
persisted receipts or logs. Checks, events and driver calls require both this
proof and the unchanged live original grant/certificate assignment. A second
process with only a copied original certificate/configuration cannot skip
consumption and dispatch an effect. A lost response loses the proof: it cannot
be refreshed or replayed, and the spent slot and logical hold remain retained.
This is not protection against compromise of the legitimate worker's memory or
an attestation of untrusted procedures.

TC database lookup preserves the original `kind: COMMAND` discriminator needed
by native critical-command checks. It does not admit sequences or unlisted TCs.

The supported original methods are:

| Family | Methods | Admission |
|---|---|---|
| TC | CreateTcItem, SendCommand | Explicit command allowlist; live original start/control grant |
| TM | CreateTmItem, DatabaseLookup, RefreshItem | Explicit telemetry/command lookup allowlist; live original grant before disclosure |
| EV | RaiseEvent, through the separate `/v1/worker/event` route | Procedure scope only; durable Context commit before acknowledgement |

Context derives wire execution/procedure identity, endpoint, binding and command
operation UUID. The worker cannot restamp an epoch, choose a resource endpoint,
submit a replacement admission object, reset the driver or acquire a new grant.
Every command stage still uses `DriverGate`'s original-grant final check and
bounded actual TCP write, two durable intent ledgers and correlated receipts.
Receipt waits hold no execution mutex or authority database transaction.
In dev18, at most ten command operations can be in flight per fixed simulator
binding, below its sixteen TCP handler slots. Each command owns its TCP stream,
operation UUID and correlated receipts. A full admission limit rejects immediately
before metadata access or binary effect; no command waits behind another command’s
receipt. This replaces a single lock held across all five stages that caused
valid ten-command bursts to expire under load. This concurrency contract is for
the synthetic DSS only; vendor resource exclusivity requires its own adapter
policy and qualification. TC and fresh-TM timeouts in
this initial profile are capped at three seconds. The composed native TC proxy
may send neutral defaults: `ConfirmCritical: false`, `LoadOnly: false`,
`SendDelay: 0`, and `addInfo: {}`. Their types and neutral values are checked
explicitly; nonneutral/scheduled/load-only options remain denied before intent.

All RPCs reserve one of 512 durable, non-replayable call identities before
execution; request and response hashes are retained without plaintext grants.
The same UUID cannot be replayed, even after a lost reply or with changed bytes.
Live authorization is checked before replay disclosure. Uncertain sends retain
the worker and logical holds and fence control; no automatic resend, capacity
reclamation or ownership transfer follows. Schema 8 prevents older binaries
opening this new state. Restoration/downgrade requires the existing manual
fencing/recovery process, not copying an older database.

## Qualification and remaining work

The local tests use original serialized protobuf requests over real mTLS to a
Context and a separate DSS process. They cover all other original method paths,
certificate/provenance/resource and copied-configuration denial, duplicate calls,
between-stage handoff,
lost release receipts and bounded capacity. They do not instantiate a native
Executor. Failed development attempts are retained separately from passes.

The hosted native matrix retains the audit-only cohort and adds
`scripts/qualify_v08_native_launch.py --native-dss`. At code commit **14ddf3d**,
[PR run 40004938954](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40004938954)
passed foundation (264 scoped tests), native-boundary and both native cohorts.
The DSS artifact proves ten completed/terminated native Executors, thirty
native PIDs, ten original commands, original telemetry refreshes, and fifty
identical ACKED receipt rows in each independent Context/driver ledger. A
separate process using copied ORIGINAL configuration and a valid permitted
CMD1 request received HTTP 403. Ten spent worker slots and logical holds
remained retained. Cross-worker/native-port and external TCP denial passed.

The [redacted qualification receipt](evidence/native-context-dss/qualification-summary.json)
pins the code/CI merge SHA, all 81 tested source hashes, image/archive identities,
artifact digest and counters. Every tested source hash matched the candidate.
Failed fixture, native-contract and adversarial attempts are retained and
explained in TEST_REPORT.md; they are not counted as passes. This qualifies
only the retained positive TC/TM subset and clone denial. The handoff check
remained BLOCKED **after container termination**; no native quiescence or
successful live transfer is claimed. Default public execution remains disabled.

Native quiescence/live handoff, child admission, recovery/reclamation, IDE
Run/Debug, browser/WSS, all-763 compatibility, production Compose/Kubernetes,
independent security and final release acceptance remain separate mandatory
gates. No merge, release or production promotion is implied by this subset.

### Fixed metadata authority

The private v0.8 transport reads only `state` and `telemetry` on the operator's
configured endpoint. It disables environment proxies and rejects redirects
before contacting another authority. HTTP error responses are closed. The
shared HTTP read boundary admits at most three requests, covering initialization,
state and inherited telemetry reads against the fixed API's four-handler budget.
The unchanged 250 ms admission deadline applies before any HTTP request; reads
are not retried. Earlier admission in `current_state()` did not cover inherited
`sample()` calls and allowed telemetry to exceed the configured handler bound.
The dev19 PR native DSS run failed one telemetry refresh with `RemoteDisconnected`
while all fifty command-stage receipts were ACKED. Dev20's two regressions first
failed against that source, then passed after moving admission into `get()`;
exact-source hosted native qualification passed at a9c9bb1 in the PR and push
DSS jobs: fifty completed calls, no recorded failures and fifty matching ACKED
command-stage receipts in each ledger. The
existing response-size and timeout bounds remain in force. Real HTTP regressions
check that a redirect target and an environment-selected proxy receive no
request, an unlisted path makes no request, and a 503 response is closed without
success. The published legacy transport and its patch preimages are unchanged.
This does not establish production DSS mTLS, complete driver methods or full
fault/recovery qualification.
