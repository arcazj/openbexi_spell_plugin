# Proposed full limit profile

This candidate extends the GENERIC ground database with up to 16 named
definitions per parameter. It is not a qualification or release claim. The
original language inventory and the native baseline remain unchanged.

The original protobuf schema lacks enable-alarm and load-file methods. This
profile carries those operations and multi-definition updates in the existing
SetLimits Any value, explicitly identified as OPENBEXI_LIMITS_1. Legacy requests
with four thresholds remain supported. No new RPC method is presented as an
original SPELL method. GetLimits uses the existing configuration Any to select
the versioned profile. The Python helper must still exercise original SPELL
failure policy and notifications.

Each modification is validated before an effect intent and again in one SQLite
ground transaction. Receipted duplicate requests return their original receipt.
Metadata and exact Unicode status values survive round trips. State is scoped
to a DSS epoch. The original flat GENERIC threshold record remains a compatible
projection; named definitions are authoritative for the advanced profile.

Active selects definitions whose Active flag is true and whose optional
Algorithm evaluates to true. Algorithms are bounded read-only expressions over
catalogued telemetry. They allow arithmetic, comparisons and Boolean operators;
calls, indexing and dynamic attribute access are excluded. Invalid or stale
telemetry cannot silently activate a definition. An empty algorithm is
unconditional.

Hysteresis N raises an alarm after max(1, N) consecutive violating observations.
A sample is identified by its timestamp and engineering value; reading it again
does not increment the count. A nominal/ignored observation resets the count.
STEP uses independent downward/upward deltas; SPIKE uses an absolute delta. The
first observation establishes a baseline. Disabled alarms reset observation
history; enabling resumes evaluation. Unlisted STATUS values raise an alarm.
These profile choices require native positive, boundary, failure and recovery
evidence before any corresponding requirement can be qualified.

Registered limits:// files are bounded JSON package resources. A load validates
all parameters before changing any, then persists the actual file SHA-256 with
the definitions. The normal file is a GENERIC simulator fixture, not a vendor
ground-system file. RestoreNormalLimits returns to the profile's empty initial
limit database without removing injected telemetry.

The source has defects beyond its driver subset: EnableAlarm and DisableAlarm
only display an unimplemented warning and return True; AdjustLimits passes an
unsupported positional configuration; status conversion removes punctuation;
STEP validation compares values with type objects. The candidate must replace
these paths and demonstrate effects rather than accepting their return values.

The Language Reference section 4.8.7 says SetLimits in prose, while examples 103
and 104 and the source API use AdjustLimits. The candidate follows AdjustLimits.
The descriptive LoHigh spelling is treated as a reference typo; LoYel is the
documented modifier and source symbol. Both discrepancies remain recorded in
the original inventory, with explicit compatibility evidence required.

Focused backend validation: 37 definition tests and 39 expression/RPC tests
passed. The first expression run preserved one incorrect test expectation about
parentheses; it was corrected to test actual nested Boolean operators. A
standalone test import failure was corrected by making its local source path
explicit. The retained JUnit files are under .qualification; these results do
not substitute for the pending native suite and independent evidence review.
