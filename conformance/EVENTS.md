# Native Event example and explicit RESEND

This bounded tranche qualifies two rows with eight native checks: Example 110
and the RESEND action constant. Each row has positive, boundary, failure and
recovery evidence. It uses original Event and Send helpers, actual native client
messages, durable event journal entries and real DSS binary command receipts.
No language function, registry or driver result is replaced. The runtime is the
unchanged CMD candidate `sha256:627f1b3a529e3581618dc739a4f0029c11e29f8ca654a58b284076f9214db708`.

LRM 2.4.4 p68 says Event injects messages into the GCS event subsystem and SPELL
clients. Example 110 on p69 demonstrates default INFORMATION, positional WARNING
and keyword ERROR. All three paths assert exact text, severity and default scope
in client IPC and the actual durable event service. A multiline UTF-8 message
at the 8192-character driver limit arrives intact. Missing/non-string arguments
fail through original syntax handling. Empty/oversize messages are rejected by
the real driver; a later valid event succeeds without restarting the executor.

`FUNCTION-EVENT` and `SECTION-4-10-083` remain open. The related Display definition
says it accepts any string, while this driver bounds events to 1..8192 characters.
Those rejection checks demonstrate a limit and do not qualify unrestricted Event
semantics. Actual desktop rendering is outside these native IPC/service checks.

LRM p28 defines RESEND as resending a command. Page116 explicitly makes this
backward-compatible action specific to Send command injection; page117 separates
operation failure from a normal False result. The suite causes genuine CMD1
RELEASE/FAILED receipts in simulator SAFE mode, then answers the original native
OnFailure prompt with RESEND. It verifies one failure followed by success, a
second failed resend before success, and a failed resend followed by CANCEL.
Every new attempt has a distinct operation ID and one ingress delivery, with
exact failed/successful stage sequences and command-execution count changes.

To permit recovery, the controller sends an actual SET_MODE command through the
original-schema driver using a separate valid authority. Its five receipts are
retained and distinguished from the native command attempts by execution ID.
Failure cancellation is followed by successful recovery in the same executor.
No command is automatically replayed and no uncertain result is treated as a
definitive failure. Whole-group RESUME and unrelated modifiers remain open.

The first retained exploratory run failed because its independent WARNING
expectation used 4 instead of the original constant 1, and its fixture repair
procedure ID violated the driver's 32-hex identity format. These were oracle and
fixture mistakes, not runtime defects. The corrected fixture associates the
separately generated valid ID with the corresponding immutable DSS receipts.
The failed raw run remains under `.qualification/v0.5/events/7114411d50c9423cbf78d89a1b14c56a`.

Run `python conformance/run_events.py --image <exact-image>` and pass its
`result.json` to `python conformance/events_report.py <result.json>`.
The report checks all required assertions, prompt answers, four dimensions and
source hashes. `conformance/evidence/events.json` retains the observations and
exact installed runtime hashes. Full v0.5 and dependent v0.6 acceptance remain
false; central coverage promotion belongs to the integration checkpoint.
