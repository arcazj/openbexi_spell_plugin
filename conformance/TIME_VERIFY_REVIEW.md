# Native TIME precision and verifier failure correction

This checkpoint fixes two defects found by independent review of `e365053`.
It does not accept v0.5/v0.6 or allocate additional language clauses.
`evidence/time_verify_review.json` binds the original counterexample, exact
source manifests, runtime image, focused assertions and complete regression
reports. The original reports and images remain unchanged.

## Native TIME conversion

The previous native helper converted `TIME.abs()`/`rel()` through `double` and
combined the rounded seconds with the original microsecond field. At sufficiently
large dates or durations, rounding can cross a whole second. The negative-time
floor correction could also subtract a second after rounding had already reached
the floor. Repeated native conversions compounded the error: the retained probe
changed `1200-01-01 00:00:00.000001` by minus two seconds and a year 3000 value and
200000-day duration by plus two seconds during assignment/read.

`dta_time_patches.py` retains the complete original and ported preimage checks.
The helper now takes one value snapshot and constructs seconds from integer
datetime/timedelta fields, with checked Python integer conversion to the existing
native `long` representation. Fractional fields come from that same snapshot.
UTC formatting also pads years to four digits so the original TIME parser can
read dates before year 1000. The native unsigned-seconds storage ABI is unchanged;
this checkpoint is limited to the supported Linux x86_64 diagnostic runtime.

Actual native tests cover repeated assignment/read, large positive and negative
fractions, years 1 and 9999, maximum positive timedelta, precise ITEM notifications,
invalid assignment, real correction prompts and recovery. Native arithmetic
operators outside this conversion remain separately scoped.

## Verify failures

The original verifier caught only `DriverException`. Numeric/string ordering,
`IgnoreCase` with a numeric comparison target, and a huge integer passed to float
tolerance arithmetic could raise an uncaught worker exception. The procedure then
received an ordinary false result even with `PromptFailure=True` and
`HandleError=False`. The existing controller correctly detected those thread
errors, so the retained counterexample is explicitly failed evidence.

`obs_patches.py` preserves original preimages and now records unexpected worker
exceptions as `DriverException` failures. The original failure policy then decides
whether to raise, suppress or prompt. Mixed-type equality returns False;
inequality returns True. Huge integer comparisons use exact rational arithmetic
only when conversion to float would overflow, preserving the existing inclusive
floating boundary behavior for ordinary values. Nonfinite/negative floating
tolerances reject, and nonfinite comparison values cannot spuriously match a
different finite value.

The actual DSS/native checks include all ordering operators, huge integer
equality/inequality, mixed-type equality, invalid tolerances, explicit failure
suppression, a real `OnFailure=CANCEL` prompt distinct from `OnFalse=SKIP`, and
successful later verification. No verifier or driver response is replaced.

## Qualification and affected rows

Image `sha256:7a44b32c4996387592fe38f29c85f39c3575e77fda78255f0fde7a9517332354`
passes TIME 168, DTA 68 and OBS 189 checks, 425 total. It preserves the original
`3434d53d` runtime as its parent, with separately compiled and relinked native
artifacts plus a checked OBS overlay. Original/ported/patched sources and compile
artifacts are retained under `/opt/dta-native-patch`; old and new OBS recipes and
sources are retained under `/opt/obs-review-baseline` and
`/opt/obs-conformance-patch`.

The counterexamples directly challenged these previously qualified IDs:

- `CMP-LRM244-TYPE-DATA-CONTAINER-DATETIME`
- `CMP-LRM244-TYPE-DATA-CONTAINER-RELTIME`
- `CMP-LRM244-OPERATOR-VERIFY-EQ`
- `CMP-LRM244-OPERATOR-VERIFY-LT`
- `CMP-LRM244-MODIFIER-IGNORECASE`

The dependent sections are `CMP-LRM244-SECTION-4-3-1-031` and
`CMP-LRM244-SECTION-4-3-8-038`. Existing clause-bearing tests now include these
boundaries and failure paths; additional focused checks allocate no new rows.
Coverage is not changed by this isolated checkpoint. The final composed wheel
must include these corrected source hashes and pass installed RECORD and runtime
qualification before its evidence can replace the historical checkpoint.

The initial focused DTA run passed positive/boundary checks but stopped because
the new test expected the wrong error-prompt text. That failed run is retained;
only the expected text was corrected before the complete 68-check passing run.
