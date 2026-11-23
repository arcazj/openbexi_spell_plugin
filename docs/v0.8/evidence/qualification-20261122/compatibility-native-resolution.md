# Native compatibility results

**332 of 763 inherited requirements passed across the tested product revisions.** A positive-dimension check failed for 27 requirements. The other 404 still need an original acceptance observation. The 47e0cb37 SPELL worker with the fadac70d IDE directly verified 159 of the 332. [All 763 verdicts](compatibility-final-outcomes.json) · [Current native rollup](compatibility-final-rollup.json)

| Product and scope | Observed results | Newly covered requirements |
| --- | --- | ---: |
| c7292d39 language suites and 99686362 with the corrected native session | 724 time, Python, data, files, common and typed-data checks. Another 88 original checks passed against the isolated GENERIC simulation. | 253 |
| 655f5b5a additional observation, common behavior and user interface | 72 observation checks and 40 common checks passed. Of 56 embedded UI checks, 48 met the independent prompt oracle. | 59 |
| 655f5b5a user dictionaries | Twelve isolated native runs passed all four original dimensions of regular-file load, formats and revert. | 6 |
| 47e0cb37 dictionary load | Four new native runs reproduced the complete 655f5b5a result bytes for the two load requirements. | 0 |
| 47e0cb37 Python | All 488 recorded assertion results matched the original report, including source, expected behavior and child dependencies. The original checker verified 48 parent dimensions against 372 distinct child dimensions. | 12 |
| 47e0cb37 complete FILES chapter | All 36 original checks passed. The controller repaired two missing files, then chose REPEAT through the public IDE client. The native checks read the expected bytes and the original whole-chapter aggregate passed all four dimensions. | 2 |

The first three rows account for the frozen 318 requirements. The two 47e dictionary IDs were `CMP-LRM244-EXAMPLE-143` and `CMP-LRM244-SECTION-4-15-5-1-101`. The 47e Python run directly verified 105 previously covered requirements and 12 additional sections. The complete FILES run directly verified 38 previously covered IDs and closed `CMP-LRM244-SECTION-4-17-115` and `CMP-LRM244-SECTION-4-17-8-123`. [Frozen dictionary cases](compatibility-user-dictionary.json) · [47e dictionary capture manifest](compatibility-47e-continuity-captures.json) · [47e Python capture manifest](compatibility-47e-python-captures.json) · [47e FILES capture manifest](compatibility-47e-files-captures.json)

### Product and receipt comparison

Between the assigned workers `a545c961` and `489ff81a`, the installed Listener, Context, Executor, host IPC bridge and shared executor library had identical SHA-256 digests. The dictionary oracle and controller, Python cases and fixture, supported-check function and native session module also matched. The server and DSS wheel archives, worker agent, role images and launch/service sources differed. The 47e build added worker handoff and epoch modules. A separate state-volume reader matched each 47e Executor PID, start ticks and executable digest to its stored terminal result and spent worker slot. [Checkout, installed bytes, wheels and authority digests](compatibility-final-rollup.json) · [FILES execution and read-only filesystem observations](compatibility-47e-files.json)

### Prerequisites for the remaining requirements

Of the original 418 incomplete rows, the new Python run supplied dependency proof for 12 and the full FILES controller supplied evidence for two. The 404 still open include 229 that require combining original component results on one installed subject, 94 that need an independent native controller observation and 81 that need the declared simulation or database fixture. The current map identifies each original source report and each required dimension across the 43 domains with open requirements. [Current prerequisites](compatibility-prerequisites.json) · [Historical 330-result matrix](compatibility-330/compatibility-final-outcomes.json)

The 27 failed requirements trace to 18 named-limit, seven ranging and two scheduled-time positive checks on 655f5b5a. A fourth diagnostic also failed the memory snapshot comparison and had zero individual rows assigned to that comparison. The failure record preserves the expected and observed outcomes and each owner's remaining dependency. [Failures by inherited ID](compatibility-negative-rows.json)

A clean Python 3.13.15 directory reproduced the current rollup, the 763-row matrix, the 404-row prerequisite map, the full FILES evidence and the earlier 318-result matrix byte for byte. Altering the original Python report or the captured run archive caused verification to fail. Reversing the observed FILES prompt options also failed verification after recomputing the archive fingerprints. [Current regeneration results](compatibility-final-reproduction.json) · [Python and dictionary verification](compatibility-47e-portable-verification.json) · [FILES verification](compatibility-47e-files-verified.json)

From the repository root, the following commands verify the captured files and regenerate the reports.

```sh
python scripts/v08_compatibility_files47.py --output docs/v0.8/evidence/qualification-20261122/compatibility-47e-files.json
python scripts/v08_compatibility_final_rollup.py --output docs/v0.8/evidence/qualification-20261122/compatibility-final-rollup.json
python scripts/v08_compatibility_prerequisites.py --output docs/v0.8/evidence/qualification-20261122/compatibility-prerequisites.json
python scripts/v08_summarize_native_qualification.py docs/v0.8/evidence/qualification-20261122 --final-subject --output docs/v0.8/evidence/qualification-20261122/compatibility-final-outcomes.json
```
