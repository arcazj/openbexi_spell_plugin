# Paired IDE controls for existing native executions

The development Listener accepts `POST /v1/contexts/{id}/commands` only when
that Context is explicitly listed in `native_command_contexts`. The list is
empty by default. Gateway certificate identity, Listener Context scope and
Context role/owner proof remain independently enforced. Worker provisioning,
host attestation and prompt reply routes are not exposed by this change.

Health advertises only the configured commands allowed by the caller's live
permissions: RUN/STEP require start and control; PAUSE requires control;
ABORT/CLOSE additionally require the terminal profile. The Listener clears this
list for disabled Contexts. Public `runtime_enabled` stays false.

The paired IDE client and panel use the originally delivered capability, epoch
and connection generation. They never derive a command proof from monitoring
data or retry an ambiguous transport response. B can explicitly reconnect after
accepted family transfer and request RUN while paused. A's original identity
remains fenced. The local Run/Debug fallback stays disabled in connected mode.

Local development verification: 230 selected server, live-handoff, terminal,
owner-command and real three-hop TLS checks passed; 37 IDE client/Qt checks
passed. Local Python is 3.12, so these are regressions rather than CPython 3.13
release evidence. Hosted foundation qualification uses CPython 3.13 and installs
the exact IDE pair from IDE_PAIR.json.

`qualify_v08_native_launch.py --native-ide` adds separate Listener/gateway
processes and three installed certificate-authenticated clients to the actual
native handoff fixture. Reservations, observation, claims, acceptance, rebind
and owner commands traverse those services. Only initial worker provisioning
remains on the independent trusted host path. The native source, cgroup freeze,
original process identity, cross-owner DSS receipts and terminal settlement
oracles are preserved. Its executed outcome must be retained before this
component is called qualified.

This does not qualify public launch, full debugger inspection/breakpoints,
browser/WSS/Git, repeated handoff or deployed recovery. Full release gates
remain unchanged. Historical failures and receipts retain their original scope.
