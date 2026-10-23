# Current limitations

The branch includes the approved architecture resolutions and an initial
internal Listener/Context foundation in `server/`. It provides TLS identity
checks, scoped routing, Context-local ACLs, durable blackboard CAS, prelaunch
reservations and ownership claims/acceptance/rebind. It
explicitly reports `runtime_enabled: false`.

The private one-time start-grant ledger has protocol tests. Optional approved
Git inventories and a pinned single-host mTLS worker preflight are implemented;
see WORKER_PREFLIGHT.md. There is no native launch network path. Source is
verified only for configured catalogs; metadata-only reservations cannot pass
Context's start guard. Runtime-image and read-only-mount attestation remain
unqualified, and a trusted worker's digest report is not hardware attestation. Acceptance succeeds only before consumption;
a post-consumption transfer is blocked and retains recovery holds. Native pause,
native effect settlement, source/alias/child admission, full driver adaptation,
browser sessions/WSS, UI, Compose and Kubernetes remain unimplemented or
unqualified. No release/recovery/capacity-reclamation operation is exposed.
See EXECUTION_AUTHORITY.md for exact limits. Full C/D and E-L gates remain pending.
There is no v0.8 release candidate, release tag, production replacement or
claim of full candidate-SHA runtime/deployment qualification. The hosted service
and prelaunch workflow covers its own subset only. Published v0.7 runtime source and entry points are unchanged.

Initial target Compose workers are single-use; automatic reuse is disabled.
Supported target authority storage is single-node local ext4 with explicit
manual fencing for replacement. Native child admission requires requalification.
The local foundation tests do not prove production storage/fsync/node fencing.

Certificate/identity configuration changes require process restart. The new
server is internal Linux-only; it is not a public browser endpoint. The trusted
approved-procedure/host scope remains in force. Vendor GCS, real spacecraft,
untrusted Python sandboxing, automatic uncertain-effect replay and HA remain
unqualified. See G1_REVIEW_RESOLUTION.md, SERVER_CONTRACT.md and RISKS.md.

## Paired IDE and compatibility qualification

The IDE's new SPELL server tab supports discovery, reservations, observers and
explicit prelaunch handoff. Native Run/Debug are unavailable; local action
fallback is rejected while connected. Browser/WSS and full deployed execution
remain pending. See IDE_PAIR.json for the exact tested companion source.

The current historical root test suite is not a portable full qualification:
it references older absolute Windows capture paths and immutable source
checkpoints that differ from current source. The failed broad diagnostic is
retained, alongside the passing explicit portable subset. Restoring the
published v0.7 capture archive alone does not satisfy all those older
references. Fresh complete native compatibility evidence on the correct
immutable source, plus driver settlement and deployment/recovery tests, remain
release blockers. Preparatory syntax and resource-lifetime source fixes do not
qualify a rebuilt native image or approve a release.

The private driver seam now serializes the final live check and bounded binary
TCP write with controller fencing and reserves separate authority/driver intent
ledgers. See DRIVER_WRITE_GATE.md for the exact tests and trust boundary. It is
not a native or network-accessible runtime path. Post-start handoff continues to
block without proven native quiescence; no release gate is waived.

An opt-in retained native launch profile is now implemented; see NATIVE_LAUNCH.md.
It is separate from the default public/IDE path and requires original
controller admission plus certificate-bound consumption. Its native worker
forces the real proxy, journals scoped audit events in Context while denying
other driver operations, retains every hold, and
fails on observed children. It does not qualify general native control,
quiescence, descendant containment or native driver integration. The ten-worker
Docker harness must actually pass before any native concurrency result is
claimed.
