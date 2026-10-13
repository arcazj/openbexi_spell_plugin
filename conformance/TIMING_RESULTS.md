# Timing checkpoint results

The unchanged quiet rerun passed all 36 native checks on image
`sha256:b572950314bb1f3c0858957efa0e77360df9aaa5a6096419e423c2c8248f2305`.
Its retained raw report is
`.qualification/v0.5/timing/6c0cd37278ea413f86541d4b65bf2599/result.json`,
SHA-256 `caa5429da0539d7fb1464e81e338f0b208eeee07935adcdbff152d4beddecb80`.
The strict qualifier adds four dependency checks, one per dimension, covering
GetTM, Verify, Send verification and the native WaitFor scheduler. Only
`CMP-LRM244-MODIFIER-WAIT` is eligible for qualification; no central coverage
allocation is changed by this checkpoint.

The prior 32/36 run and its uncertain command deadline remain retained. The
rerun changes no image, command deadline, freshness limit, scenario, assertion
or fixture. Its only input difference is the historical account added to
`TIMING.md` before the retry. A passing retry does not establish the cause of
the earlier command deadline. The earlier run correctly retained the uncertain
effect and fenced three subsequent commands without replay.

`TIMING.md` is retained byte-for-byte as a tested input. Its statement that a
quiet rerun is required describes the state before this result. The two page
ranges in its table that contain encoding artifacts mean pages 50-51 for
ConfirmCritical and pages 49-50 for ReleaseTime.

The checked original source corrections are:

| Target | Original SHA-256 | Corrected SHA-256 |
| --- | --- | --- |
| spell/lang/helpers/tchelper.py | efa7ec315be2553050fcb82567d205f458bf6c7899726fbaab92ebb8f9d1ea3e | c40677470312d45aa2d28de92ab05aaa116e1d1d6644038dc94957bcbe6c8ec8 |
| openbexi_dss_proxy/tm.py | 21c8a9c0bf4927868cd320505d89a3315c03d4afee6d09c727f05982d8857ad6 | 0f1488c410ba03869926be34acd1cbdf4e3cbc597646af0e01487ecc8b7e1203 |

The diagnostic overlay preserves the independently reproduced base identity,
applies the frozen LIMIT recipe followed by this timing recipe, and audits the
complete installed source and native binary set. Original notices and source
preimages are retained. This checkpoint is separate from the frozen integrated
470-row candidate and does not claim an independent timing-wheel rebuild.

Global `Retries=0` in composed Send remains an observed defect: the manual
allows verification modifiers, but the TC proxy rejects it before transmission.
The complete Send, WaitFor, Delay and Timeout rows, automatic limits, scheduled
commands and interrupted waits remain open. Full v0.5 acceptance and the v0.6
dependency remain false.
