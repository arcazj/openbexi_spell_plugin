# Historical Phase A/B test report

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

The original checkpoint above preceded G1 review and implementation. It is
retained as historical evidence; G1 was subsequently reviewed and approved.

# Historical initial C/D foundation qualification

The owner authorized the G1 review resolutions and staged implementation with
"Approved , move forward". The original Phase A/B evidence above remains
historical evidence at its stated identities.

New implementation: standalone `server/`, version `0.8.0.dev1`; no change to
published v0.7 runtime packages or entry points. The service has no execution,
worker, driver, ownership transfer, browser session or WSS route.

Local CPython **3.13.16**, OpenSSL **3.5.9**: **51 passed**, zero errors, failures
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
PENDING, not inferred from 51 foundation tests. No native Executor test, Docker
deployment or Kubernetes cluster test was performed in this implementation run.


# Historical dev2 services and prelaunch authority qualification

Package `0.8.0.dev2` adds the bounded registry and ownership protocol described
in [EXECUTION_AUTHORITY.md](EXECUTION_AUTHORITY.md). Native execution remains
explicitly disabled. This supersedes the earlier foundation-only description,
while preserving that checkpoint's original results.

Local CPython **3.13.16**, OpenSSL **3.5.9**: **106 passed**, zero errors,
failures or skips, warnings as errors. Ruff lint/format and mypy pass. Exact
SHA-256s of **21** qualification inputs match the tested local files. The report
records parent HEAD `925ad0d` and a dirty working tree; these are source-hash
results, not a claim that the parent commit contained the new implementation.
Candidate hosted checks must independently run on the actual pushed SHA.

Evidence: [result](evidence/execution-authority/result.json),
[JUnit](evidence/execution-authority/tests.xml),
[real process trace](evidence/execution-authority/process-trace.json),
[development attempt](evidence/execution-authority/development-attempts.json),
[package build](evidence/execution-authority/package-build.json) and
[compatibility scope](evidence/execution-authority/compatibility-scope.json).

The added tests cover 100 concurrent logical reservations with one winner,
100 consumptions of one immutable start grant with one winner, ten distinct
single-use registry slots, same logical ID in two Contexts, simultaneous claims
and accepts, transfer of B while A/C remain unchanged, forged proofs, revocation,
expiry/rejection/cancellation, response-loss replay, private capability delivery,
rebind/late disconnect, bounded admission waits, audit rollback and SQLite failure.
Start/accept races cannot produce an accepted new owner plus old-origin start.
A deliberately delayed grant remains invalid after transfer and new-owner rebind.
Post-consumption transfer returns BLOCKED and retains the old owner and holds.

A real subprocess dies immediately after start-consumption commit; reopening
state fences the original grant and refuses replacement. Separate real service
processes demonstrate that Listener death/restart preserves Context ownership,
while Context death/restart advances its epoch, retains its procedure hold and
leaves the other Context's epoch unchanged. The credential-free trace records
those service processes. It does **not** record native Executor processes.

The initial 34-test authority development attempt retained one failure: a test
expected `controller_fenced` after an already closed connection, while the
correct denial was `connection_denied`. Its original compressed JUnit is retained;
the denial remains enforced. Manual design review also caught an epoch-restamping
hazard: issuance moved to original controller admission, and the new delayed-grant
regression passed. Neither observation is reclassified as a passed original run.

Wheel and sdist build passed; the isolated installed wheel CLI smoke passed.
All seven wheel source members match the checked files, licensing and source
tests are included, and no private keys are packaged. Nothing was published.
Original v0.7 runtime paths remain unchanged from the requirements base; the
37 historical baseline regressions and native/DSS test were not repeated here.
That integrity check is not a new full compatibility qualification.

**G2/E and G3/F remain pending.** These are authority protocol, actual TLS and
service-process tests. They do not launch a native worker, authenticate a worker
certificate/Pod UID, verify actual source inventory/aliases, pause descendants,
settle driver writes, exercise browser/WSS or deploy Compose/Kubernetes. No
native pause, external-effect recovery, production storage fencing, automatic
reuse, full security scan or release gate is inferred from these passes.


# Current dev3 source and worker-preflight qualification

Package `0.8.0.dev3`: **143 local CPython 3.13.16 tests pass**, zero failures,
errors or skips, warnings as errors. Ruff lint/format and mypy pass.
WORKER_PREFLIGHT.md defines the exact configured profile and limits.

New tests verify exact Git commit/tree/blob hashes, ignore working-tree changes
and replace refs, normalize approved aliases, reject unapproved metadata, and
reject unsafe or mismatched source inventories. Actual mTLS sockets and a
separate worker-preflight CLI process test role/scope/assignment checks and
source digest verification without importing or executing procedure code.
Expiry, forged receipts, rebind/transfer, Context restart, replay, capacity and
audit rollback are covered. Expired preflight at consumption rolls back the
spent flag and preserves the hold. Unsupported Kubernetes identity and
ambiguous worker/Listener roles fail startup.

Evidence: `evidence/worker-preflight/result.json`, `tests.xml`, service and
worker-preflight traces, package/source hashes and the retained failed development
attempt. The initial new-source run had one fixture failure because `git add .`
removed a staged, absent submodule before the test commit. The fixture now
commits the staged gitlink directly; the source rejection remains enforced.
Intermediate lint findings about unused/imported fixtures were corrected.

The source-hash result records the parent HEAD plus dirty local state; candidate
hosted checks must independently run on the resulting pushed SHA. The scoped
workflow also builds the wheel and smokes both service and preflight CLIs.

**Runtime remains disabled.** The worker reports a digest using a registered
credential; it is not binary/image/hardware attestation. Read-only mounts,
Kubernetes Pod UID/admission, native execution/pause/descendants, final source
immutability at launch, driver actual-send/settlement, browsers and deployments
remain unqualified. Docker is unavailable on this local execution host. No
native Executor or deployment result is inferred from the preflight PID.
Original v0.7 runtime files remain unchanged; its historical baseline/native
evidence is retained and was not rerun in this increment. No merge or release.

# Disconnect barrier qualification — 2026-10-23

Development package `0.8.0.dev4`: **148 tests passed**, zero failures/errors/skips,
warnings as errors; lint, formatting and mypy passed. Exact source hashes,
commands and JUnit are in `evidence/disconnect-barrier/`. Earlier checkpoints
above retain their original scope and identities.

The new tests exercise a held execution mutex during close, durable CLOSING
after timeout, admission denial, unrelated database progress, original-key
retry, live permission revocation, rebind preservation, restart recovery and
schema-version preservation when worker preflight initializes. A development
test initially used an unsupported ContextStore context manager; its fixture
was corrected to use explicit closing before the final qualification.

No actual driver write or native Executor was run by these checks. The barrier
orders future bounded writes; native quiescence, effect settlement, deployment
and full compatibility gates remain pending. Package schema 4 intentionally
rejects downgrade to older binaries.

# IDE/gateway pair qualification

Server package `0.8.0.dev5`, paired IDE `1.2.1.dev1` at the exact commit in
`IDE_PAIR.json`: **152 local tests pass**, zero failures/errors/skips, warnings
as errors; lint/format/mypy pass. Source hashes and installed IDE source hashes
are retained in `evidence/ide-pair/`. Four new real-boundary checks use actual
IDE clients and the Qt panel over the certificate gateway, Listener and Context:
three separate user certificates, 20 observer reads, denied observer mutations,
explicit handoff, original-key replay, stale owner denial, rebind/late disconnect,
forged headers, direct internal-role denial and live role revocation.

The companion IDE retains its separate 11 passing client/Qt tests and the failed
local legacy baseline (21 passed, 16 failed) caused by PID/procfs namespace
mismatch. Hosted full-IDE checks must be read on their actual SHA; no local
compatibility pass is inferred. First hosted setup failed on missing libEGL;
the workflow now installs the Qt runtime and retains startup logs.

A new hosted diagnostic verifies frozen v0.7 image/archive bytes and probes real
native process startup/execution in an isolated non-root container. Its actual
outcome must be read from CI; it is not v0.8 native launch, effect settlement,
descendant pause or Compose/Kubernetes qualification. All full runtime gates
remain pending and `runtime_enabled` remains false.

## Final paired GUI/concurrency increment

**154 local tests pass**, zero failures/errors/skips, with lint/format/mypy
passing. `IDE_PAIR.json` pins the final companion source including GUI shutdown
and local-execution-fallback guards. `evidence/ide-pair-final/` retains exact
source hashes, installed IDE module hashes, JUnit and process traces. A real
100-request TLS reservation race across eight independent clients produces one
winner and 99 conflicts. Three actual Qt panels (captured in `evidence/ide-pair-final/ide-three-panels.png`) complete reserve → request →
accept → rebind → observer refresh → disconnect. Fourteen companion IDE client
and GUI tests pass locally, including nonblocking shutdown and rejection of
local Run/Debug while connected to the server.

The expanded IDE hosted run at `74335a1` passed **232 tests**, with one explicit
Windows-only Job ownership skip on Linux: SDK and DSS examples were installed,
and all eight existing immutable-image Docker execution tests ran. Both PR and
push workflows passed (`39908884967`, `39908880908`). Earlier `ab44417` hosted
results had 218 passes and 15 skips; those skips are not counted as passes.
The latest GUI guard candidate must run its own hosted checks.

The frozen native boundary diagnostic passed in hosted PR run `39908551614`.
The verified downloaded artifact and origin metadata are retained under
`evidence/native-boundary/`. It observed SPELL-Listener PID 9, SPELL-Context PID
26 and SPELL-Executor_v3 PID 74 in the container, with PAUSED → FINISHED.
These are real native PIDs, independently observed from registry/preflight PIDs.
The original v0.7 image is identified by its exact archive/image hashes.
No v0.8 native worker launch or driver settlement is inferred from that result.

# Portable legacy compatibility subset and full-suite diagnostic

Latest companion IDE `a1ec00f`: **235 hosted tests pass**, with one Windows-only
Job ownership test skipped on Linux; both PR `39909450551` and push
`39909445313` pass. This includes all 14 new client/Qt tests, companion SDK/DSS
examples and the eight existing offline Python Docker execution tests. The
paired server candidate `3fd050f` passed both hosted workflows (`39909811358`,
`39909806537`), including all 154 scoped checks and frozen native diagnostic.

A broader local plugin diagnostic initially collected 916 cases with 23 import
errors because grpc/protobuf were absent. After installing their pinned
versions, the full historical root suite recorded **744 passed, 227 failed and
271 errors**. This is a failed diagnostic, not a compatibility pass. Of those
failures/errors, 336 were missing historical Windows capture files, 141 were
composed test-module relative-import warnings, two were missing pypdf, 17
concerned the legacy token-preparation helper and two rejected stale source
identity assertions. Original compressed JUnit/logs are retained in
`evidence/compatibility-diagnostics/`.

The published v0.7 raw archive was downloaded and its exact 217,653,956-byte
size and SHA-256 verified. Its manifest describes 7,838 files. Those are later
v0.7 captures; this does not supply every earlier absolute Windows capture
referenced by historical development tests. No report was rewritten, source
hash restamped, missing capture fabricated or failure relabeled. The full root
suite has not been qualified for the current candidate. G4 remains pending.

Portable fixes: package-relative imports in composed fixture modules now have
their actual package metadata; the GPL legacy `<>` helper also handles adjacent
`<`/`>` operator tokens without changing whitespace, strings, comments, encoding
or line positions. This helper is still preparation-only, not a newly integrated
native compiler. Actual native grammar qualification remains separate.

The first portable run had 191 passes and two resource-warning errors. Follow-up
fixed real read-only viewer connection cleanup, closed recorder connections and
released HTTP error responses. A direct regression proves the viewer closes
SQLite on both success and failed namespace lookup. No warning filter was added.

Final local portable subset: **241 tests passed**, zero failures/errors/skips,
with warnings as errors, including actual original protobuf dispatch and binary
DSS TCP exchanges. Exact commands, tool versions and source hashes are in
`evidence/portable-compatibility/`. The separate hosted compatibility workflow
runs this explicit subset; it must not be presented as all 763 requirements,
a native worker/DSS-process test or v0.8 actual-send fencing qualification.
Published v0.7 artifacts remain unchanged; source fixes are unreleased and need
their own future wheel/image build and native acceptance before publication.

## Private actual-send boundary, development candidate 0.8.0.dev6

The current local service/paired-IDE suite passes **179 tests**, zero failures,
errors or skips, with warnings as errors. Ruff formatting/lint and mypy pass.
The 25 new boundary cases use the actual GPL fenced transport and independent
DSS processes. Five-stage receipts, ten concurrent driver operations, another
execution's progress during receipt waiting, stale/forged provenance, wire
identity binding, role revocation, capacity/endpoint denial, handoff while a
receipt is pending, real backpressured writes, lost release receipts and process
death between an actual TCP write and the SENT commit are covered.

`DRIVER_WRITE_GATE.md` defines this private trusted-Context seam. Final live
admission and the bounded actual socket write share the execution mutex used by
controller changes. Short authority and separate driver ledger commits precede
the write. Receipt waits hold neither execution nor database mutex. Missing or
uncertain effects retain recovery holds; no replay or synthetic receipt exists.
Start admission and consumption now both require live `execution:start` as well
as control permission. Creating the gate upgrades authority storage to schema 5;
older binaries reject that state.

The first compatibility attempt caught three strict telemetry-preimage errors
when the original transport source was edited (238 passed, 3 setup errors).
Those diagnostics are retained. The fix preserves the original `transport.py`
byte-for-byte and implements the mandatory-admission variant in the separate
GPL `fenced_transport.py`; no immutable patch recipe hash was changed. Final
portable compatibility rerun: **241 passed**, zero failures/errors/skips, with
warnings as errors. It still does not cover the full historical root suite.

The server development wheel builds and passes isolated installed import,
package-version consistency and CLI checks. Evidence, source hashes, commands,
JUnit, DSS PIDs, failed compatibility diagnostic and wheel digest are retained
in `evidence/driver-write-gate/`. Local reports identify the prior Git head plus
exact changed source hashes; hosted candidate-SHA checks must be assessed
separately. The companion IDE remains pinned to `a1ec00f` by IDE_PAIR.json and
its actual three-panel integration is included in the 179 tests.

**Full v0.8 remains unqualified and `runtime_enabled: false`.** No native worker
or service route invokes this seam yet. Ten driver operations are not ten native
Executors. Full native driver lifecycle/TM/resource ACLs, native child admission,
quiescence and handoff, all-763 compatibility, browser/WSS, real Compose and
Kubernetes admission/network/storage/failure recovery, independent security
review and release acceptance remain pending. No tag/release/merge follows from
these results.

## Retained native compute and Context event driver, 0.8.0.dev8

Hosted push **d962268** and its PR workflow passed the first actual v0.8 retained
native launch cohort. Ten distinct approved procedures consumed their original
grants over real mTLS and ran simultaneously in ten separate read-only,
non-root, single-use containers. Host Docker inventory verified thirty distinct
live native Listener/Context/Executor PIDs. All ten procedures finished and all
containers terminated. Twenty real EV lifecycle calls were committed to Context
before driver acknowledgement. Ten spent slots and ten logical reservations
remained held. Worker-to-worker native-port and external TCP denial passed;
Context had no Docker socket or host manager. The positive handoff check occurred
after container termination and remained BLOCKED with old ownership/epoch.

The server/source/IDE/driver/launch suite passed **217 tests** locally and hosted
at this code checkpoint, with zero failures/errors/skips and warnings as errors;
lint/format/mypy and installed development-wheel checks passed. The **241-test**
portable compatibility PR workflow passed on the same candidate. The redacted counts, public source hashes and workflow references are in
`evidence/native-retained-launch/qualification-summary.json`. Detailed logs,
process observations and original failures remain in their existing CI runs.

Earlier completion tests correctly failed on real EV calls. Original native
controller code emits start/finish events even for arithmetic-only procedures;
removing printing alone was insufficient. The final implementation parses the
original event protobuf in the GPL agent, forwards it over pinned mTLS, and
acknowledges only after Context's atomic, original-grant-authorized journal
commit. Non-procedure scopes, changed replays, fenced owners, unknown bindings
and full audit storage are denied. Other native driver calls remain denied.
Schema 6 prevents old-binary downgrade and is preserved by the socket driver
gate. Audit text never serves as a quiescence or release proof.

A later check adds a physical worker clone using the same certificate,
incarnation and spent original grant; final candidate CI must verify rejection
before native startup. The final suite also adds a concurrent native event vs
handoff regression and a per-execution event bound. These additions do not
retroactively change the d962268 artifact's scope.

**Full v0.8 is still unfinished and unqualified.** This is retained compute plus
scoped audit logging, not native TC/TM, safe cooperative pause/handoff, child
admission, worker reclamation/recovery, native IDE Run/Debug, browser/WSS, all 763
requirements, production Compose/Kubernetes or independent security/release
acceptance. The companion IDE remains pinned to a1ec00f and its existing
prelaunch control/panel integration is exercised by the service suite. No
release/tag/merge is authorized by these subset results.
