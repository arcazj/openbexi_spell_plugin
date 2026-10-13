# Composed telemetry timing

This tranche qualifies only `CMP-LRM244-MODIFIER-WAIT`. Its four dimensions
are checked separately through GetTM, Verify, Send with verification, and the
original native WaitFor scheduler. The complete Delay and Timeout rows, full
Send/WaitFor functions, interrupted waits, scheduling and automatic limit
adjustment remain open.

## Manual and original source

The retained Language Reference 2.4.4 PDF describes fresh versus last recorded
telemetry on pp37/113, global and condition-specific verification modifiers on
pp40/44, composed Send/Verify on p54, Send's TC-to-TM Delay on p55, and WaitFor's
telemetry deadline versus acquisition Timeout on p57. A Delay in Send occurs
after confirmed command execution and before telemetry verification. WaitFor's
Delay bounds the condition wait; Timeout bounds acquiring an individual sample.

The original `Send_Helper` passes its whole configuration to `TM.verify` after
the TC phase. The strict driver consequently rejected command defaults during
TM verification, after the command had already executed. The checked correction
passes a copied configuration without the following TC-only settings:

| Key | Meaning and source |
| --- | --- |
| Confirm | Confirmation before command injection, pp50/108 |
| ConfirmCritical | Critical-command confirmation, pp50Ã¢â‚¬â€œ51 |
| Time | Absolute TC time tag, pp49/111; p111 also assigns Time to OpenDisplay, not TM acquisition |
| ReleaseTime | Ground release time, pp49Ã¢â‚¬â€œ50 |
| SendDelay | Ground command release delay, pp53/111 |
| Sequence | Original TC interface metadata for a GCS command sequence, p51 |
| Block | Command block injection, pp52/108 |

These fields have already reached the TC phase. Shared Wait, Timeout, Delay,
Tolerance and policies remain intact. Per-condition dictionaries are untouched:
a Time key placed inside a TM condition is still rejected by the strict TM
driver. No new scheduling, sequence, block, or critical-command capability is
claimed.

Original `SPELLscheduler::checkVerification` sets `InWaitFor=True` before calling
the original TM verifier. This suppresses the verifier's own operator-policy
loop while the scheduler manages the condition. The proxy now accepts that
internal Boolean metadata, validates its type, and sends only Wait, Timeout and
ValueFormat in RefreshItem. Direct telemetry calls still reject all TC-only
keys. No native C++ unit is changed.

## Independent observations

The native executor calls the original functions, helpers and scheduler. A real
loopback DSS and original-schema gRPC driver perform all acquisitions and
commands. Freshness checks stop periodic publication, publish one known initial
sample, and arm a real simulator STEP half a second after RefreshItem begins.
The returned TM.CORE.TICK must equal the new tick, the request must remain pending
until publication, and the binary RPC must contain that value. Recorded-value
checks run with publication stopped and read the existing tick.

Every relevant Send has exactly five ordered immutable stage receipts, each
delivered once. Missing fresh samples and false verification are followed by
explicit recovery calls; failure must not replay a command. Global/condition
overrides and caller dictionary preservation are asserted. Secondary Delay
checks are retained as bounded evidence, not full-row qualification.

## Retained baseline and open clauses

Raw evidence is retained beneath `.qualification/v0.5/timing`:

- `40ef592c94ce47f6af9bbe321046bd66`: seven failed initial probes. Four
  WaitFor cases rejected InWaitFor. Three Send cases rejected global Retries=0.
- `c8626db177f14c928678ffe80684daa8`: after narrowing Send probes by omitting
  global Retries, all three executed their TC but rejected TC-only TM settings.
- `2937a1e462484f56b27e16b0c98346c6`: the initial seven corrected probes passed.
- `39f6aba9ee6e45cbbbd1721d8f8a4b4a`: 24 expanded native probes passed.

A subsequent 36-check run, `6d77cc55ace54c8eb933a0ac3b4ade0e`, retained
32 passes and four failures from one uncertain command deadline. SendCommand
took 5.105 seconds against Timeout 2; only TRANSPORT and LOADING receipts exist,
the driver retained PENDING, and three later commands were correctly fenced.
All 16 core Wait assertions passed, but the run is not promotable. The complete
workspace, SQLite databases, source-input bytes and incident analysis are kept.
Concurrent native build/gate contention is a possible cause, not an established
root cause. A quiet unchanged-oracle rerun is required; no deadline or freshness
limit is relaxed.

The first Send failure is a remaining implementation limitation, not invalid
manual syntax: p54 allows Verify modifiers in composed Send, but the TC proxy
still rejects global Retries. This tranche does not close general modifier
composition. The final report additionally requires all four dimensions for
GetTM and Verify and stricter invalid-metadata/condition-override cases.

Prompt Timeout has a manual contradiction: p72 says that without Default the
client beeps and continues waiting; the p112 table says it fails without Default.
No interpretation is silently selected, and the complete Timeout row stays open.
The driver's bounded acquisition deadlines and freshness limits remain explicit
profile limits. Complete Delay validation and interrupted/resumed scheduler
behavior are outside this checkpoint.

## Reproduction and provenance

`run_timing.py --image IMAGE` retains the exact image ID, all source inputs,
native IPC, binary RPCs, original source manifests, DSS receipts and failures.
The diagnostic image derives from independently reproduced checkpoint 422 image
`49667cb1aae52c7293a48b2b092b3ace04d53ea55a1adc69bb9d05b16f64e7fd`, applies frozen
LIMIT 419b37a followed by `timing_patches.py`, and preserves every original and
patched preimage. `timing_provenance.py` checks the complete installed source and
native binary set against that declared chain. This overlay is not represented
as a fresh independently reproduced wheel or an accepted full plugin release.

The checked recipe touches only post-CMD `tchelper.py` and post-LIMIT proxy
`tm.py`. The later ValueType/Units recipe changes `tc_item.py` and proxy `tc.py`,
so its paths do not overlap. The current independently building integration
freeze excludes this later timing tranche.
