# Bounded ranging qualification

The native procedure calls the original SPELL 2.6.10 helpers, migrated to CPython
3.13, and the original adapter interfaces. The real binary gRPC proxy reaches the
persistent GENERIC ground service. This is the declared DSS ranging profile; it
does not operate an RF antenna or substitute sequential operations for dual ranging.

LRM 2.4.4 pages 93–95 distinguish schedule enable/disable from on-demand ranging.
Example 169 explicitly takes no antenna/baseband arguments. Example 170 supplies
one mandatory baseband/antenna pair. Example 172 aborts activities; page 95 also
requires calibration to be affected by AbortRanging. Example 174 returns known
names as lists. Example 175 specifies a single calibration pair.

Each operation is checked against independent SQL reads of the persisted ground
state and effect journal, captured original-schema RPC requests/responses, exact
receipt counts, and native failure-policy prompts. Catalog reads must create no
effects. Syntax errors must perform no RPC. Invalid paths/configuration must not
create an effect intent. Explicit REPEAT must produce exactly the requested new
attempt; CANCEL must not replay an effect. Recovery is a subsequent explicit call.

The original calibration helper calls startRangingCalibration, but the original
adapter interface and concrete proxy expose startCalibration. Enable/Disable
pre-operation hooks accept any positional arguments, contrary to page 93. A
candidate recipe corrects these demonstrated defects. The wrapper removes a
trailing modifier dictionary before arity validation, preserving that syntax.

The first baseline also exposed default AllowInterrupt=False serialized to the
strict ranging service as an unsupported option. The RNG proxy now validates
this helper-owned flag as an exact bool and removes only that field before
serialization. Unknown operational modifiers remain errors. The 36-case suite
tests both boolean values and malformed values, including zero-effect rejection
before any RPC. It exercises positional modifier dictionaries, config=, and
individual keyword modifiers. A preserved expanded baseline uses the same oracle.

Dual ranging (Example 171), all baseband configuration forms and ENG/RAW handling
(Example 173), GetRangingStatus constants (Example 176), and whole containing
sections remain open. In particular, persisted DSS READY/DISABLED strings are
observations of this simulator's state, not claimed implementations of the
manual's IDLE/RANGING/CALIBRATING/ERROR return constants. Whole StartRanging and
AbortRanging functions remain open for multi-path semantics. Calibration list
forms accepted by original helper syntax are outside the single-pair manual case.
This report cannot establish full v0.5 or v0.6 acceptance.
