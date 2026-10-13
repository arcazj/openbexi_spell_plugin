# Original DSS driver and operating modes — v0.4

The v0.4 profile connects the original SPELL 2.6.10 driver framework to the
existing GENERIC Dynamic Satellite Simulator. It supports durable Development,
read-only Monitoring and approved immutable Execution through the neutral IDE
service. These are operating modes; controller and observer are separate roles.
The exact platform, artifacts and tests are recorded in
[DRIVER_QUALIFICATION.json](DRIVER_QUALIFICATION.json).

This is simulator driver qualification. It grants no approval to control a real
spacecraft or RF station. Full SPELL inventory conformance remains v0.5;
distribution, upgrades and independent reproducibility remain v0.6.

## Source and wire contract

The original registry, factory, DriverManager, interfaces, helpers and TM/TC/PCS
models run inside the native CPython 3.13 image. CONFIG installs the private
connection; original setup/cleanup owns the other interfaces. There is no new
`spell` namespace and no replacement language interpreter. The bridge uses the
unchanged `protos/SPELLDriver.proto` from the supplied archive, SHA-256
`f2534b012489a4b9f3cb61e7f4a50ada4aaea7fe0b2de6041b7748d25aa96588`.
`scripts/generate_driver_contract.py` verifies the archive and records generator
and output hashes. The only generated-code patch is a package-relative import.
The GPL driver package retains its license and the original schema notices;
the inherited native image retains the original GPL/LGPL sources and notices.

The Driver Development Manual 2.4.4 permits partial drivers with explicit
unsupported capabilities. The 2.6.10 source supplies the actual wire signatures.
Conflicts are resolved explicitly: TC IDs use the schema's string type; the
source's RSC `isLocal` argument has no wire field, so only shared scope is
accepted; TIME returns the original interface's `datetime`; original Any values
include wrapped None, dictionaries, lists and TIME. Bytes can be decoded by the
original helper but are not produced by its PackValue. MEM GetObjectIDs has no
RPC and is rejected. Unused EV streaming methods, PCS_Control and vendor Cortex
configuration remain unsupported. No lifecycle RPC pretends to stop a service:
setup, interruption and cleanup belong to the owning worker.

## Qualified GENERIC capabilities

| Family | Implemented contract and explicit boundary |
| --- | --- |
| TM | Original items; binary raw/engineering values, timestamp, validity, quality, freshness and source-gap checks; fresh-sample waits; read-only catalog; four ordered engineering limits; catalog-calibrated ground injection and alarms. No arbitrary mission limit definitions or archive queries. |
| TC | Catalog-validated typed arguments, radix and format; five correlated binary command stages; finite deadlines; ordered lists/blocks stop at the first failure and retain completed effects. No atomic-group rollback, critical-command confirmation, onboard scheduling or automatic resend. |
| EV | Bounded durable messages with original severity/scope; no event-stream subscription. |
| PCS | Original item/result models over synchronous GENERIC TC; readiness, receipt verification, ARQ disabled. Abort returns false when no asynchronous command exists; PCS_Control is unsupported. Verification means DSS stage acknowledgements, not independent spacecraft telemetry verification. |
| MEM | Named GENERIC JSON snapshots, lookup, comparison and reports; no raw memory addresses, byte ranges or filesystem access. |
| RSC | Persistent typed JSON shared resources and TM/TC link gates; no procedure-local scope. |
| TASK | Actual DSS_CLOCK start/stop/check; manual-clock fixtures reject Start. DSS_TELEMETRY is a headless snapshot display/report, not a GUI, printer or arbitrary shell. |
| RNG | Explicit virtual DSS-BBE-1/DSS-ANTENNA-1 state transitions and bounded baseband settings; no RF hardware or Cortex. |
| USER | Explicit service-owned simulator accounts and persisted login/logout state; never a controller-role grant. No default credentials. |
| TIME | Actual DSS simulation UTC converted to the original datetime/TIME contract. |

Library reporting, comparison and prompt policies stay in the original helpers.
Operational modifiers outside the declared profile fail explicitly. A native
helper may offer its original manual error choices; an uncertain transport
effect instead terminates the worker and retains the service's recovery hold.

## Authority and transport

The executor container has no network access beyond its private loopback RPC.
Original gRPC requests traverse a bounded relay over the existing private DAP
pipes. Only the installed service provider has DSS network access. It attaches
session/run, logical definition/version, controller epoch, procedure fence, mode
and approved release identity; procedure payloads cannot supply that authority.
Every command write rechecks the live lease and fence under the service lock.
Monitoring rejects mutations before an intent or packet is emitted.

`driver-effects.sqlite` retains a FULL-synchronous WAL intent before an effect and
a matching response receipt afterward. Duplicate receipted requests return their
receipt. Pending intents survive restart and block further effects for that run.
Lost acknowledgements never cause automatic command replay. The existing durable
logical reservation also blocks aliases and later versions until offline
reconciliation. DSS retains its independent binary stage receipts and outbox.

Telemetry comes from binary `packet_hex` over the DSS read API or, when configured,
the actual `openbexi.GENERIC.tm` Kafka topic. Catalog/epoch/APID/sequence identities
are checked; exact duplicates and old outbox records cannot advance the sample.
Conflicting bytes for a retained sequence are rejected. Wait requires a newer
sample. Kafka consumer failure cannot silently switch to HTTP. Transport threads
are joined before their consumer/journal closes. The local manual-clock fixture
and the automatic Kafka DSS continue to declare different capabilities.

Confirmed Docker pause freezes every native descendant before releasing a slot.
A request arriving during pause waits for explicit resume. A private independent
watchdog exits the container after four seconds without parent heartbeats; a
declared freeze gets one bounded grace period after thaw. Restart removes only
the recorded image/label/container identity and never replays interrupted work.

## Install and configure

Build the three plugin wheels from the repository root, retaining the accepted
host wheel 0.3.0 alongside them:

```powershell
python -m pip wheel --no-deps --no-build-isolation ./driver_plugin ./shared_plugin . -w .qualification/v0.4/release-wheels
docker build --network=none -f driver_plugin/Dockerfile -t openbexi-spell-dss:0.4.0 .
python -m pip install --find-links .qualification/v0.4/release-wheels --find-links .qualification/v0.3/host-wheels 'openbexi-spell-shared[dss]==0.4.0'
```

Build only over the accepted host image identity in the qualification manifest.
The worker image installs the driver wheel without the service extra; the service
extra installs the separate Apache DSS package and Kafka client on the host.
Never install that bounded SDK over the original in-container SPELL library.

Set these on the **service process**, using your actual endpoints:

```powershell
$env:OPENBEXI_SPELL_SHARED_IMAGE='openbexi-spell-dss:0.4.0'
$env:OPENBEXI_SPELL_DSS_URL='http://127.0.0.1:8765'
$env:OPENBEXI_SPELL_DSS_TCP='127.0.0.1:8766'
# Optional actual Kafka transport; omit for the manual local fixture.
$env:OPENBEXI_SPELL_DSS_KAFKA='127.0.0.1:9092'
```

Binding resolves the image tag to its full immutable ID and captures endpoints.
Changing service environment cannot retarget an existing captured release.
This profile qualifies a local trusted DSS/Kafka network. It does not expose a
public unauthenticated driver server or qualify remote broker security settings.
Optional `OPENBEXI_SPELL_DSS_USERS` names a service-only JSON file mapping simulator
usernames to SHA-256 password verifiers. It is neither mounted in the worker nor
stored in request audit records. Those simulator verifiers are not suitable as
an Internet identity system.

For Execution, use the neutral IDE 0.3 `release-prepare --backend spell` with the
exact driver image ID, review the captured source/runtime/binding, then separately
approve the manifest's digest through the offline authority. See the sibling
IDE's `docs/PLUGIN_EXECUTION_SERVICE.md`. Release qualification tests use synthetic
approvals and do not approve any user's procedure. The accepted host 0.3.0 image
and JetBrains ZIP are preserved. Prior shared Development 0.4.0.dev1 bindings can
still be recovered; unaccepted development DSS bindings are not release inputs.
