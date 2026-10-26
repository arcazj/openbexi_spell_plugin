# Controller and network recovery boundaries

Dev55 exercises seven faults using the production TLS transport, durable Context
state and worker handoff activation. Freeze/process evidence is supplied by the
existing explicit test fixtures. These cases establish protocol and persistence
behavior; native quiescence and deployed node partitions require separate tests.

| Fault boundary | Required outcome |
| --- | --- |
| Connection closes after `session.close` commits | Old grant denied; durable close receipt replayable; recovery requires a fresh session and host barrier |
| Controller client process dies after close commits, before its reply | Same durable fence; original native ownership and reservations retained |
| Connection closes after pending rebind commits | Exact-key replay returns the same pending barrier; no capability before host proof |
| Pending rebind reply stalls beyond the client deadline | Same pending barrier and original ownership; no automatic continuation |
| Runtime activation reply disconnects after commit | Worker records uncertainty; its original request remains unchanged; activation is not retried |
| Runtime activation reply stalls beyond the production read deadline | Same uncertainty fence; no grant restamping or automatic resume |
| TCP connection accepts but TLS never completes | Bounded transport failure; no inferred native pause; explicit rebind and host recovery remain required |

Every case also checks an independent observer read within two seconds, the
original owner/epoch, retained reservation and spent worker. A successful recovery
uses the existing explicit host completion and activation protocol. Lost replies
do not justify replay of an uncertain effect. The client-death case kills a real
separate TLS client process; it occurs **after an explicit close has committed**.

## Automatic liveness component

Dev56 adds four automatically detected loss cases: a killed controller process,
a lost heartbeat acknowledgement, a stalled reply and a TCP/TLS blackhole.
All retain holds and complete explicit recovery using fixture host proofs. The
original seven dev55 cases remain regressions; their legacy prelaunch blackhole
case intentionally has no lease and continues to report no automatic detection.

Retained native Contexts now require a monotonic lease, defaulting to 30 seconds.
Rotating challenges prevent replayed or queued old heartbeats from extending it.
Both native and installed-IDE cohorts verify automatic fencing with eight
original processes and host-proven explicit resume. Their injected fault is
heartbeat transport detach, not a deployed node partition. See
[AUTOMATIC_CONTROLLER_LIVENESS.md](AUTOMATIC_CONTROLLER_LIVENESS.md) for the
protocol, evidence limits and remaining native-memory concern.

## Reproduction

Run `python scripts/qualify_v08_faults.py` in the hosted Linux environment with
the pinned qualification requirements. The runner preserves source hashes,
JUnit and `controller-network.log`; socket-capable execution is mandatory.
`server/tests/test_controller_network_recovery.py` contains the fault selectors,
which are confined to tests. No production retry or deadline extension is added.

All eleven full-v0.8 release gates remain unqualified.

## Source-bound qualification

Candidate `81b8b41be71a3420241ed8163535e65518987226` passes the available hosted component profiles.
1,210 service tests, 71 overlapping fault probes and 241 portable tests pass, with zero failures/errors/skips. All fourteen core jobs and five ancillary workflows pass. All nineteen artifact archives and recorded source hashes are verified. Seven controller/network cases and nine compiled spawn cases pass. All eleven full-release gates remain unqualified.
[The receipt](evidence/controller-network/qualification-summary.json) and [executed run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40278694435) retain the exact result.

## Dev56 source-bound qualification

1,234 service tests, 95 overlapping fault tests and 241 portable tests pass with zero failures/errors/skips. All fourteen core jobs and five ancillary workflows pass. The paired IDE passes 282 tests with one Windows-only skip. Nineteen server archives plus one IDE archive, source inventories and wheel contents are verified. All eleven full-release gates remain unqualified. See [the exact receipt](evidence/controller-liveness/qualification-summary.json) and [executed workflow](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40283981575).
