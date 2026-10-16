# Wait progress intervals

LRM pages 58-59 describe periodic messages with remaining time, and a list of
intervals that becomes more frequent near the target. Example 83 omits a comma
between the Interval and Message arguments; the executable fixture supplies it.

The diagnostic uses real native clocks and IPC. Simple intervals wait 3.4
seconds with one-second updates. Complex intervals wait six seconds with
`[3, 1, .4]` updates, so the same transition pattern runs within seconds.
Native hour/minute units and literal TIME arithmetic have separate controls.
Boundary cases finish before the first interval. Failure cases omit the
required message; recovery cases perform a valid wait after that rejection.

The controller retains every progress message and countdown, measures message
gaps with an independent monotonic clock, checks the original target, and
requires successful native completion. The scheduler's 200 ms sampling period
is included in the timing bounds; early messages and missing rate transitions
are rejected. No clock, scheduler, registry or native execution is replaced.

This is an unrun diagnostic preparation. It qualifies no inventory row yet.
Full telemetry WaitFor/modifier behavior remains separate.
