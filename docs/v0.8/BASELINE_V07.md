# Baseline evidence — Phase A / G0

Evidence collected 2026-10-22 UTC. `VERIFIED-v0.7` means inspected source,
published metadata, or retained qualification evidence; fresh checks are
identified separately. `TARGET-v0.8` is a proposal; `UNKNOWN` is not a pass.

| Item | Evidence |
|---|---|
| Repository/default branch | https://github.com/arcazj/openbexi_spell_plugin, `master` |
| Published v0.7 commit | `109a47af47951e2fa54b60cb408a543b117f7f15` |
| Correct new base | `76144fb704a8e3777209df04058c62d80bbc962f`, latest remote master at audit |
| Changes after v0.7 | Requirements document and preserved architecture PNG only |
| Dedicated branch/worktree | `feature/v0.8-server-architecture`, `C:/obspell_v08` |
| IDE baseline | `7585d221a58fcfe178b93046c691ad74a92148e9`, release 1.2.0 |
| Native runtime image | `sha256:d99b095d65c7fef008f9e6c02ff95c678cff295ee85a129f7a62fc0b795b1283` |
| Native source/runtime | Accepted source wheel 0.6.0; CPython 3.13.15 |
| Packages | host/shared/DSS/JetBrains 0.7.0; SDK 0.1.0 |
| Published releases | SPELL v0.7: 15 assets; IDE v1.2.0: 13 assets, both public |
| GitHub CI at baseline | 0 Actions runs, 0 check runs, 0 commit statuses; aggregate status `pending` |
| Open PRs at audit | 0 |

The original plugin worktree is older (`6a00c5c`) and has four uncommitted
JetBrains/layout files. Their hashes were recorded and checked after this work.
They were preserved. The latest remote v0.8 requirements, rather than that old
worktree, form the new branch base. All local branches and remote refs are
inventoried in [evidence/baseline-audit.json](evidence/baseline-audit.json).

## Actual implementation

`VERIFIED-v0.7`: the IDE has two different service paths. Treating either as the
complete proposed v0.8 server would be incorrect.

* `openbexi_runtime.procedure_service.ProcedureService` serves the desktop and
  browser procedure workspace. It has per-run `owners`, but `start()` requires
  existing runs to be paused; packaged desktop permits only one live instance.
  `claim()` acquires an unowned run, not a consent request to its current owner.
* `openbexi_runtime.session.Session` plus `session_http.SessionServer` is the
  durable Development/approved Execution authority. It supports parallel slots,
  immutable capture, logical procedure reservations, durable audit, and fenced
  driver writes. It has **one controller and epoch for the whole session**.
  `handoff()` pauses/transfers session control; it is not a per-execution claim.
* `openbexi_spell_shared.Worker` starts an isolated native container for each
  run, routes DAP and original-schema driver calls over private pipes, and
  attaches authority on the service side. Its native adapter launches the
  already-qualified native Listener → Context → Executor process chain.
* `host_runtime/python/demo_dss.py` embeds a disposable teaching DSS in the
  adapter process. Durable shared execution can instead use external DSS HTTP
  and binary TC endpoints. These are distinct deployment modes.
* The browser workspace polls REST snapshots. It is not a WSS event gateway.

Source locations and protocol details are in [PROCESS_AND_PORT_MAP.md](PROCESS_AND_PORT_MAP.md)
and [PROTOCOL_REGISTER.md](PROTOCOL_REGISTER.md). The separate IDE repository
is part of the required implementation scope; it has not been changed here.

## Fresh baseline execution

37 baseline IDE session, durable-session and procedure-service tests passed
with warnings treated as errors. A further installed native/DSS acceptance
test passed using the exact published native image and installed 0.7.0
host/shared/DSS packages. During that test, `docker top` observed distinct
`SPELL-Listener`, `SPELL-Context`, and `SPELL-Executor` processes. The test sent
CMD1 through the original driver RPC and binary DSS transport, observed TM,
and checked correlated DSS receipts. [Raw trace](evidence/native-trace.json).

The UI → procedure service → installed DAP host → native Listener/Context →
Executor call path was inspected in source. Actual browser and Qt UI execution
was qualified in the retained v0.7 evidence; this audit did not repeat browser
interaction. Historical UI evidence is not relabeled as a fresh v0.8 test.

Retained v0.7 reports record 763 qualified language requirements, 61 native
suites / 2,157 checks and 90 installed operational tests. Their files/hashes
were checked; the full historical suite was not rerun for this documentation
change. No v0.8 concurrency, transfer or deployment result is claimed.

## Running deployment

Fresh inspection: `openbexi-ide-spell-v07-ide-1` is healthy, using the accepted
desktop image `sha256:cc41cf1a0ba2d7b670d8c831066c51b22fe2b7974f5803034d8c3fa2a133fc9d`.
Only `127.0.0.1:6080` is published. Existing workspace and preferences volumes
remain attached. No production authority, source, preference, cache or image
was removed or upgraded. Future migration must use separate state and ports.

G0: baseline identified, source inventoried, focused reproduction passed;
missing hosted CI is documented and must be fixed before release. Phase A's
independent review remains pending alongside the Gate B architecture review.
