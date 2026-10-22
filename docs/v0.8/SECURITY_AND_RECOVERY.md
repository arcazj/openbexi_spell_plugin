# Proposed security and recovery boundaries

`TARGET-v0.8`; this is a threat model and test plan, not a completed security
review. Preserve the v0.7 trusted operator OS/Docker host and approved-procedure
scope. CPython `-I` is not a security sandbox. Untrusted tenant Python requires
separately demonstrated isolation and cannot be claimed from these documents.

| Threat / failure | Required enforcement and test |
|---|---|
| Observer or stale controller mutation | Context checks principal, execution, epoch and connection capability on every mutation and every driver effect; negative tests on all alternate paths |
| Identity/header/session spoofing | Registered client identities, authenticated edge/Listener/Context roles, strip forwarded headers, exact Origin/Host checks, no secrets in URLs; forged/revoked certificate tests |
| Claim or command replay | Durable idempotency/payload binding and monotonically fenced ownership; duplicate/delayed/cross-execution request tests |
| Python/debug expression execution | Read-only snapshot, separate bounded worker container/Pod per active run, no authority/host mount, no engine socket, no direct driver-egress; debug evaluate is mutating |
| Worker credentials stolen by procedure | Worker-role identity cannot impersonate Context, issue owner tokens or bypass Context effect admission; no Context/driver secrets in worker environment |
| Cross-Context leakage | Separate state volumes, certificates, blackboards, source paths and driver bindings; credential and data-negative tests |
| Listener loss | Context/worker lifetimes independent, bounded replay/reconnect; claim never auto-accepted |
| Context loss or disk full | Persist intent before side effect; revoke tokens/advance epochs, preserve active/uncertain reservations and driver journals; no automatic resume/replay |
| Worker/node partition | Loss of heartbeat is uncertain; fence driver writes, retain reservation; no replacement until shutdown/effect proof |
| DSS loss / unknown TC outcome | Fail/degrade affected run, persist intent and receipts, no uncertain telecommand retry; unrelated runs stay healthy |
| Slow viewers / overload | Bounded queues, replay, logs, requests, claims, connections and stored idempotency; reject new work before effects; 20 required/100 stress viewers |
| Git path/credential exposure | Separate workspaces, expected-base conflict checks, allowlisted Git operations, excluded credentials; immutable approved execution digest |

## Deployment policy

Non-root workloads, dropped capabilities, no-new-privileges, read-only root
filesystem, bounded writable tmpfs, PID/CPU/memory limits, seccomp, health probes,
secrets outside Git and rotated structured logs. Only TLS edge publishes a port.
Compose networks alone do not prove egress denial: host/container firewall
rules and a negative reachability test are mandatory. Kubernetes defaults to
deny ingress/egress with explicit DNS, Context/worker and adapter/DSS paths.

K8s Context Job creation needs RBAC **plus admission restrictions** on images,
mounts, service accounts and privileges; basic Job-create RBAC is insufficient.
One authoritative Context replica owns a single-writer PVC. Storage fencing,
failed node replacement and stale authority must be tested, not inferred from
`replicas: 1`, RWO access mode or a Kubernetes rollout.

## Recovery/migration policy

Reuse the accepted offline backup/restore model: exclusive authority lock,
consistent SQLite backup, bounded inventory with path/hash validation, exact
shutdown and effect-settlement evidence, increased epochs, revoked approvals
and no automatic execution replay. New per-execution ownership/claim records
need migration tests. Never reuse an old control capability after restore.

v0.8 runs on new state volumes and separately configured ports. Before any
production migration, back up source/preferences and compare inventories;
preserve all uncertainty holds. Rollback stops v0.8 authorities/workers,
settles external effects, and restores the retained v0.7 deployment against
its own compatible state. Never point v0.7 directly at a v0.8 database.

Image provenance, SBOM, dependency/license review, vulnerability scans, secret
scan, source/artifact integrity and exact-SHA hosted CI are mandatory release
evidence. They have not been performed for a v0.8 candidate because none exists.
