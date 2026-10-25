# Full v0.8 publication qualification

Latest owner request: **"Qualify and release full v0.8"**. This authorizes
implementation/qualification, merge, tag and GitHub publication when all
mandatory criteria pass. It supersedes the separate-confirmation hold; another
routine publication confirmation is not required. It does not authorize
production migration or weaken G1 F1–F10 or acceptance requirements.

The full release is **not qualified**. Package `0.8.0.dev34` remains development
code. Dev31 at `9de50ea` verified a 21-member retained native family, original
durable member identities and stale-controller initial RUN rejection. Dev32
adds fresh owner STEP/PAUSE grants. Its push native STEP/disconnect oracle passed;
the PR family OOM-killed a worker at 768 MiB. Dev33 bounded memory requalification
failed on resource accounting and a separate non-OOM startup timeout. Dev34
corrects kernel peak telemetry and adds same-owner RUN/PAUSE/RUN qualification;
hosted execution is pending, and all original failures are retained.
Existing component receipts do not qualify full family handoff/resume, joint
IDE Run/Debug/browser, Kubernetes or deployed recovery.

## Publication preflight

`RELEASE_GATES.json` records eleven mandatory gate groups and their blockers.
`python scripts/check_v08_release.py --output <report.json>` exits nonzero unless
all have complete, source-bound, checksummed receipts and server version `0.8.0`.
Partial/component schemas, missing checks, altered evidence, stale SPELL/IDE
commits and uncommitted runtime changes cannot qualify publication. The
preflight validates records; it does not execute missing qualification or create
a release. Actual hosted/cluster results and source artifact verification remain
mandatory; hand-edited flags are not executed tests.

Receipts use `openbexi.v08.acceptance-gate/1`, the gate name, exact executable
candidate_commit, paired ide_commit, passed true, every required check true and
executed-evidence references. The manifest pins relative path and SHA-256.
`--candidate <exact-code-SHA>` permits later evidence-only commits, avoiding a
self-referential commit hash inside its own receipt. Runtime/workflow/IDE-pin
changes require new qualification; evidence commits cannot hide them.

## Confirmed inherited-suite issue

The broad inherited diagnostic was interrupted after repeated failures/errors;
it is not a completed suite. A bounded reproduction stopped after **three
failures and sixteen passes**, first failures in
`tests/test_child_arguments_report.py`. They reference missing captures at
historical Windows path `C:\\obspell_v06_resume\\.qualification\\...`. The
original v0.7 raw archive SHA-256 is
`9db68109972848d7dd38634c421c1aad94bb75103df9e65432e0e58e99dd9357`.
Captures must be verified against original immutable sources. Current files
cannot replace captured sources or relabel old reports as v0.8 proof. The
historical/current split is in `scripts/qualify_repository_v07.py`. New behavior
needs fresh native qualification. The 241 portable tests remain a named subset,
not all-763 requirement coverage.

## Work required before publication

First implement the mandatory native before-RUN child gate and full participant,
control/prompt/effect settlement. [Child admission](NATIVE_CHILD_ADMISSION.md) is
preparatory and keeps native_start_qualified false. Then prove owner/epoch CAS
and explicit new-owner resume with old requests fenced. Complete compatibility,
driver faults/recovery, joint SPELL/IDE browser Run/Debug/WSS/Git, actual
Compose/Kubernetes qualification, independent security/SBOM/license/vulnerability
review and stable installed artifacts. No full deployment environment or full
gate receipt is present here; hosted component jobs do not satisfy those gates.

Publication remains authorized conditional on these results. Release is blocked
by qualification, not missing user approval.


## Executed assessment

On clean code **7d2ab39951e3e250aa5bbb43633641fbd5254a3c**, the
[publication preflight](evidence/release-readiness/publication-preflight.json)
exited 1 with full_v08_qualified and eligible_for_publication both false. All
11 mandatory full gate groups remain unqualified; server is 0.8.0.dev16. The
[bounded inherited summary](evidence/release-readiness/inherited-bounded-summary.json)
records 16 passes/3 failures and preserves the narrower scope. Hosted 344 scoped
checks, 241 portable checks and all six services/native jobs passed at that code;
they do not override this failed full-release assessment. See TEST_REPORT.md.
