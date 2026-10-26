# Native admission transport checkpoint

Development package **0.8.0.dev50** is undergoing qualification. All eleven
full-release gates remain false.

The dev49 evidence-only follow-up at `5bde4fd` failed one of thirteen core jobs:
native-prompts did not reach child-running. Two workers reported member binding
followed by BrokenPipeError sending the native acknowledgement. Their native
startup traces reached binding-requested but not member-bound. The failure's
cause is **not established**. [Verified failed receipt](evidence/native-admission-channel/dev49-followup-failure.json).

Inspection found a separate reproducible defect: the native admission code
treated `poll` interrupted by a signal as a permanent channel failure. A compiled
regression using the original wait behavior and real SIGUSR1 delivery aborted
after 10 ms. Both readiness and deadline cases failed before the correction and
pass afterwards. This reproducer does not establish which event closed the two
historical native peers.

The corrected transport resumes interrupted waits and transient send/receive
operations on the same descriptor and original byte offset. The single original
four-second deadline remains in force. There is no reconnect, packet replay,
fresh grant, deadline extension or retry after an uncertain callback. Exact
SO_PEERCRED checks, bounded requests and exact ALLOW replies remain mandatory.
Lost replies, denial, peer mismatch and deadline expiry continue to fail closed.

The transport is isolated in `admission_channel.H` so compiled tests exercise
production code without a JSON fixture. Hosted Linux tests additionally exercise
real Unix sockets and credentials, partial I/O, injected EINTR/EAGAIN, lost and
denied replies, and signal storms across the original deadline. Local Unix socket
creation is denied by the execution environment; those mandatory tests remain
enabled for hosted qualification.

Native failure records contain only fixed reason/stage labels and numeric
PID/timing/errno/interruption metadata. The worker records callback phase and
elapsed/dispatch time. No packet, path, argument, reply or capability is logged.
Diagnostic parsing rejects extra fields and unexpected values; diagnostics do
not grant admission or authorize a retry.

Native, installed IDE, prompt/handoff, startup stress, terminal, deployment and
package requalification must complete on the exact new sources before this
checkpoint can be called a passing component result. Historical startup causes,
full compatibility, driver faults, public launch/debugger/browser, complete
deployed recovery/security and stable publication remain open.
