# Current limitations

The branch includes the approved architecture resolutions and an initial
internal Listener/Context foundation in `server/`. It provides TLS identity
checks, scoped routing, Context-local ACLs, durable blackboard CAS, prelaunch
reservations and ownership claims/acceptance/rebind. It
explicitly reports `runtime_enabled: false`.

The private one-time start-grant ledger has protocol tests, but no authenticated
worker network adapter or native launch path. Source/image fields are declared
metadata, not verified inventories. Acceptance succeeds only before consumption;
a post-consumption transfer is blocked and retains recovery holds. Native pause,
actual-send/effect settlement, source/alias/child admission, driver adaptation,
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
