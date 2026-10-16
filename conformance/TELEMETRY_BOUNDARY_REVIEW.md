# Telemetry diagnostic corrections

The first telemetry feature run retained a fixture failure when one case reset
its DSS scenario twice using the same scenario identifier. The DSS correctly
rejects reused identities. The corrected controller includes each fixture
request's unique token in the new scenario identifier. This changes fixture
setup, not the DSS reset contract.

The first list-comparison baseline assumed that `nbw` excludes exact endpoints
with the default configuration. That expectation conflicts with the original
SPELL 2.6.10 `TmInterface.__c_nbtw` implementation. With `Strict=False`, `bw`
includes both endpoints and `nbw` includes values equal to either outer endpoint.
With `Strict=True`, both operators exclude equality at their respective
boundaries. These operators therefore overlap at endpoints in non-strict mode;
they are not Boolean complements there.

Language Reference 2.4.4 page 39 names the ternary operators without specifying
endpoint inclusivity. This profile preserves the original source behavior and
tests both explicit Strict settings. It does not change the comparison
implementation to match an assumed complement rule. The original failed
expectation remains retained as an oracle correction, not a product defect.

The corrected four-comparison case then exposed a separate fixture lifetime
problem: the initial sample exceeded the five-second freshness threshold before
the third comparison. Its original RPC response correctly marked the parameter
invalid. The case now enables the real DSS periodic feed before comparing the
four endpoints. The dedicated freshness cases retain their stopped-feed setup;
the production freshness threshold is unchanged.

The one-minute acquisition baseline is a separate product limitation: the old
driver rejects durations above 30 seconds. Its replacement must still complete
a real acquisition delayed beyond that limit through the original RPC path.
