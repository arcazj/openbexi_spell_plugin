# Full v0.5 inventory

All **763 original LRM requirements are qualified; none remain open**.
`inventory.json` preserves every original identity, page reference and historical
classification. `coverage.json` binds each requirement to independent positive,
boundary, failure and recovery evidence. Historical labels alone do not qualify
behavior.

The [acceptance record](../docs/V05_CONFORMANCE_QUALIFICATION.json) binds all
61 native suites (2,157 raw checks) to one installed runtime. Missing rows,
changed inputs, incomplete dimensions or failing dependencies reject acceptance.

```powershell
python conformance/check.py --output .qualification/v0.5/conformance-gate.json
```

The accepted v0.5 gate exits 0. Final distribution and installed host workflows
remain v0.6 work, with the declared GENERIC simulator and platform boundaries.

| Package | Qualified / inventory |
| --- | --- |
| CMD | 66 / 66 |
| COMMON | 66 / 66 |
| DATA | 94 / 94 |
| FILES | 45 / 45 |
| FLOW | 51 / 51 |
| LIMIT | 70 / 70 |
| OBS | 104 / 104 |
| PY | 122 / 122 |
| SPECIAL | 43 / 43 |
| TIME | 42 / 42 |
| UI | 60 / 60 |

Manual/source decisions remain in their family reports, including
[page-79 SCDB scope](DATABASE_SCOPE.md), database input octal, native legacy
comparison spelling and special-service extension contracts. The
[historical qualification](../distribution/evidence/pre-v05-qualification.json)
retains its original 470-row evidence and limitations.

## Reproduce the TIME milestone

```powershell
python conformance/build_time_patch.py
docker build --network=none -f conformance/native.Dockerfile -t openbexi-spell-host:v05-time .
python conformance/run_native.py --image openbexi-spell-host:v05-time
```

The patch checks the exact 2.6.10 source preimage. The accepted host 0.3.0 image
and wheel are preserved. The development image includes the original file,
patched file, patch recipe and hashes alongside the inherited source/notices.
The original native executor imports the oracle module from a small procedure;
oracle function objects are not procedure checkpoint state. Original language
methods and native registry/factory/executor are used except for the declared
TIME patch. Only the example driver's clock input is controlled.

The baseline exposed signed fractional-second parsing, optional relative-second
parsing, host-timezone/fraction loss in `abs()`, and reversed reflected
subtraction. The suite uses literals and Python datetime expectations, a leap
day and year rollover, controlled clock failure/recovery, a non-UTC host
timezone, invalid grammar/arithmetic, negative fractions, and output-format
restoration. Floating seconds use an absolute tolerance of 1e-12 seconds,
below the runtime's microsecond precision.

## TIME manual/source decisions

LRM 2.4.4 p.33 requires UTC. Example 29 on p.35 gives epoch 1144002754 for
`2006/04/02 20:32:34`; the independent UTC value is 1144009954. The normative UTC
rule wins. Original `time.mktime()` depended on the host timezone and discarded
fractions; the patch uses UTC epoch conversion and preserves microseconds.

Page 34 defines the default output as `dd-mmm-yyyy hh:mm:ss`. Example 29's slash
output requires an explicit `TIME.fmt()` setting; it is not a second default.
Tests preserve the page-34 default and exercise every listed format specifier.
The COMMON milestone separately resolves its two original errata.

Relative input follows the documented signed-seconds and signed day/time grammar,
including omitted seconds. Expression evaluation inside a time component is not
part of that grammar. Existing absolute formats and numeric relative inputs stay
available. Reflected subtraction now follows Python operand order.

## Other completed prerequisite

Original TIME has `rel()` and does not implement `__float__`. The DSS proxy now
uses `rel()` for TM/TC timeouts and rejects absolute, nonfinite, nonpositive,
oversized and boolean values before sending an RPC. The separate native driver
acceptance test uses original models and actual binary DSS receipts across two
fresh runs. This closes that defect, not the full cross-family Timeout modifier.

The full v0.5 gate now passes. Its frozen composition also passes
two independent offline native builds, identical complete wheel bytes, eight
fresh-install/removal checks per build, and installed host/DSS image provenance.
Versioned upgrades, final host workflows and production packaging
remain required for v0.6 acceptance. See [distribution progress](../docs/V06_PROGRESS.md).
