# Requirement-to-change map

| ID | Verified gap / baseline capability | Proposed change | Required evidence |
|---|---|---|---|
| GAP-01 | Local service restricts parallel runs; durable service has slots | Separate Listener routes independent Context authorities; 10 worker slots | 10 distinct runs, PIDs and health; Listener restart |
| GAP-02 | Durable controller and handoff are session-wide | Owner, epoch and lease per ExecutionID | U1 controls A/B/C; transfer B leaves A/C unchanged |
| GAP-03 | No request/accept claim record | Durable single-pending claim, owner-only accept/reject | Claims, expiry/cancel, replay and race tests |
| GAP-04 | Local owners lack durable per-run epoch | Atomic Context CAS, per-command identity/epoch/idempotency | Stale actor/token/session and in-flight races |
| GAP-05 | Native chain exists inside per-run runtime | Supervised workers, modern Context authority, unchanged native semantics | Process tree, child cleanup, worker crash isolation |
| GAP-06 | Logical aliases/reservations already persist | Scope reservation to ContextID + ProcedureID, preserve uncertain holds | 100 duplicate races; cross-Context isolation |
| GAP-07 | REST polling UI; monitor restrictions exist | HTTPS/WSS gateway, bounded replay, many panels, claim notifications | Multi-browser E2E; observer negative tests |
| GAP-08 | External DSS transport exists; teaching DSS embedded | Independent deployed DSS; explicit Context adapter capabilities | Round trip, loss, timeout, correlation and no replay |
| GAP-09 | Captured/approved sources already immutable | Bind clean Git commit and full inventory to execution; isolated developer workspaces | Same-file conflict tests, immutable running revision |
| GAP-10 | Single local desktop Compose deployment | Multi-service Compose and Kustomize deployment | G6/G7 failure and security gates |
| GAP-11 | Durable restart rotates credentials and holds runs | Persist per-run owners/epochs/claims, cancel claims and fence on restart | Restart/recovery proof; no takeover/replay |
| GAP-12 | No hosted CI checks on baseline | Python 3.13 CI, native compatibility, browser/integration/deployment jobs | Green hosted CI URLs tied to exact candidate SHA |

The source remains unchanged while the architecture is reviewed. Changes to
the IDE's neutral transport/UI belong in a separate IDE branch; SPELL behavior
stays in plugin/provider code. No global replacement of Session's controller
field is proposed: its slot, checkpoint, debug and driver paths all rely on it.
