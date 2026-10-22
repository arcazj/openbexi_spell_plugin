# Mandatory acceptance plan

All rows are **NOT RUN for v0.8**. Tests must exercise the real boundary
identified below, retain failed attempts and attach source/image identities.
Unit mocks alone cannot satisfy deployment, native, browser or partition gates.

| Gate | Mandatory scenarios | Artifact |
|---|---|---|
| G0 / A | Exact v0.7 tag, latest master, dirty-work preservation, process/protocol audit, focused baseline reproduction | baseline-audit.json, source inventory, native trace, JUnit |
| G1 / B | ADR-01..12, independent architecture/security challenge, owner approval of proposed boundaries | review decision and approval reference |
| C | Unauthorized discovery, concurrent clients, stale Context registry, Listener restart while workers run, reconnect | Real process/API trace |
| D | Independent Contexts, blackboard/config/credential isolation, event ordering, Context crash | Two real authorities and durable histories |
| G2 / E | 10 distinct concurrent procedures, 100 same-logical-procedure start requests, immutable source, alias/version races, unique PIDs, abort/pause/crash/stale holds | Concurrency report, PID/Pod trace and reservation SQL |
| G3 / F | U1 controls A/B/C; 20 observers; all mutations/prompts denied to observers; request/no response/reject/accept B; A/C unchanged; stale commands; two claims/accepts; cancel/expiry; transfer vs driver write; disconnect/reconnect/restart | API traces with epochs and browser E2E, ordered audit |
| G4 / G | All inherited 763 requirements against correct immutable sources, native runtime suites, original Driver contract/capabilities, cancellation/time/error/prompt behavior | Compatibility matrices, native and installed reports |
| G5 / H | Independent DSS PID/endpoints; TC/TM/ack correlation; reconnect/reset/network loss; unknown outcome no replay; unrelated workers survive | Simulator/fake-GCS trace and fault records |
| I | Three independent authenticated browser users, multiple panels, identical observers/progress, accept/reject widgets, WSS gap resync, same-file developer conflicts | Chromium E2E with screenshots and no page errors |
| G6 | `docker compose config`, clean isolated boot, 10 runs/20 viewers, secrets/negative auth, worker/Listener/Context/DSS loss, SQLite crash/disk failure/restore, egress-negative tests | compose config, logs, health/network matrix, backup checks |
| G7 | kind/minikube plus production-like cluster; 10 Jobs/20 viewers, node drain/partition, DNS/DSS loss, RBAC/admission and NetworkPolicy denial, stale epoch, WSS replay, storage fail/recover, backup/upgrade/rollback | Cluster versions/commands/logs/Job identities; no YAML-only pass |
| G8 / J | Auth/replay/secret/source integrity, bounded load, 100+ viewers where capacity allows, dependency/SBOM/license/vulnerability scan, independent review | Security report, explicit owner-approved risk exceptions |
| K | Clean checkout format/lint/types/unit/Python 3.13/native/protocol/driver/DSS/isolation/claims/recovery/Git/API/Chromium and deployment CI | Green hosted CI URLs tied to candidate SHA |
| G9 / L | Reviewable PR, docs/runbooks/manifests, version/package consistency, checksums, explicit owner publication approval, annotated tag, downloads and smoke/rollback | Approved release URL, tested/tag SHA and download receipts |

## Required implementation order

Finish A/B review before invasive modifications. After approval, implement C/D
contracts with deterministic transactional tests, then E/F workers/ownership,
then G/H native/driver/simulator, then I UI/Git and J security/failure injection.
Prepare Compose/K8s manifests and qualification scripts during E–J, and wire
all mandatory checks into CI during K. Any failed mandatory gate stops dependent
release progression. Fix/retest; never turn a failed test into a documented pass.

Release artifacts must include architecture/ownership/concurrency and protocol
docs, `SPELL_COMPATIBILITY_MATRIX.md`, `DRIVER_COMPATIBILITY.md`,
`DSS_INTEGRATION.md`, deployment/network/runbooks, security/recovery, test report,
changelog/release notes, known limitations, DOT/PNG/checksums, Compose/Kustomize
sources and actual qualification evidence. These audit documents do not stand
in for missing implementation deliverables.
