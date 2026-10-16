# Wait progress intervals

LRM pages 58-59 describe periodic messages with remaining time, and a list of
intervals that becomes more frequent near the target. Example 83 omits a comma
between the Interval and Message arguments; the executable fixture supplies it.

The diagnostic uses real native clocks and IPC. Simple intervals wait eight
seconds with two-second updates. Complex intervals wait thirty seconds with
`[15, 5, 1]` updates, so the same transition pattern runs within seconds.
Native hour/minute units and literal TIME arithmetic have separate controls.
Boundary cases finish before the first interval. Failure cases omit the
required message; recovery cases perform a valid wait after that rejection.

The controller retains every progress message and countdown, measures message
gaps with an independent monotonic clock, checks the original target, and
requires successful native completion. The scheduler's 200 ms sampling period
and acknowledged IPC are included in a 600 ms per-gap timing bound; early
messages and missing rate transitions
are rejected. No clock, scheduler, registry or native execution is replaced.

The retained first run, `8b3e93b53928447f8c9eb024599a94ff`, rejected the initial
3.4-second fixture because only two updates arrived, at 1.394 and 2.556 seconds.
Its countdowns and native message timestamps show the timer also spends time
waiting for IPC acknowledgements; the original source records the next interval
after sending the preceding message. The initial fixture assumed three updates
without allowing for that overhead. The revised fixtures retain real clocks,
require three scalar updates and all three staged rates, and leave more time
for repeated updates in the shortest phase. They still need a complete passing
native run; no requirement is qualified by this timing analysis.

This diagnostic qualifies no inventory row yet.
Full telemetry WaitFor/modifier behavior remains separate.
