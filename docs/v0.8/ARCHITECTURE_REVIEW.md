# Architecture review readiness and challenges

Review status: **author self-review completed; independent review and owner
approval pending**. No independent reviewer or sub-agent result is fabricated.

| Challenge from source audit | Response in proposal | Remaining proof |
|---|---|---|
| Simply changing a global owner field can miss slot/debug/driver checks | New per-execution authority and complete mutation map; keep old service operational during migration | All command and effect paths tested |
| v0.7 already has native Listener/Context, so is the server done? | They are private per-run engine helpers, not a modern multiuser Context authority | Process/routing trace with no alternate control endpoint |
| Compose cannot launch a fresh container per run | Static constrained worker pool, one active Executor per service; no Docker socket | Lifecycle/reuse/quiescence, capacity and fault tests |
| Worker heartbeat expiry might allow duplicate external effects | Retain reservation and fence writes; timeout is not termination proof | Partition/crash/recovery tests |
| A transferred epoch might appear to undo an already sent command | Define admission linearization; retain actual old admitted command outcome; block subsequent old-epoch writes | Transfer vs write/ack fault injection |
| SQLite/PVC + one replica may be mistaken for HA/fencing | OS-exclusive single authority and supported storage only; fail closed, no HA claim | Node/storage failure tests and authority exclusion |
| Kubernetes Job-create privilege can mount secrets/host paths | Admission restrictions and separate role/Context boundaries in addition to RBAC | Negative arbitrary image/mount/service-account tests |
| UI can hide a button but leave DAP evaluate or prompt route open | Server owns full mutation classification and capability checks | Direct API/worker/driver negative tests |
| Old manual/source versions can be conflated | 2.4.4 manuals vs 2.6.10 source explicitly distinguished | Source-linked compatibility matrix |
| Baseline qualification might be called green hosted CI | Hosted checks are absent; fresh local tests and retained evidence labeled separately | New CI with exact-SHA green runs |

G1 remains **PENDING**, not PASS. The review package is concrete enough for
the owner to approve or revise ADR-01..12, particularly the static Compose pool,
Context-owned single-writer SQLite, mTLS service RPC, per-execution consent
protocol and K8s Job/admission boundary. Approval authorizes implementation,
not a release, security exception, merge or tag.
