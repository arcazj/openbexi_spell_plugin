# Context-owned native DSS subset (development)

`0.8.0.dev9` connects the original protobuf driver request to the private Context
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
The body has exactly `schema`, `context_id`, the ORIGINAL `grant`, a canonical
`request_id` UUID, the original `path`, and a base64 `payload`. Decoded request
and response protobufs are at most 32 KiB, within the existing 64 KiB JSON bound.
The reply binds `request_id`, `execution_id` and base64 response bytes.

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
Receipt waits and the one-second shared DSS resource admission wait hold no
execution mutex or authority database transaction. TC and fresh-TM timeouts in
this initial profile are capped at three seconds.

All RPCs reserve one of 512 durable, non-replayable call identities before
execution; request and response hashes are retained without plaintext grants.
The same UUID cannot be replayed, even after a lost reply or with changed bytes.
Live authorization is checked before replay disclosure. Uncertain sends retain
the worker and logical holds and fence control; no automatic resend, capacity
reclamation or ownership transfer follows. Schema 7 prevents older binaries
opening this new state. Restoration/downgrade requires the existing manual
fencing/recovery process, not copying an older database.

## Qualification and remaining work

The local tests use original serialized protobuf requests over real mTLS to a
Context and a separate DSS process. They cover all other original method paths,
certificate/provenance/resource denial, duplicate calls, between-stage handoff,
lost release receipts and bounded capacity. They do not instantiate a native
Executor. Failed development attempts are retained separately from passes.

The hosted native matrix retains the audit-only cohort and adds
`scripts/qualify_v08_native_launch.py --native-dss`. The new variant must prove
ten distinct native Executors, ten successful original SendCommand calls,
original RefreshItem calls and fifty ACKED stage receipts in a separate isolated
DSS container, while retaining all original reservations and spent slots.
Until that candidate-SHA workflow succeeds, this boundary is **not native
qualified**. Adding or passing unit/RPC tests is insufficient.

Native quiescence/live handoff, child admission, recovery/reclamation, IDE
Run/Debug, browser/WSS, all-763 compatibility, production Compose/Kubernetes,
independent security and final release acceptance remain separate mandatory
gates. No merge, release or production promotion is implied by this subset.
