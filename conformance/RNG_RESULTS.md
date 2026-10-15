# Ranging helper and catalog checkpoint

The isolated candidate passes all 36 native observations. Only three inventory
rows qualify: GetBasebandNames, GetAntennaNames, and Example 174. All schedule
and activity clauses remain open. No central coverage or release version changes
are part of this donor.

The checked recipe fixes two original helper defects: Enable/Disable now reject
unexpected positional names, after the original wrapper consumes a trailing
modifier dictionary; calibration calls the existing adapter startCalibration
method. The RNG-only proxy validates AllowInterrupt as an exact bool and omits
this helper-owned flag from ground options. Every other option retains its strict
driver validation. Original notices, exact preimages, patched sources, recipe and
the independently rebuilt native composition are retained in the image.

| Source | Original SHA-256 | Candidate SHA-256 |
| --- | --- | --- |
| spell/lang/helpers/rnghelper.py | 8a892776f286c2cc3230d45bebd871da39dca3e4d67ee4af1093afd1b1c09a61 | 12a95ccbf1bdd3857a6d6e8bced9222af0fc6d67318e4c3412546d166b20bd18 |
| openbexi_dss_proxy/ranging.py | 7c962da4fae3a08d5b13d7a7ab72573b3061196c8be1d123258ded6aece1937a | c8586f47b47dbaa5f1d3fb411a33c8f2f4746bdaa0276fa80de61e004b716388 |

The base image is
`sha256:1fef3e691d8590079898a01cb7bddad9dbce8d9b4c4c29046a790e16af2a3342`.
The candidate is
`sha256:ae9c39c8de3c59f5ab611f11143f79c834addc2b93a9dea25fd2efa11a6aed75`.
Native binary identities are unchanged. This diagnostic overlay supersedes two
installed RECORD entries; fresh wheel composition remains a separate gate.

The local retained evidence is under `.qualification/v0.5/rng/` in this worktree:

| Run | Result | Raw result SHA-256 |
| --- | --- | --- |
| d70dfc81bfc543c9a440b2d0d02b1eca | Initial baseline: 6/32 pass | 55a5c2da5960e33d6bce23331bee87635138ea06ef80c378e9f9664f52389da1 |
| 7fec8c89a3824b278f48a07a80731635 | Expanded baseline: 6/36 pass | 661f83e534acb4707529db8ff8699d20b1815d6cc7b8ee2d45cfe3351fc2c3b9 |
| ba77da5b49d341d39d5d0be07cbffdd9 | Candidate: 36/36 pass, FINISHED | e011ca000ff83eae44acbc43e07228a0fb56f8853381944c507c1bb61646c7b9 |

All run inputs, native logs, exact original-schema RPC traffic, prompt fields,
and actual SQLite journals are preserved. Expanded baseline/candidate oracle
code is identical. The baseline records the missing calibration method and the
default AllowInterrupt option reaching and being rejected by the real driver.
The candidate records 85 ranging RPCs, including 60 successful responses and 25
expected driver rejections. The final journal has 52 RECEIPTED effects and no
pending effects; lifecycle event receipts are included in that total. Per-case
assertions independently check ranging receipts, request IDs/digests, boolean
payloads, baseband/antenna arguments, persisted state and unchanged configuration.
The real native CANCEL/REPEAT prompts select CANCEL, then REPEAT/CANCEL, and a
calibration CANCEL. Explicit REPEAT makes exactly two failed attempts in total,
without producing any effect intent or implicit replay. Six malformed
AllowInterrupt values produce no RPC or effects.

The repository suite also passes: 224 tests, followed by six focused recorder
checks that reject failed, incomplete or misassociated evidence and prevent
activity observations from qualifying the open clauses. The bounded native procedure imports
an independent oracle that calls original helpers; it does not qualify generic
warm-start or checkpoint recovery.

## Manual conflict retained open

LRM p93 distinguishes the periodic ranging plan/schedule controlled by
EnableRanging/DisableRanging from on-demand StartRanging/AbortRanging. The current
GENERIC Ground implementation stores just one `ranging` value: enabling resets
an activity to READY, disabling changes it to DISABLED, and on-demand start while
disabled returns False. The baseline/candidate boundary cases record that
existing profile behavior. They do **not** prove the manual's independent
schedule/activity semantics. This qualification correction takes precedence over
any provisional activity-row associations in the raw cases or design notes.

The original RngInterface preserves separate methods for these operations; its
unimplemented fallbacks do not authorize their state conflation. The empty
driver rejects operations. The Driver Development Manual pp6–7 requires mapping
generic services to concrete GCS services and contains no ranging-specific
override of LRM p93. The qualifier therefore removes all activity/schedule
contract claims from the canonical report while preserving the observations.

The next independent tranche must test enable/disable during active ranging and
calibration, Abort without changing schedule, and on-demand start while periodic
ranging is disabled. It must preserve stored-state migration, explicit simulator
boundaries, real receipts and unresolved-effect fencing. Dual paths, hardware RF,
baseband list/ENG/RAW configuration, and GetRangingStatus constant mapping also
remain open. Full v0.5/v0.6 acceptance remains false.

Reproduce this bounded checkpoint using the exact candidate image:

```powershell
python conformance/run_rng.py --image sha256:ae9c39c8de3c59f5ab611f11143f79c834addc2b93a9dea25fd2efa11a6aed75
python conformance/rng_report.py <candidate-result.json> --baseline <expanded-baseline-result.json>
```
