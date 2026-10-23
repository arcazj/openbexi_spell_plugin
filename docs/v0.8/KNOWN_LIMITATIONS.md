# Current limitations

The branch includes the approved architecture resolutions and an initial
internal Listener/Context foundation in `server/`. It provides TLS identity
checks, scoped routing, Context-local ACLs and durable blackboard CAS. It
explicitly reports `runtime_enabled: false`.

Native v0.8 procedure execution, execution reservations/worker start grants,
per-execution ownership/claims, transfer barriers, driver adaptation, browser
sessions/WSS, development UI, Compose and Kubernetes are not implemented or
qualified by this foundation. Full C/D integration and E-L gates remain pending.
There is no v0.8 release candidate, release tag, production replacement or
claim of full candidate-SHA hosted CI. The new foundation workflow covers its
own subset only. Published v0.7 runtime source and entry points are unchanged.

Initial target Compose workers are single-use; automatic reuse is disabled.
Supported target authority storage is single-node local ext4 with explicit
manual fencing for replacement. Native child admission requires requalification.
The local foundation tests do not prove production storage/fsync/node fencing.

Certificate/identity configuration changes require process restart. The new
server is internal Linux-only; it is not a public browser endpoint. The trusted
approved-procedure/host scope remains in force. Vendor GCS, real spacecraft,
untrusted Python sandboxing, automatic uncertain-effect replay and HA remain
unqualified. See G1_REVIEW_RESOLUTION.md, SERVER_CONTRACT.md and RISKS.md.
