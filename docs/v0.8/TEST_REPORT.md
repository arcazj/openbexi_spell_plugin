# Phase A/B test report

Date: 2026-10-22. Plugin baseline `109a47af47951e2fa54b60cb408a543b117f7f15`;
requirements base `76144fb704a8e3777209df04058c62d80bbc962f`;
IDE baseline `7585d221a58fcfe178b93046c691ad74a92148e9`.

| Check | Result | Evidence |
|---|---|---|
| Baseline API/refs/source/manual/deployment audit | Collected; public release metadata and healthy production verified | `evidence/baseline-audit.json` |
| IDE session/durable/procedure regressions | **37 passed**, 0 failed/skipped, warnings as errors | `evidence/baseline-regressions.xml` |
| Installed original-native-driver → binary DSS test | **1 passed**, actual 0.7.0 packages and exact native image | `evidence/native.xml`, `native.log` |
| Native process tree/socket trace | Listener, Context and Executor distinct PIDs observed | `evidence/native-trace.json` |
| Retained v0.7 qualification | Report hashes/inventories checked; full historical run not repeated | Existing `docs/V07_QUALIFICATION.json` and evidence |
| Baseline integrity | 109 retained report files and 225 installed package members match accepted hashes; original edits preserved | `evidence/review-integrity.json` |
| Architecture diagrams | Three editable DOT sources, PNG/SVG exports; repeat render bytes and checksums verified; images visually inspected | `diagrams/manifest.json`, `SHA256SUMS` |
| Hosted CI at baseline | **Absent**; 0 Actions/check/status records, aggregate pending | Baseline audit API results |
| Independent architecture/security review | **Pending** | `ARCHITECTURE_REVIEW.md` |
| v0.8 mandatory runtime/browser/Compose/K8s/security gates | **Not run** | `ACCEPTANCE_PLAN.md` |

Commands executed (PowerShell; use CPython 3.13 with pytest 8.4.2):

```powershell
# Plugin worktree; pypdf is an audit-only dependency.
& C:/projects/openbexi_spell_plugin/.venv/Scripts/python.exe -X utf8 scripts/audit_v08_baseline.py --ide C:/projects/openbexi_ide --original C:/projects/openbexi_spell_plugin --output .qualification/v08-baseline
# IDE baseline worktree; imports its frozen source through the existing fixture.
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& ./.venv/Scripts/python.exe -I -m pytest tests/test_sessions.py tests/test_durable_sessions.py tests/test_procedure_service.py -q -W error --junitxml=C:/obspell_v08/.qualification/v08-baseline-regressions.xml
# Plugin worktree; executes the already-retained, composition-adapted installed oracle.
& C:/projects/openbexi_ide/.venv/Scripts/python.exe -I scripts/trace_v07_baseline.py --installed-tests C:/obspell_v07/.qualification/v07-installed-fenced --output .qualification/v08-native-baseline
```

The trace harness records the exact retained oracle SHA-256, installed package
versions, test command, image, process IDs and socket tables. It does not repeat
fresh browser interaction or claim external DSS runs in a separate process in
that test: the acceptance fixture hosts DSS in its test process. Independent
deployed DSS lifecycle is a required v0.8 gate.

The v0.7 browser/Qt evidence and source complete the as-is UI call-path audit.
The fresh native test adds a current execution/driver trace. No failed tests
were reclassified and no v0.8 acceptance result is inferred from them.

Phase A/G0 evidence is ready for review. Phase B/G1 is pending explicit review
and owner approval. Phase C implementation has not started.

# Initial C/D foundation qualification

The owner authorized the G1 review resolutions and staged implementation with
"Approved , move forward". The original Phase A/B evidence above remains
historical evidence at its stated identities.

New implementation: standalone `server/`, version `0.8.0.dev1`; no change to
published v0.7 runtime packages or entry points. The service has no execution,
worker, driver, ownership transfer, browser session or WSS route.

Local CPython **3.13.16**, OpenSSL **3.5.9**: **50 passed**, zero errors, failures
or skips, with warnings as errors. Lint, formatting and mypy pass. Real TLS
sockets cover pinned service roles, forged identity/Origin/Host, independent
Context permissions, authorization before idempotency replay, malformed input,
Context isolation and concurrent writes. Separate real processes cover Listener
crash/restart, Context crash/restart, durable data and new incarnation.
A 100-request CAS race produces one revision winner and 99 conflicts.

`uv build server --python .venv/bin/python` built wheel and source distribution.
The wheel was installed without dependencies and its CLI executed successfully
with `python -I -m openbexi_spell_server --help`. Nothing was published.

Evidence: [result](evidence/server-foundation/result.json),
[JUnit](evidence/server-foundation/tests.xml),
[process trace](evidence/server-foundation/process-trace.json),
[development attempts](evidence/server-foundation/development-attempts.json) and
[package hashes](evidence/server-foundation/package-build.json). Four failed
development attempts are retained as compressed original JUnit files; they
were fixed/retested and are not relabeled as passes. The final report records
input hashes and a dirty working tree; it is local source-hash evidence, not an
assertion that the preexisting HEAD was the tested implementation commit.

Reproduce with `.venv/bin/python scripts/qualify_v08_server.py`; each invocation
retains a fresh output directory. The new pinned-action GitHub workflow runs
these foundation checks and package smoke on the candidate SHA and uploads
evidence, including failures. Hosted results must be read from the actual PR
checks; a local pass does not establish a hosted pass.

G1: approved for staged implementation under F1-F10. Initial C/D foundation
checks: PASS within the scope above. Full C/D integration: PENDING. E-L native
execution/ownership/driver/browser/Compose/Kubernetes/security/release gates:
PENDING, not inferred from 50 foundation tests. No native Executor test, Docker
deployment or Kubernetes cluster test was performed in this implementation run.
