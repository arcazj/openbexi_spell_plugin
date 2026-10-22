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
