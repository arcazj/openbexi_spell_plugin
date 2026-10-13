# Full v0.5 inventory

The release remains open. `inventory.json` restores all 763 original LRM rows,
including their identities, page references and historical 195 ADAPTED / 79
PARTIAL / 489 GAP classifications. Its allocation source SHA-256 is
`694a7a5de3a72622f7ca6c6bec3b4326577f0b832821f00b27b007b48ab23573`.
These historical labels do not assert compatibility with the new native runtime.

`coverage.json` allocates every row to its original work package. Qualification
requires positive, boundary, failure and recovery reports bound to exact input
hashes and the native image. A report identifies its independent oracle and
actual contract. Missing rows, duplicate allocations, stale inputs, missing
dimensions and failing reports cannot pass the release gate.

```powershell
python conformance/check.py --output .qualification/v0.5/conformance-gate.json
```

Exit 1 means the release is still open; it is currently the expected result.
The first qualified package is TIME: 42 rows / 168 checks. All other 721 rows
remain open, including the seven pre-existing source errata. The specific TIME
evidence is retained in `evidence/time.json`; it qualifies the development image
identified there and does not qualify a new distributable native wheel.

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
These decisions do not resolve the seven unrelated original errata.

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

v0.6 depends on the full v0.5 release gate. Independent native rebuilds, packaged
upgrade/removal, all three actual IDE hosts and the DSS distribution image remain
required; the development overlays are not substitutes for that acceptance.
