# Live procedure and service reconnection

The native CIF now owns a reconnect worker. An IPC input callback records the
connection failure and returns; the owner then replaces the failed channel.
Shutdown cancels an incomplete connection and joins the worker before releasing
its dependencies. Numeric TCP connection, key exchange and input readiness have
deadlines, and disconnect interrupts both key-exchange stages.

A replacement context attaches to the surviving process once and waits for that
attachment before querying its status. It starts without a controlling GUI client
and uses the original no-client acknowledgement path. The previous constructor
marked this state connected with a null client, silently dropping the PAUSED
acknowledgement and preventing the Python body from resuming. A native stack
capture established the blocked acknowledgement wait; the repaired path allows
the original process to resume after a new GUI explicitly takes control.

Acknowledgement waits are tied to a connection generation. A notification skipped
during a disconnect is retried after login instead of waiting for an unsent
message. Socket creation and accept use atomic close-on-exec flags. The native
time arithmetic also preserves fractional seconds, including carry and borrow;
the previous addition could shorten a one-second scheduler wait.

## Qualification

[NATIVE_LIVE_RECONNECT_QUALIFICATION.json](NATIVE_LIVE_RECONNECT_QUALIFICATION.json)
records Build 49, with exact source and artifact hashes. All preceding native,
standalone recovery, service-binding and ownership gates pass. Nine context tests
cover 21 complete lifecycle runs. The ordinary procedure receives an explicit
Close command before context shutdown; services use the context's existing
graceful service-close path. Upstream context shutdown deliberately calls
`killAll()` for any ordinary procedures still open.

The fixture verifies the native executable, parent and owned process group before
killing only its context. The original listener starts a replacement. The test
requires the same child PID, a single body-start record, stable progress while
paused, successful control reattachment and resumed progress. Final acceptance
also verifies Python `finally`, normal exit and reaping of the adopted child.
Private test process groups and child-specific reaping leave user services alone.

The [subsequent Build 52 gate](NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json)
tightens test clients to acknowledge only synchronous notifications and repeats
each live reconnect case three times. It exposed a shutdown race: automatic
pause requests could follow Close, and a late pause could erase the close wakeup.
The context now marks closure before removing its client and stops issuing
automatic pauses. The controller publishes terminal flags atomically and checks
them again while arming its wait. All 25 lifecycle runs pass; procedure Close
must finish within four seconds, run `finally` and exit normally. A successful
Close response alone cannot pass, since upstream can also respond after force-kill.

Additional checks cover eight fractional-time cases and cancellation before each
of the two handshake key bytes. Targeted runs cannot pass the release recorder;
the complete suite and every preceding native gate must pass with matching inputs.

## Scope

Reconnection preserves a live process; it is distinct from procedure checkpoint
recovery and service watchdog cold restart. See
[service recovery semantics](SERVICE_RECOVERY_SEMANTICS.md). Hostname resolution
still uses the system resolver; its cancellation is not qualified. The evidence
uses Linux x86_64 and GIL-enabled CPython 3.13.15 with ASan/UBSan, with leak and
thread sanitizer qualification separate. v0.2 acceptance and later releases remain
open until their own gates pass.
