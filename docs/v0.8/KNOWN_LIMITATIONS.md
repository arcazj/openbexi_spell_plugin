# Current limitations

This branch currently contains the v0.8 baseline audit and architecture proposal
only. v0.8 server, per-execution ownership/claims, WSS dashboard, static worker
pool, Compose deployment and Kubernetes support have **not been implemented**.

Fresh checks cover the unchanged v0.7 baseline. They are not v0.8 acceptance.
There is no v0.8 release candidate, tag, public release, green hosted CI or
completed runtime qualification. Independent review and owner-authorized
resolutions are recorded in G1_REVIEW_RESOLUTION.md. Production remains the healthy v0.7 desktop.

Legacy vendor GCS, real spacecraft, RF operations, untrusted Python sandboxing,
automatic recovery/replay and HA are not qualified. See [RISKS.md](RISKS.md).

Initial Compose worker containers are single-use; automatic reuse is disabled.
Supported authority storage is single-node local ext4 with explicit manual
fencing for replacement. Native child admission requires requalification.
