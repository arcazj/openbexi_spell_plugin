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

The [v0.5 acceptance record](V05_CONFORMANCE_QUALIFICATION.json) qualifies all
763 original language requirements with none open. All 61 native suites pass
on one rebuilt runtime, with independent source and behavior reviews.

The [v0.6 acceptance record](V06_QUALIFICATION.json) also accepts reproducible
packages, versioned upgrades and installed OpenBEXI, IntelliJ IDEA and PyCharm
workflows on the supported platform matrix. The [v0.7 acceptance record](V07_QUALIFICATION.json)
adds operational security, capacity and recovery qualification against installed
artifacts. Next is v1.0.0-rc1: freeze the accepted source/artifact set and complete
the release-candidate gates. Preserve the GENERIC simulator scope, all 763
original requirements and retained failures.

Use `distribution/run_language_regressions.py --image <immutable-image-id>` to
run the combined runtime sequence. It retains each raw report and rejects failed
checks, missing checks, changed source bindings and mismatched runtime identities.
The conformance gate remains `conformance/check.py`; an open-row result must not
be relabeled as full acceptance. The existing archive and qualification evidence
remain preserved.
