# Onboard execution scheduling candidate

LRM 2.4.4 section 4.5.2 distinguishes an onboard execution time from a ground
release time. The GENERIC simulator now accepts `execution_time_unix_ns` on
individual binary TC packets. The absolute time is bound to the command's
persisted definition; changing or dropping it on a later stage is rejected.

TRANSPORT and LOADING retain their existing behavior. RELEASE accepts a future
timetag and records ACKNOWLEDGEMENT without executing the command. The simulator
executes it at the first model tick at or after the target, independently of the
driver process. Pending schedules survive restart. Execution occurs between
ticks, so subsequent dynamics use the resulting spacecraft state. Pausing the
simulation pauses scheduled execution. A past or current timetag executes at
release. The horizon is one simulated day and the queue holds 64 commands.

An early execution query reports PENDING. Its receipt remains an immutable
observation; a new observation requires a new operation identity. Execution
failures are terminal and do not replay. Resetting a scenario with queued
commands requires the existing explicit test-case retirement mechanism, which
retains those queued commands in its evidence.

The focused packet/engine tests cover due-time boundaries, loaded-only behavior,
restart, duplicate receipts, invalid and changed times, queue capacity, failure,
clock pause/resume, and effects on later dynamics. Existing DSS engine and
transport regressions also passed.

The isolated `command_execution` driver module now exercises individual commands
over real DSS binary TCP. It distinguishes a ground hold (no TC frame before
ReleaseTime/SendDelay) from onboard Time (TRANSPORT, LOADING, RELEASE and
ACKNOWLEDGEMENT before execution). LoadOnly finishes after two actual stage
receipts. The driver reconnects between stages without replaying a stage, keeps
checking live authority, and preserves uncertain outcomes after any write.
Additional information reaches the binary packets and persisted command
definition. Deadline calculations use integer simulation nanoseconds; SendDelay
extends the verification window. A one-minute Timeout is accepted by this module.

The combined 120 tests cover these paths, the onboard engine, and existing DSS
engine/transport behavior. An initial delay test used an 80-millisecond total
verification budget, which expired after two real network stages. Its database,
sources and failing report are retained. The corrected test waits longer than
Timeout alone and then verifies completion within SendDelay+Timeout, with enough
time for the real network exchanges. Production deadline logic was preserved.

The original SPELL proxy and dispatcher now carry individual scheduling,
LoadOnly, one-minute timeouts and metadata. Seventy-one focused tests and thirty
original native cases passed. Native capture exposed the original SendDelay=None
default; its complete counterexample is retained and the corrected adapter was
replayed. The native LoadOnly notification reports LOADING/SUCCESS, and native
metadata arrives unchanged in actual binary frames. The outer RPC envelope
permits scheduled waits; a real 36-second relay test passed.

Group/block transport, sequence expansion, critical confirmation, strict evidence
qualification and fresh composed package acceptance remain incomplete. No language
coverage or release acceptance is promoted by this change. Shared transport
frames with timetags currently require further per-element implementation.
