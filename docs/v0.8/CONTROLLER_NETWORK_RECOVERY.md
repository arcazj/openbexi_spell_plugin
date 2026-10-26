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

## Remaining liveness gap

The current stateless request protocol has explicit `session.close` and rebind,
but no controller heartbeat or persistent connection-loss notification. An abrupt
client death or partition **before** an explicit close does not automatically
change its logical session to `CONTROLLER_DISCONNECTED`. The blackhole case
records `automatic_disconnect_detection: false` and observes `OWNED`; it does not
mislabel the unreachable client as a detected disconnect.

Closing this gap requires authenticated session liveness, a bounded detection
policy and durable fencing serialized with existing execution admission. Missing
liveness must never promote an observer, release reservations, kill a native
family or claim quiescence. Reconnect must still create a new generation and
require the existing host barrier. Tests must include killed clients, one-way
partitions, delayed heartbeats, old-generation traffic, Context restart and
unaffected observers with actual native families. This remains a services and
recovery release blocker.

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
