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

This is an isolated implementation candidate. The SPELL proxy, ground release
scheduling, group/block protocol, RPC deadlines, command confirmation, native
capture, and composed package qualification remain incomplete. No language
coverage or release acceptance is promoted by this change. Shared transport
frames with timetags currently require further per-element implementation.
