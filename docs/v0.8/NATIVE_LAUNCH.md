# Retained one-shot native launch profile

`0.8.0.dev8` adds an explicitly enabled `worker_launch: "retained-single-use"`
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
live authorization; schema 6 prevents old-binary downgrade. The native controller
itself emits lifecycle events even for arithmetic-only procedures. All other
native driver methods remain denied; no ExampleDriver or fabricated success is
allowed. The external-socket driver seam is not yet integrated with native RPC
dispatch. Native child
notifications cause failure; full pre-run child reservation still needs native
bridge work. Unknown/uncooperative Python descendants are not a qualified
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
