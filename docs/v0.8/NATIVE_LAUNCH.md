> **Qualification status:** full v0.8 remains unqualified. [Current results and next work](CURRENT_STATUS.md) supersede historical summaries below; original evidence and acceptance limits remain binding.

# Retained one-shot native launch profile

## Starting an assigned worker from the desktop

The v1.2.2 server panel can start a new approved native procedure in a Context
configured with the v0.8.0 assigned-worker profile. Select the procedure, click
**Reserve**, select its execution row, then click **Start native**. The panel
checks for registration of the root Executor. **Run / Continue** sends a
separate command using the controller proof held by that panel.

The **Native result** column displays `FINISHED`, `ABORTED` or `ERROR` after
the consumed worker reports the terminal state it observed for the registered root
Executor. Context persists that observation and fences further commands to that
root. The execution reservation and worker incarnation stay held until independent
host settlement. A missing result remains unconfirmed.

Configure the Context with `worker_launch: "assigned-single-use"`,
`native_children: "admission-only"`, `native_controls: "run-journal"` and
`native_commands: "owner-queue"`. Set its existing `approved_sources`,
`worker_slots` and `worker_credentials` to the approved immutable commit, exact
worker image, slot incarnation and that worker's private certificate pin. Add
the Context ID to the Listener's `native_command_contexts` and
`native_launch_contexts`. The gateway uses its existing authenticated client
and Listener routes. Each controller needs both start and control permissions.

Build the private worker offline with
`python scripts/build_v08_assigned_worker.py --native-image <image-digest> --wheel-directory <directory> --server-sha256 <digest> --dss-sha256 <digest> --receipt <output.json>`.
The native input comes from the full-family native profile builder. Use the
recorded worker image ID in the catalog and worker configuration. Provision one
worker per static slot with its own private network route to Context, immutable
source mounts, read-only root, unprivileged UID 10003, private temporary workspace
and durable ASRUN volume as described in [the audit storage profile](DURABLE_AUDIT_STORAGE.md).
Mount its role-specific private configuration at `/credentials/config.json`.

```json
{
  "assigned": {
    "ca": "/credentials/ca.pem",
    "certificate": "/credentials/tls.pem",
    "key": "/credentials/tls.key",
    "context_url": "https://context:9443",
    "context_fingerprint": "<64 lowercase hexadecimal characters>",
    "context_id": "A",
    "worker_slot": "one",
    "worker_incarnation": "instance-1",
    "runtime_image": "sha256:<worker image digest>",
    "snapshots": {"<approved source manifest digest>": "/source"}
  },
  "native_prompts": true
}
```

An assigned prompt-enabled worker sends the original question and its ordered
options privately to Context. Context retains them in memory while that prompt
is open. The current controller can choose **View prompt** in the browser
workspace or the installed Qt panel, then send an answer or explicitly cancel
the native prompt. **Dismiss** closes the dialog without responding. Context
rechecks the controller, original member, definition digest, current generation
and delivery state. A queued reply removes that answer opportunity. Restart or
an uncertain delivery requires operator reconciliation. Audit and replay contain
identifiers and outcomes. The question, choices and answer remain private.

### Live controller transfer on one Linux host

Set the assigned worker's `native_handoff` to `host-freeze-epoch` alongside
`native_prompts: true` to enable live transfer. Configure Context with
`native_pause: "host-freeze-candidate"`, the independently pinned
`single-host-terminal-candidate` settlement host, and the native child, command
and prompt journals. Mount a separate operator-controlled directory read-only at
`/control` in the worker. The Gateway and worker have no Docker management
socket or operator credentials.

The operator binds the immutable, originally created container ID and image to
the exact Context incarnation and reservation before the assigned start. It
writes the admitted start request UUID to `/control/handoff-epoch`. When the
controller accepts a claim, the operator atomically writes the same current UUID
to `handoff-prepare` and verifies that the worker drained its outstanding RPCs.
The operator then independently freezes the original cgroup. Its private
handoff completion requires the kernel's completed freeze, the matching sealed
member roster and original living process handles. The new controller explicitly
rebinds and requests **Run / Continue**. Only after a matching private resume
receipt does the operator atomically install the new runtime epoch and unfreeze
that original worker. A lost one-shot activation keeps authority fenced.

The operator can witness a single Docker Desktop worker in a separate
capability-free, read-only container using the bound worker's PID namespace and
read-only cgroup-v2 observations. It holds original pidfds across every transfer
and verifies Executor executable hashes and kernel birth ticks. The authority
retains ownership and capacity for recovery if any required proof is absent.

When native prompts are enabled, provision the prompt-enabled native build and
configure Context with `native_prompts: "owner-reply-candidate"`. Each worker
accepts a configured source digest and independently checks the read-only tree.
Only the original controller can then admit the start. Context gives the
assigned worker one private delivery and persists its consumption. A lost
admission, delivery or consumption reply leaves the reservation held for
operator reconciliation. Refresh displays the current public state. Start and
Run are separate operator actions, including after any reconnect.

## Operator-provisioned retained profile

The retained profile, introduced in `0.8.0.dev8`, is an explicitly enabled `worker_launch: "retained-single-use"`
Context profile. Default services and the desktop gateway/Listener do not expose
native execution. This profile is not a qualified v0.8 release or a general
execution service. `runtime_enabled` remains false for the public product.

The authenticated Listener identity can submit `execution.start` directly to a
Context with this profile. Context repeats live start/control authorization,
original controller proof, immutable catalog and fresh worker source-preflight
checks. It returns the original start grant once. Response loss never replays a
plaintext grant. The operator provisions that grant to its assigned worker;
workers have no admission, epoch refresh, release or recovery endpoint.

Registered worker certificates can use `/v1/worker/consume` and
`/v1/worker/check` only when the profile is enabled. Consumption atomically spends
the assigned incarnation once under the existing execution mutex and durable
ledger. Schema, original scope/provenance, actual peer certificate, owner,
session, generations and start permission are checked. A lost reply prevents
native startup and retains all holds. A check does not admit a driver effect or
prove pause/quiescence. Controller handoff after consumption still blocks and
retains the original owner and recovery holds.

The new GPL `host_runtime/python/v08_worker.py` is separate from the Apache
Context package. It verifies the approved source on a read-only mount, requires
a read-only image root, performs one consumption request, then opens the actual
original Listener/Context/Executor via the frozen native bridge. It checks the
original grant again before the fixture's initial RUN. It never retries a
consumption or RUN, refreshes provenance, releases logical holds, reuses a worker
or claims that best-effort native process cleanup proves whole-container
quiescence. The independent host must confirm container termination.

The actual proxy driver is mandatory. Procedure-scoped EV/RaiseEvent calls are
forwarded over mTLS to Context and acknowledged only after a durable atomic
journal commit under the original grant and execution mutex. Scope/system and
configuration writes are denied. Idempotent receipts are checked only after
live authorization. The retained launch protocol is `openbexi.worker/2`;
preflight remains `openbexi.worker/1`. Only the single consumption winner
receives a separate memory-only runtime proof, required on check/event/driver
calls in addition to its unchanged original grant. Only its hash is committed,
atomically with consumption. Lost replies retain holds and cannot refresh this
proof. Current child admission uses schema 10; unsupported older binaries fail closed. The native controller
itself emits lifecycle events even for arithmetic-only procedures. All other
native driver methods remain denied; no ExampleDriver or fabricated success is
allowed. The optional Context-owned TC/TM integration is described in NATIVE_DSS.md;
it has its own mandatory native cohort. Default native profiles reject child
notifications. The separate dev17 before-spawn child provider and its exact
qualification scope are described in NATIVE_CHILD_ADMISSION.md. Unknown/uncooperative Python descendants are not a qualified
sandbox or handoff protocol. Only approved trusted qualification fixtures run.

## Native concurrency test

`scripts/qualify_v08_native_launch.py` provisions an isolated Context container
and ten single-use native workers, without mounting a Docker socket or host
manager into Context or workers. Each worker has its own certificate, source
mount and internal network shared only with Context. The host provisions and
checks containment independently. A separate Context development image adds Git
to the verified frozen base; its image ID/build log/Git version are retained.
This image is not a release build or a claim of reproducible dependencies.

Startup is staggered with the verified baseline worker resource limits. The
test requires ten distinct procedures to reach RUNNING together before its
finish barrier. Docker's host PID inventory must identify thirty distinct real
Listener/Context/Executor processes. It checks cross-worker native-port and
external-network denial, blocked post-start handoff, unaffected other owners,
actual completion, unique durable start/finish events, terminated containers,
ten spent worker slots and ten retained reservations. The passing cohort attempts
handoff after container termination; earlier failed completion evidence retains
its separate blocked handoff while all ten native workers were RUNNING. Hashes, native event logs and container/PID evidence are retained,
including failures. A workflow success is required before claiming this test
passed; adding a harness does not satisfy a qualification gate.

This test does not qualify production Compose, Kubernetes admission/identity,
node fencing, safe native pause/resume/handoff, child semantics, native driver
TC/TM dispatch, all 763 requirements, browser/WSS, or IDE Run/Debug. Those remain
release blockers. Existing prelaunch IDE integration continues separately.

The optional development DSS variant is specified in [NATIVE_DSS.md](NATIVE_DSS.md).
It keeps this audit-only cohort and adds a separate native TC/TM CI cohort with
Context-owned endpoints, explicit resource permissions and the actual-send
gate. Its results must be tied to the exact candidate SHA; its presence does
not turn an unexecuted native or deployment test into a pass.
