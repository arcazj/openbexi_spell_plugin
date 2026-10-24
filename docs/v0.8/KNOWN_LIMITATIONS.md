# Current limitations

SPELL v0.8 remains a development implementation. Public services report
`runtime_enabled: false`; PR #2 is draft, and no stable v0.8 release is qualified.
G1 authorized staged implementation under F1–F10. It did not establish that the
runtime, recovery, deployment or release gates had passed. See STATUS.json,
TEST_REPORT.md and RELEASE_GATES.json for exact candidate identities and results.

## Implemented private profiles

Internal services implement pinned mTLS identity, explicit route/role checks,
Context ACLs, durable SQLite CAS, original-grant reservations, ownership
claims/acceptance/rebind before launch, immutable approved Git inventories and
worker preflight. The catalog can contain 64 approved entries, including children;
there are ten retained worker slots. Source verification covers configured
catalogs only. A worker report is not hardware, Pod or image attestation.

The operator-provisioned retained profile adds one-time certificate-bound grant
consumption, actual native Listener/Context/Executor launch, durable procedure EV
audit and a separate Context-owned TC/TM subset with explicit resource allowlists.
The actual-send gate repeats live authorization under the same execution mutex
as fencing and records separate authority/driver intents and correlated receipts.
It never retries an uncertain effect. Read DRIVER_WRITE_GATE.md and NATIVE_DSS.md
for those component boundaries; they are no longer merely disconnected adapters.
Complete driver methods, lifecycle, overload, reset, loss and recovery remain
unqualified. A retained failing native DSS burst is documented in TEST_REPORT.md.

The dev17 child provider builds a new native Context from the frozen image's
checked source/recipe provenance. It admits and consumes an approved child
before physical spawn, preserving original zero-based native instance IDs. It
authenticates the native Context process and original family over the separate
local and mTLS boundaries. The agent disables dumpability before configuration
or native startup to protect its memory-only consumption proof; deployment must
also drop all capabilities. See NATIVE_CHILD_ADMISSION.md for candidate results.
Default profiles still reject children. Native manual/nonblocking modes, broader nested execution,
child prompt/return/repeat/failure semantics, per-child driver attribution and
complete descendant containment require additional qualification. Admission
and native status observations do not establish quiescence or release a hold.

## Ownership and recovery blockers

Post-consumption ownership transfer remains blocked without complete native
quiescence proof. The main native PAUSED state alone leaves a background thread
running. The optional cooperative barrier holds observed snapshot Python threads
only; it does not prove that C/native/generated code, children, prompt/control
queues and external effects are settled. Neither component authorizes effective
handoff or resume. Unknown outcomes retain the owner/epoch and recovery holds.

No automatic worker reuse, logical-hold release, capacity reclamation, uncertain
command replay or authority relocation is exposed. Native FINISHED, process-group
cleanup and container termination are distinct observations; none alone is a
whole-family recovery protocol. Single-authority storage, node fencing,
backup/restore and upgrade/rollback still need deployed fault qualification.
Certificate and fixed identity configuration changes require process restart.

At 56439d7, killing and recreating the separate v0.8 Listener preserved ten
advancing native procedures, thirty PIDs, Context incarnation and original
owners/epochs/generations. This read-only observer component does not establish
active-controller disconnection behavior, browser/WSS or recovery. See
`evidence/listener-survival/qualification-summary.json`. The push scoped suite
passed 382 tests; the PR suite retained one concurrent duplicate-driver denial
assertion failure. Exact status/error diagnostics are being added; its cause is
not yet established, and that PR workflow is not qualified.

## Joint product and full qualification

The pinned IDE supports discovery, reservations, observers and explicit prelaunch
handoff through real mTLS and Qt integration. At d523c96 its installed client
observed ten actual native executions through a separate gateway, failed closed
during Listener loss and reconnected to the original executions after replacement.
The read-only user was denied control. The digest/CRC and 24 source hashes were
verified; see `evidence/listener-survival/ide-observer-summary.json`. Native IDE Run/Debug, browser/WSS,
Git collaboration and the full joint deployed workflow remain unfinished or
unqualified. No local fallback is authorized while connected to the server.

The passing 241-test portable subset is not all-763 qualification. Inherited
archival tests refer to older immutable source checkpoints and absolute Windows
capture paths. Published v0.7 captures do not satisfy all those older references.
Their failed diagnostics remain retained; no skip, restamped hash or fabricated
capture is used to claim compatibility. Published v0.7 bytes and original legacy
patch preimages remain unchanged.

Production Compose and Kubernetes admission/RBAC/Pod identity/network/storage
faults, a production-like cluster, independent implemented-system security
review, bounded load, SBOM/license/vulnerability disposition and final stable
installed artifacts remain mandatory. Vendor GCS/spacecraft integration,
untrusted Python sandboxing and distributed HA are outside the qualified scope.
The full-publication preflight rejects this candidate until every mandatory gate
has valid exact-source evidence. Publication is blocked by incomplete work and
qualification, not by a missing routine owner confirmation.
