# Delivery through stable v1.0

Execute releases in order, committing and pushing accepted releases to GitHub
master. Keep release notes short: behavior, supported scope, verification and
remaining limits. Retain detailed machine-readable evidence separately.

| Release | Acceptance |
| --- | --- |
| v0.5 | All 763 original language requirements independently qualified, including positive, boundary, failure and recovery evidence; manual/source conflicts resolved. |
| v0.6 | Final reproducible packages, clean install/removal and versioned upgrades; installed OpenBEXI, IntelliJ and PyCharm workflows; DSS runtime qualification and supported platform matrix. |
| v0.7 | Operational security and capacity qualification; controller fencing, uncertain-effect handling, overload, backup/restore and recovery exercised against installed artifacts. |
| v1.0.0-rc1 | Frozen source/artifact set; end-to-end regression, operational and installation gates pass; concise installation/recovery documentation. |
| v1.0.0 | Release-candidate defects resolved and affected gates repeated; exact artifact hashes and accepted scope recorded; stable tag on master. |

Current accepted scope ends at the v0.4 GENERIC simulator profile. The
[current checkpoint](LANGUAGE_CHECKPOINT.json) qualifies **487 requirements with
276 open**. All 35 native suites pass on the rebuilt runtime. Final installed-host
workflows remain open; passing prerequisites do not accept their parent release.

Next language work: legacy comparison compatibility, then remaining telemetry,
command/limit, display, data and special-service contracts. Each increment needs
independent positive, boundary, failure and recovery evidence. Preserve all 763
original requirements and retained failures.

Use `distribution/run_language_regressions.py --image <immutable-image-id>` to
run the combined runtime sequence. It retains each raw report and rejects failed
checks, missing checks, changed source bindings and mismatched runtime identities.
The conformance gate remains `conformance/check.py`; an open-row result must not
be relabeled as full acceptance. The existing archive and qualification evidence
remain preserved.
