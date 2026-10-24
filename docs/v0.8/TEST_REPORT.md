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

Final native-code checkpoint **c8b286c** passed hosted PR and push services/native
workflows, including **218 scoped tests** and wheel smoke. Its native cohort
also started a physical clone with an original worker certificate, incarnation
and spent grant; it was rejected before opening a native session. Ten positive
workers, thirty native PIDs, twenty durable lifecycle events and all retained
holds were verified again. The same-code PR compatibility subset passed **241
tests**. The redacted summary now identifies this checkpoint; detailed CI
artifacts are not republished in the repository. Full qualification remains false.

# dev9 Context-owned original TC/TM boundary

The optional GPL host and route contract are documented in NATIVE_DSS.md.
The standalone Apache server and default gateway/Listener/IDE retain their
execution-disabled defaults. The worker forwards original protobuf bytes under
the original consumed grant; Context selects the endpoint, resource allowlist,
wire identities and non-replayable operation UUID. Schema 7 protects the new
bounded call ledger against older binaries.

Fresh local CPython **3.13.16** qualification passed **246 scoped tests**, with
zero failures, errors or skips and warnings as errors. Ruff lint/format and mypy
passed. The real mTLS/original-protobuf/independent-DSS subset adds 28 tests:
one real TC has five correlated ACKED receipts; twenty duplicate RPCs have one
winner; other original driver methods and wrong certificates/grants/resources
are denied; transfer between stages blocks the next write; a lost RELEASE
receipt retains uncertainty and ownership holds and cannot be replayed; bounded
call capacity is reserved before any wire effect. Telemetry uses original
CreateTmItem/RefreshItem messages and the existing packet/catalog validation.

The unchanged portable compatibility subset also passed **241 tests**, with
zero failures/errors/skips and warnings as errors. An offline wheel build with
the pinned build backend and clean isolated installed-wheel version/import
check passed for **0.8.0.dev9**. No existing environment was modified to install
the wheel. An initial test fixture used the wrong generated protobuf class and
one fixture import triggered lint; both failed diagnostics are retained in the
local development log and are not counted as passes. The first packaging
command found no pip in the shared uv environment; the wheel was instead built
from the offline uv cache and installed in a new isolated environment.

The hosted native matrix now keeps audit-only compute and adds a separate
`--native-dss` cohort. The latter requires ten real native SendCommand calls,
original RefreshItem calls, ten retained native workers and fifty durable TC
stage receipts, using a separate internal-network DSS container. **This new
native profile is NOT RUN locally:** Docker/Kubernetes tools are unavailable in
this workspace. Its candidate-SHA CI result must pass before claiming native
TC/TM qualification. It does not close native quiescence/live transfer, children,
recovery, IDE execution, full historical compatibility, browser/WSS, production
Compose/Kubernetes or independent security/release acceptance.


## dev10 single-consumer proof and native fixture correction

The dev9 PR services/native run 39999917882 completed: foundation,
native-boundary and audit-only launch passed, but the new native DSS job failed.
Artifact 12520924294 retained all ten worker failures, each `NameError: name
'Send' is not defined`; the procedure fixture lacked `from spell.lang import *`.
The dev10 fixture adds the SDK import. This is a corrected cause, not yet a
native pass.

A separate adversarial probe against dev9 confirmed a more serious defect:
a second process holding a copied ORIGINAL certificate and start configuration
could skip consumption and call the newly added driver route successfully
(HTTP 200 where 403 was required). The pre-fix failing JUnit is retained as
`original-config-probe-before-fix.xml` in local qualification evidence. The
honest clone's failed consumption was insufficient proof against direct RPC.

Dev10 atomically commits a hash of a new random 256-bit runtime proof with the
single successful consumption. Only that consumer receives the plaintext;
the native agent retains it in memory, never in the original configuration,
logs or a replayable response. All check/event/driver requests now require
this proof plus the unchanged original grant, certificate assignment and live
authority. A lost receipt cannot be refreshed; slots and reservations remain
retained. Schema 8 rejects unsafe old-binary access. Retained launch uses
`openbexi.worker/2`; preflight stays on version 1. This does not attest worker
memory or admit untrusted procedure code.

Fresh CPython **3.13.16** qualification passed **254 scoped tests**, zero
failures/errors/skips, warnings as errors; lint/format/mypy passed. New checks
cover copied configuration, missing/malformed/guessed proofs, lost-proof denial
and retention, atomic rollback on failed audit commit, and absence of plaintext
proofs in both effect databases. The first focused run exposed one stale
schema-6 expectation (now schema 8); that failure is retained separately.
Evidence: local `v08-server/run-20261023T181302Z-64733ab3`, with exact changed
code hashes. The README/protocol documentation was updated during that run;
no tested code changed after capture. Candidate-SHA CI must independently
qualify the committed source and documentation.

An offline **0.8.0.dev10** wheel build and clean isolated installed-wheel
version/import plus both service/worker CLI smokes passed. The existing dev9
**241-test portable compatibility** pass still applies to the unchanged legacy
code; it is not all-763 qualification. Hosted dev10 audit/DSS cohorts are
pending. The DSS cohort additionally requires a separate physical process with
only copied original credentials/configuration to receive HTTP 403 on direct
driver RPC. It must still prove ten commands, telemetry and fifty ACKED stages.

Full v0.8 remains **unqualified**, with public runtime disabled. Native
quiescence/live transfer, children, recovery/reclamation, full compatibility,
IDE/browser execution, deployment and independent security/release acceptance
remain open. No merge, tag or release is authorized by these subset results.


## dev11 native-client route integration

The dev10 hosted PR run 40001929895 passed foundation (254 tests) and
native-boundary. Both actual launch cohorts failed before native-ready:
`Route.call` rejected the protocol-2 launch as an unconfigured route. Direct
HTTP tests had covered the new server protocol but not the agent's real
client allowlist. Artifacts 12523245135 (audit) and 12522007581 (DSS) retain
the original failures. This is not an application procedure failure or a pass
for the corrected dev9 fixture.

Dev11 updates the explicit client allowlist to protocol 2 for consume/check/
event/driver, leaving challenge/verify at version 1. The physical clone probe
now asserts the transport's actual `Fault.status`, not an HTTPError cause. A
new real-client mTLS regression sends checks, events and an actual command,
proves direct driver use without the winner proof is denied, and rejects both
client-route and server-body launch downgrade. Its initial certificate-fixture
key error is retained in `client-v2-fix.xml`; the corrected focused test passed
in `client-v2-corrected.xml`. Full local and hosted qualification follow below.


Fresh dev11 CPython **3.13.16** qualification passed **255 scoped tests**, zero
failures/errors/skips and warnings as errors, with lint/format/mypy all passing.
Evidence: `v08-server/run-20261023T181847Z-b34d7eb0`; exact tested code hashes are
retained under prior head 2ba8743 plus local changes. Offline wheel build and
clean isolated installed **0.8.0.dev11** version/import and both CLI smokes
passed. The dev10 hosted 241-test compatibility job also passed. Native dev11
candidate-SHA results remain pending; full v0.8 stays unqualified.


### Native SDK fixture follow-up

At dev11 head cbb2abd, hosted PR run 40002594765 passed the audit-only native
cohort and native-boundary. The DSS cohort reached ten actual running native
Executors but again failed `NameError: Send`, with no denied driver methods
(artifact 12523475378). The earlier `from spell.lang import *` imported the
compatibility facade rather than the native function exports. Existing native
conformance fixtures explicitly use `spell.lang.functions`. The follow-up
changes the DSS procedure to `from spell.lang.functions import Send,GetTM`.
Server package/runtime-proof logic is unchanged; the hosted native result is
still mandatory. All failed artifacts remain retained; no native TC/TM pass is
inferred from a syntactically valid fixture or from the audit-only cohort.


## dev12 original native command-catalog response

The e20357a hosted PR run 40003202950 passed the audit-only native cohort and
native-boundary. The DSS cohort then reached the actual native Send path and
failed `Invalid original command catalog response` in the installed proxy's
critical-command check, with no denied RPC method. Artifact 12523221760 retains
all ten original failures. Context's TC DatabaseLookup had omitted the original
`kind: COMMAND` discriminator that the composed native proxy requires.

Dev12 supplies this discriminator for an explicitly admitted single command.
The existing resource permission check still runs first; unknown/unlisted
commands and sequences remain denied. The new original-protobuf regression
checks the native catalog response's name/kind/critical/arguments and denies
CMD2 and SEQNAME. This is a response-contract correction, not expanded TC scope.
Local and hosted candidate results follow; no native pass is inferred yet.


Fresh dev12 CPython **3.13.16** qualification passed **256 scoped tests** with
zero failures/errors/skips and warnings as errors; lint, format and mypy passed.
Evidence: `v08-server/run-20261023T182835Z-2a5aba63` with source hashes under
prior head e20357a plus changed code. An offline **0.8.0.dev12** wheel build,
clean isolated version/import and both CLI smokes passed. The native candidate
must independently prove the corrected catalog contract through real Send;
full v0.8 remains unqualified and public runtime stays disabled.


### Physical copied-configuration probe validity

Review of the new physical probe found that its empty SendCommand payload
could independently receive resource-denied HTTP 403 if proof enforcement
regressed. The probe now serializes a valid original CMD1 CommandDesc with
the same original credential/configuration. CMD1 is explicitly permitted and
already used by the positive cohort, so a missing-consumer-proof denial can no
longer be confused with an unlisted command. A successful bypass would also
execute an eleventh command and violate the exact ten-command/fifty-stage
oracle. This is a qualification-strength correction; server logic is unchanged.
The unit/RPC copied-configuration regression already used a valid CMD1 and
retains its pre-fix HTTP-200 failure. The stronger physical probe still requires
its own hosted candidate-SHA result.


## dev13 neutral options from the composed native proxy

The 8887833 hosted PR run 40003950252 passed audit-only launch and native-
boundary, but the real SendCommand request was denied (artifact 12522339194).
Review of the frozen proxy composition in command_feature_patches.py and
command_catalog_patches.py confirms it always adds `ConfirmCritical: false`
after the native confirmation hook. Context's earlier timeout-only schema
rejected this legitimate native wire option.

Dev13 accepts only the neutral composed forms: ConfirmCritical/LoadOnly exactly
false, SendDelay numerically zero, and addInfo an empty dictionary, alongside
the existing positive timeout of at most three seconds. Actual critical commands
are still rejected at adapter startup; nonneutral options, delayed/scheduled or
load-only operations, nonempty metadata, unknown resources and other methods
remain denied before any effect intent. Tests require a real five-stage command
with these defaults and reject seven attempts to expand or mis-type them.
The native agent now logs only method/status/fixed error code on driver denial,
never a payload, grant or runtime proof. The valid physical clone probe remains
mandatory. Local and hosted results follow; full v0.8 remains unqualified.


Fresh dev13 CPython **3.13.16** qualification passed **264 scoped tests**, zero
failures/errors/skips and warnings as errors; lint/format/mypy passed. Evidence:
`v08-server/run-20261023T183448Z-9047e8b2`, with exact changed code hashes under
prior head 2aa20a1. Offline wheel build and clean isolated installed dev13
version/import and both CLI smokes passed. The native harness was subsequently
strengthened to compare all fifty ordered receipt rows across the independent
Context and driver databases, require nonempty receipt hashes, and report only
a digest/count and equality result. This harness change still needs hosted
validation; no additional native pass is claimed from the local suite.


## Confirmed hosted dev13 retained native TC/TM subset

Code **14ddf3df7956f2462a915072f5341488789b6842**, PR checkout merge
**21b409e469f8353fab8abf1ebe890382f161d58d**:
[services/native run 40004938954](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40004938954)
passed all four jobs. Foundation passed **264 scoped tests**, zero failures,
errors or skips, and built/installed/smoked the dev13 package. Native-boundary
and the audit-only cohort passed separately.

Native DSS artifact **12524290803**, ZIP SHA-256
`5e53a10d80b8b993ab4da84765d7d8175a8f2b7129de9b86a3e55ef5b95c3a3e`,
was downloaded, CRC-checked and inspected. All **81 source hashes** matched the
candidate checkout. It proves ten completed and terminated native workers,
thirty distinct running native Listener/Context/Executor PIDs, ten original
SendCommand and ten RefreshItem calls, twenty durable native lifecycle events,
and **fifty identical ACKED effect rows in each separate database**, including
nonempty receipt hashes. The valid-command copied-original-configuration probe
was denied, as was the honest spent-grant clone. Command count stayed exactly
ten, with ten logical holds and spent slots retained. Worker cross-peer native
port and external TCP denial passed; Context had no host manager/Docker socket.

The durable redacted receipt is
`evidence/native-context-dss/qualification-summary.json`. Raw operational
archives and credentials are not republished. This closes the retained positive
native TC/TM and direct copied-config subset only. Handoff remained BLOCKED
**after termination** with the original owner preserved; quiescence/live
handoff is NOT qualified. Full native fault/reconnect/child/recovery semantics,
all-763 compatibility, IDE/browser execution, production deployment, independent
security/SBOM/vulnerability and release acceptance remain open. Full v0.8 is
unfinished/unqualified and public runtime remains disabled.


The same code commit's
[portable compatibility run 40004938969](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40004938969)
also passed **241 tests**, zero failures/errors/skips and warnings as errors.
Both PR workflows completed successfully. This is the named portable subset,
not qualification of all 763 inherited requirements.


## dev14 durable fenced native pause probe

The next increment implements NATIVE_PAUSE.md: explicit opt-in Context-owned
barriers fence original-grant effect admission under the existing per-execution
mutex and commit a PAUSING decision without waiting for a worker. Only the
certificate-bound consumption winner can poll/report under the unchanged
original grant and memory-only proof. This safety channel can report after
controller revocation but cannot admit effects or grant authority. Unknown,
expired, restarted and status-only barriers preserve owner/epoch and every hold.
No report can assert qualified family quiescence; effective native handoff and
resumption remain unavailable.

The new real-mTLS/independent-DSS checks exercise fencing, a between-stage pause,
forged/invalid proofs, original binding and worker identity, role revocation,
expiry/dead worker, late report, concurrent accepts, lost/changed report replies,
audit rollback, restart and plaintext-secret absence. Agent checks reject family
proof inferred from main PAUSED and prevent repeating an admitted pause after
lost diagnostic delivery. The first focused attempt exposed the Context worker
route classifier still treating the new routes as preflight (404); the classifier
was fixed. One restart fixture used a nonexistent path attribute and was fixed.
The first full 289-test run also detected changed live-session error precedence
from grant-validation refactoring; existing effect-path precedence was restored.
Those failed JUnit records remain in local qualification evidence. The corrected
289-test run passed with zero failures/errors/skips; the final lost-reply case
is included in the subsequent candidate run below.

The separate hosted `--native-pause-probe` cohort must demonstrate the actual
native boundary: main B paused while its background thread counter still
advances, nine unrelated procedures complete, no owner/epoch changes, all holds
retained, bounded controller latency and explicit independent host teardown of B.
It is a negative safety qualification and never marks native_pause_qualified or
full_v08_qualified true. No native outcome is claimed before candidate-SHA CI.


Final local CPython **3.13.16** candidate qualification passed **290 scoped
tests**, zero failures/errors/skips, warnings as errors, with lint/format/mypy
passing. Evidence: `v08-server/run-20261023T191649Z-51403d96`, prior head ead1a5d
plus exact changed source hashes. This includes the lost-pause-report regression:
response loss reuses the recorded diagnostic without another native pause.
Offline wheel build and clean isolated installed **0.8.0.dev14** import/version
and both service/preflight CLI smokes passed. Hosted candidate-SHA audit, DSS and
new pause-probe outcomes remain pending; native family quiescence/live handoff
and full v0.8 remain unqualified.


## Confirmed hosted dev14 native pause negative boundary

Code **34f201da11318850e8fbe3aac5ee17e6ff403371**, PR merge checkout
**854955fcb447e4a59484bc4a5fe39ffa2208d9d4**:
[services/native run 40010794562](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794562)
passed all five jobs, including **290 scoped tests**, native-boundary, audit,
DSS and the new pause-probe cohort. The same code's
[portable compatibility run 40010794672](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40010794672)
passed **241 tests**, zero failures/errors/skips. Package build/install/CLI
smokes passed. All test attempts remain retained separately.

Artifact **12527050416**, ZIP SHA-256
`c02788c03babaf9a728a96da10bf4f2df774b2f849f2a59285654f40a6261bc3`,
was downloaded, CRC-checked and inspected. All **17 runtime source hashes**
matched the candidate. Ten real native procedures reached RUNNING, with thirty
distinct native Listener/Context/Executor PIDs. B's main Executor became
**PAUSED**, yet its background counter advanced **89 to 99**. The transfer
remained **UNPROVEN/BLOCKED**, preserving owner/epoch and all ten logical holds
and spent slots. Ten unrelated-controller reads had maximum observed latency
**0.01278221 seconds**. The other nine procedures finished and persisted their
start/finish lifecycle events; B persisted a start only (19 events total).
Independent host cleanup terminated B after evidence capture; it was neither
native completion nor runtime quiescence/reclamation.

The durable redacted receipt is
`evidence/native-pause-probe/qualification-summary.json`. This confirms that
main-status-only pause cannot authorize a live handoff and that the new Context
barrier fails closed without blocking other procedures. It does not fix the
native provider's missing whole-family barrier. The required correction is
native acknowledgment of participating threads/children plus control/prompt
queue draining, followed by explicit separately admitted new-owner resume
provenance. Positive native pause/handoff/resume, children, recovery and full
v0.8 remain unfinished/unqualified. Public runtime remains disabled.


## dev15 cooperative background Python component (candidate)

The opt-in thread component uses CPython 3.13 monitoring alongside the original
native debugger trace. It holds observed snapshot background threads at their
next monitored line, including late entrants. Bounded waits, original one-shot
identity/deadline, retained disappeared participants and monitoring failure do
not authorize resume or positive family proof. The original Context pause
contract stays unchanged. A new native matrix profile contrasts the original
counter-still-running negative probe with an acknowledged, stable-counter
component probe. Both must retain owner/epoch and all holds; nine unrelated
native procedures must finish. The published v0.7 image stays byte-identical;
only the explicit profile loads a candidate read-only host session/library.

Development attempts are retained in `.qualification/native-pause/`: the first
component run exposed test-snippet indentation (five failures/six passes), fixed
without weakening its real-thread assertions. The next run passed ten checks
and found this local environment denies AF_UNIX socket creation. The diagnostic
wire was implemented on private loopback TCP, consistent with the native helper
profile. All eleven real-CPython component checks then passed. Two worker-boundary
cases also verify that success or loss of this helper cannot promote the worker
report to whole-family quiescence. There is no helper resume action.

Offline dev15 wheel build, clean isolated import/version and both service and
preflight CLI smokes passed. Local scoped suite and candidate-SHA hosted outcomes
are recorded below once verified. Until then native thread integration is
pending; full family pause/handoff/resume and full v0.8 remain unqualified.

The first full local candidate run passed **303 scoped tests**, zero failures,
errors or skips, with lint/format/mypy and warnings-as-errors passing. Evidence:
`v08-server/run-20261023T194207Z-60e2de45`. A final worker refinement extends the
one-time local safety attempt to the cooperative helper on authority loss; the
final exact-source run is retained separately. Hosted native outcomes remain
pending.


The first hosted thread cohort at **6b178d0** failed its acknowledgment oracle
in [run 40014006886](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40014006886),
while native-boundary, audit, DSS and the original negative pause cohort passed.
Its retained artifact **12526799005** (ZIP SHA-256
`4e6ec00989849acfb5158ec49d34fe5159a0f1c519fb28c7106511291c4cb436`)
was downloaded and CRC/digest checked. It recorded two observed background
identities, one acknowledgment, deadline expiry and UNPROVEN main PAUSED; the
owner/epoch was not transferred. Investigation reproduced the specific bug
locally against the original candidate: resolving `<frozen os>` relative to a
snapshot working directory wrongly admitted a synthetic participant. The fix
requires an originally absolute filename before resolving the snapshot boundary.
A regression now runs with the native snapshot working directory and excludes
frozen, synthetic and relative code while requiring a real background thread to
acknowledge. It does not remove unknown participants by liveness or weaken the
barrier. Candidate-SHA native requalification is required below.


The corrected focused native-pause/component suite passed **40 checks**. The
full local run `v08-server/run-20261023T195114Z-0ba5a66d` passed **304 scoped tests**,
zero failures/errors/skips, lint/format/mypy and warnings-as-errors. The next
hosted thread cohort at **795874d** recorded exactly one observed background
thread, one acknowledgment, no expiry and original main PAUSED; it then failed
the host socket-inventory command. Its retained artifact **12527836953** has ZIP
SHA-256 `b54819b341eb07fb68ff95cc5a0abdc3d319064a71c3de194669a21b23e940f2`
(CRC/digest checked). The socket assertion was narrowed to LISTEN entries,
rather than including established/closing TCP records. CI path filters now cover
the new component and candidate host session. Neither failed attempt is claimed
as successful native integration; complete stable-counter/other-worker results
remain gated on the final candidate. The local 304-test evidence precedes that
small inventory assertion/CI-filter refinement; final exact-source qualification
is recorded separately.


## Confirmed hosted dev15 observed Python-thread component

Final exact-source local qualification
`v08-server/run-20261023T195458Z-9ebc93b4` passed **304 scoped tests**, zero
failures/errors/skips, lint/format/mypy and warnings-as-errors. Every recorded
source hash matched executable code **41a2fb2409f147b6b9bd018f1fe6f089f0eb71e2**.
The offline dev15 build and isolated import/version/CLI smokes passed.

At the same code, merge checkout **d32d9eb5676645548ae2d7110c8cd4cf47ef8b53**,
[services/native run 40015231877](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40015231877)
passed all **six jobs**: foundation (304 tests plus package checks),
native-boundary and audit/DSS/original pause-probe/new thread-barrier cohorts.
[Portable compatibility 40015231748](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40015231748)
passed **241 tests**, zero failures/errors/skips; full all-763 remains unqualified.

The component artifact **12527589091** (ZIP SHA-256
`b96c0324093d195d5d4d6b25d1b4da9601cbde580f17f9ea0a71e7f83acc557c`)
proved main PAUSED with the real background counter stable at **72 to 72**, one
observed thread/one acknowledgment and no expiry/failure. The original negative
control artifact **12528820448** (ZIP SHA-256
`2032617b5bf553ae92161973b08ec20c2d1ef93f3a19f76ce9d789b476716550`)
proved main PAUSED still leaves the counter advancing **62 to 81** without the
component. Both downloaded artifacts passed ZIP CRC/digest checks and all
**19 runtime source hashes** matched the candidate.

The component cohort had ten native Executors/thirty distinct native PIDs,
nine unrelated normal completions, nineteen durable lifecycle events, actual
loopback-only helper binding, unchanged owner/epoch and all ten logical
holds/spent slots retained. Maximum observed unrelated-controller read latency
was **0.014496056 seconds**. Independent host cleanup ended B after collecting
evidence; this is not native completion, reclamation or whole-family proof.
The durable redacted receipt is
`evidence/native-thread-barrier/qualification-summary.json`.

This qualifies the **observed snapshot background-Python component only**.
Native extensions/unknown participants, children and prompt/control/effect queue
settlement remain unqualified. Context refuses effective transfer and every
whole-family/runtime/full-v0.8 flag stays false. Next implementation is native
child admission plus family queue/effect settlement before any ownership CAS
and explicitly admitted new-owner resume. The PR remains draft and unmerged;
no tag, release or production deployment is authorized by these test results.


## dev16 full-release request, child authority and publication preflight

The latest owner request, **Qualify and release full v0.8**, supplies conditional
merge/tag/GitHub publication authorization once all mandatory gates pass. It does
not waive qualification or authorize production migration. RELEASE_READINESS.md
and RELEASE_GATES.json record the active request and exact pending groups.

The new optional child-admission authority uses original live parent identity,
consumption-winner proof, immutable arguments/mode/source binding and the same
canonical reservation namespace as top-level runs. Grant delivery/consumption is
single use, with no token recovery, replay authority or hold release. Schema 10
fences restart and older binaries. Native before-RUN integration remains absent;
all replies keep native_start_qualified false. The first focused attempt found
root-consume suffix classification incorrectly applying to child-consume and a
test using an integer file descriptor as a path (12 failed/13 passed). Exact
root-route matching and the fixture were corrected; 25 checks then passed. The
expanded checks include missing winner proof and parent-catalog rebinding.
Publication preflight cases reject partial native receipts, stale paired sources,
missing gates, tampering, development/dirty checkouts and hidden runtime changes.

Final local CPython **3.13.16** qualification passed **344 scoped tests**, zero
failures/errors/skips, lint/format/mypy and warnings-as-errors. Evidence:
`v08-server/run-20261023T202621Z-c7777e70`; all recorded source hashes matched the
candidate working tree. Earlier intermediate full run passed 341 before final
source/guard regressions. Offline dev16 wheel build, isolated installed family
module import/version and both service/preflight CLI smokes passed.

The requested full inherited diagnostic was interrupted after repeated failures
and errors. A bounded reproduction (`v08-full-release/inherited-bounded.xml`)
passed 16 and failed 3, first failures caused by missing historical Windows
child-arguments captures. This is not a completed full compatibility run or a
proved application regression. Historical proof needs the original immutable
sources and retained raw archive; current native changes need fresh qualification.
The 241-test portable subset remains separately scoped.

The publication preflight rejected the current development checkout with all
**eleven full mandatory gate groups unqualified**, development version and
uncommitted-source notices. It did not publish. Hosted exact-candidate scoped,
package/native component and compatibility outcomes are recorded when verified.
The child RPC suite is not native child execution or full v0.8 qualification.


## Confirmed hosted dev16 authority and failed full-publication qualification

Executable code **7d2ab39951e3e250aa5bbb43633641fbd5254a3c**, PR merge checkout
**39ad48dd59e48c2c1fb378da30a9b1d8cf1736a5**:
[services/native run 40020149313](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020149313)
passed all six jobs. Foundation passed **344 scoped tests**, zero failures,
errors or skips, including **28 child-authority cases** and **12 publication
preflight cases**, plus package build/install/CLI checks. The audit, DSS,
original negative pause, observed-thread and native-boundary jobs also passed.
[Portable compatibility 40020147843](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020147843)
passed **241 tests**, zero failures/errors/skips. Those are named subsets.

Foundation artifact **12529419483**, ZIP SHA-256
`27311f95e897a2405c203ba2dd8437dbea5c2be5a1b7898322558adda7653c80`,
was downloaded and ZIP CRC/digest checked. All **111 recorded source hashes**
matched the candidate. The receipt is
`evidence/child-admission/qualification-summary.json`. It explicitly keeps native
before-RUN child execution, native pause and full-v0.8 qualification false.

On the clean committed candidate, the publication preflight exited **1**:
**full_v08_qualified=false, eligible_for_publication=false**. All eleven mandatory
full gate groups remain unqualified and the package is a development version.
No uncommitted-source blocker remains on that assessment. The executed report
is `evidence/release-readiness/publication-preflight.json`; the bounded inherited
failure is separately summarized beside it. No native child was launched by the
new API tests and no mandatory gate was promoted by a green component workflow.
The latest verified published release remains v0.7. Full v0.8 publication is
conditionally authorized, but the requested qualification has failed and
substantial native/UI/deployment/recovery/security work remains. No v0.8 release
was created.

### dev17 native before-spawn child provider candidate

Adds a checked-source compiled Context launch gate, exact native peer process
identity, original-family admission/consumption and a separate hosted native
child cohort. The 22 new locally executable provider/RPC cases pass, including
all mode bindings, nested provenance, races, revocation and committed-but-lost
replies. An additional real Unix SO_PEERCRED/pidfd case is retained unchanged;
this managed local host rejects creation of AF_UNIX sockets with EPERM, so its
local result is a failure, not a pass or a skip. Hosted Ubuntu qualification is
required. No native child result or full release qualification is inferred from
these component checks. Prior dev16 hosted results remain historical exact-source
evidence, not verification of changed dev17 runtime code.

First dev17 hosted attempt at `08ec573` (PR run 40038718571) passed the
367 scoped checks, package smoke and the five existing baseline/native profiles.
The new child profile compiled all 74 Context translation units, reproduced the
frozen native composition and started ten roots through the checked native gate,
but timed out before observing children RUNNING. That job is failed, with its
original CI artifact retained (12537798253; ZIP SHA-256
`0cdb260c05bfba78ea5defe91663767504330e702e11232583fea1fe1831e546`).
It is not a positive child-start qualification. Follow-up adds direct native
start/peer-denial probes, strict receipt types, current authority checks before
visible-child RUN, bounded native log diagnostics and the required explicit
`spell.runtime.ARGS` import in the child fixture.

The `c4fb768` push child job (40039300726) exposed a startup notification race:
nine roots became ready; the tenth Executor was physically PAUSED but startup
waited for a PAUSED notification consumed by the runtime pump during an info
request. No child success is claimed. The follow-up installs that pump only
after `NativeSession.start()` has completed its own handshake. The failed ZIP
12537944717 was verified by CRC and SHA-256
`e81dc53fb5e1ec1282914398af1859d217c68457c8b7610365b9649b8e2f5d02`.
The same `c4fb768` PR native child run (40039305597) passed direct native GUI
unadmitted-root and same-UID Unix peer denial, then reached WAITING in the parent
without child RUNNING. Its ZIP 12538438420 passed CRC/SHA verification
(`e0e6a3cce648ac1c54c03ed77686e8650a5bdea1ba5b104d2fd2427610ac97a6`).
Follow-up records bounded before-spawn admission stages and retained child-state
counts to distinguish an authority rejection from native startup blockage.

At `45d187f`, all existing native jobs and 372 scoped tests passed; the new child
profile remained failed. Verified ZIP 12538728112
(`6981fecc659cfdc83cb59fc63c4e273f6c3e3ba0f8f1d5d580192ebbb76812f6`)
showed the original native before-spawn child request being rejected by the
provider's positive-only instance-number check, with zero child authority rows.
The original native `getInstanceId()` assigns `#0` to a first child. The validator
now accepts canonical zero-based suffixes and tests exactly-one admission for
that original format. No failed native run is relabeled as a pass.

Agent-memory hardening also requires non-dumpability before config/launch. Its
real subprocess flag test passes locally. This managed host denies even a
positive-control `process_vm_readv` against a test child, so the additional
before/after memory-read regression fails locally on the positive control and
must pass in hosted Linux CI. It is not skipped, and denial without a working
positive control is never counted as a security pass.

The `ed5c9de` child cohort completed all ten roots and ten admitted children,
observed forty simultaneous native PIDs, retained ten consumed child rows and
twenty logical holds, and denied both native GUI and same-UID peer bypasses.
Its final audit assertion failed: hidden automatic children do not traverse
original `callbackEventCall()`'s STATUS_LOADED branch and therefore do not emit
the same start event as visible children. The next harness checks this original
source behavior explicitly (root start/finish, visible-child start, every child
finish) and retains observed per-worker counts; no start event is fabricated.
The failed ZIP 12538963062 passed CRC and digest checks
(`a3653cdf0b3b92c9fe9fd81d58ef4822a290dbb766b243b494ba58f75e2a2d07`).

The same executable checkpoint's push DSS cohort failed on one original
SendCommand HTTP 503 under the ten-worker burst. No command retry was performed.
ZIP 12539241160 passed CRC and SHA-256 verification
(`edf0fdb0b34bd73956c9c4dc735b0ac9d3bbbea6ba3de86ce42ab4cddfd1f660`).
A follow-up adds durable bounded failure categories to the private Context
ledger and a real mTLS held-resource regression: busy denial produces no binary
intent/effect, records the reason and retains replay denial. Failure diagnostics
must establish the bottleneck before any timeout/admission policy is changed.

At **b644d56223f0a859819c19afef0f5f5b1d18a06e**, all six native component jobs
in push run [40041544143](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40041544143)
passed, including the new before-spawn child cohort. It completed ten roots and
ten automatic blocking children (five visible/five hidden), verified forty
native PIDs, original argument transfer, native GUI/peer bypass denial and
physical spent-grant clone denial, and retained ten consumed child admissions,
ten spent workers and twenty logical holds. Thirty-five actual lifecycle EV
receipts match the original visible/hidden distinction. The child ZIP digest
`b656651a7970af562a23884fd58448e4e71548388c37ac19e42fc0a6792a0a8a`
and CRC were verified, and all 23 source hashes matched that commit. The
[redacted receipt](evidence/native-child-start/qualification-summary.json)
contains counts, public source hashes and qualification limits only.

The same push's foundation suite hit the runner's 180-second limit; the overall
workflow is failed, not green. Artifact 12539822036 has ZIP digest
`c064242a9921ed34109f8037d388e00d19a6876d7f29035a6498207c3ea4c63d`.
The follow-up allows 300 seconds for the expanded suite, keeps lint/type budgets
unchanged, retains partial logs and exit 124 on timeout, and never marks such an
attempt passed. Service/effect/transport timeouts are unchanged. Two actual
subprocess regressions verify timeout and nonzero-exit failure retention.
A separate real mTLS/DSS regression runs three ten-request bursts, checks thirty
commands and 150 ACKED stage rows in each independent ledger, and does not retry.
These three new local regressions passed; hosted full-suite results remain
required. All full release gates remain unqualified.

Final local scoped run before the metadata-reader correction passed **377 tests**
with warnings as errors and deliberately deselected the two Linux controls this
managed host cannot execute (Unix peer/pidfd and positive-control cross-process
memory read). Those two remain mandatory, unskipped in hosted CI. The new fixed
metadata endpoint tests then passed **3/3**, and the driver/effect regression run
passed **74 tests** before the final HTTP-error-close addition. These are explicit
subsets, not a completed all-382 result.

The security review found that inherited urllib metadata reads could follow a
DSS redirect or environment proxy away from the operator-owned endpoint. The
private v0.8 adapter now refuses both, limits metadata paths to state/telemetry,
and closes HTTP-error responses. Actual HTTP peer tests confirm no request to
the redirect target/proxy or unlisted path and no success for a closed 503
response. Published v0.7 transport bytes remain unchanged. Hosted exact-source
CI, including the new 300-second scoped-suite budget and these regressions,
is required before treating the final candidate as verified.

At **39ce43c7f0b9d8ce90f4789e62f27fc26a4c0b3e**, hosted push
[40043463719](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40043463719)
and PR [40043468765](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40043468765)
passed all seven services/native jobs. The expanded foundation suite completed
**382 tests**, zero failures/errors/skips, lint/format/mypy, isolated dev17 wheel
installation/version and service/preflight CLI smokes. This includes the actual
same-UID memory-read positive control and subsequent protection denial, Unix
peer/pidfd tests, metadata redirect/proxy denial, three ten-command mTLS bursts,
all original driver/effect checks and the native child cohort. These are scoped
component checks; no full v0.8 gate is promoted.

The next candidate adds a separate native Listener-survival cohort. It uses a
real read-only observer through an independently pinned edge/Listener/Context
path, kills and recreates the Listener process, checks continuing native counters
and unchanged thirty PIDs, and compares Context incarnation, owners, epochs,
generations, holds and spent slots. The Listener has no host manager or authority
volume. This is a new test awaiting actual hosted execution, not a recorded pass;
it does not qualify controller disconnection, recovery, browser/WSS or production
deployment. Existing private native profiles remain separate.

At **56439d763074e8e62be0457a57286c6b10639444**, push
[40044575533](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40044575533)
passed all eight services/native jobs and all **382 scoped tests** with zero
failures/errors/skips. Foundation archive digest
`267868148fa551f6bef8a9f2d3fd5522a1bd62abf01ead2c5c6ec3c655a365d8`,
CRC and all **119** repository source hashes were verified. The
[redacted foundation receipt](evidence/native-child-start/foundation-summary.json)
also records the distinct failed PR attempt below.

The new Listener cohort passed in both push and PR runs. It killed the actual
Listener and recreated a distinct process/container while all ten native
procedures advanced, thirty native PIDs stayed unchanged, and Context process,
incarnation, owners, epochs and generations remained identical. Ten logical
holds and ten spent workers remained. Worker-as-edge impersonation was denied.
The Listener had no host manager or authority volume. The push Listener ZIP
digest `b77d996210abad1f5d8b149a2daaca083df0f4298bf7632a014200a6797705e0`,
CRC and all **24** source hashes were verified; the
[redacted receipt](evidence/listener-survival/qualification-summary.json) contains
counts, public source hashes and explicit limits. This is read-only observer
survival, not active-controller disconnection, native recovery or full services
qualification.

PR [40044579825](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40044579825)
passed all seven native jobs but its foundation suite had **381 passes and one
failure**, `test_twenty_duplicate_rpc_calls_produce_one_real_command`: one 200
and sixteen 409 responses were observed; the previous assertion discarded the
remaining three denial statuses/error codes. Archive 12540783103 digest
`0693f6a2a09c29a49d08c066b76cb6521511c2412e8a91fd9cdcba397c51fb02` and CRC
were verified. No all-green PR result is inferred. The follow-up retains bounded
status/error-code diagnostics while preserving its one-success/nineteen-replay
assertion and no-retry behavior. A local focused rerun passed, but cannot explain
or override the failed hosted attempt. The cause remains under investigation.

The next native child candidate extends that existing cohort with one visible,
automatic blocking grandchild under child 0. The trusted host opens a separate
start barrier only after all first-level children are running, requires a second
distinct child-running observation in that worker and **41** simultaneous native
PIDs, then checks eleven consumed child admissions, one consumed same-family
parent link, twenty-one logical holds and thirty-seven original EV receipts.
Generated procedure sources compiled and 27 local provider tests passed (the
managed host's Unix peer control was deliberately deselected, still mandatory
unskipped in hosted CI). This new nested native cohort awaits hosted execution;
no nested or full-family pass is claimed from source/provider checks.

At **9bbae553b863b40129111f2d904a5cdf33891706**, all seven native jobs passed
in push run 40045545732 and PR run 40045550149, including the expanded nested
cohort. It verified **41 native PIDs, eleven consumed admissions with one correct
consumed same-family parent link, 37 original lifecycle receipts, 21 retained
holds and ten spent workers**. ZIP digest
`1459a71a6ab2cbd8c1561c3260fe7716e64efd778b7fcbd7b1a17c8ec2869618`, CRC and
all 23 repository source hashes matched. See
[evidence/native-child-start/nested-summary.json](evidence/native-child-start/nested-summary.json).
Only one visible automatic blocking grandchild is qualified; manual, nonblocking,
error/prompt/return/repeat, full-family handoff/resume and recovery remain pending.

Both foundation attempts at 9bbae55 failed the ten-independent-effect test before
any command effect: the metadata reader's one-slot admission queue exceeded its
250ms budget. The PR archive 12541003473 digest
`2b9f706c7a307601c7daece15a855069f23308fa435d372eb7c8b24e93c8d66f` and
push archive 12541097738 digest
`dc519337203b86f832a131e5b4bb3c14498f631973a40c59c2f1d4ce1dc0a19c`, plus both
CRCs, were verified. The duplicate-driver assertion passed in these attempts;
its earlier differing denials remain unexplained, not presumed fixed. The
follow-up allows three concurrent metadata reads against the fixed DSS API's
four configured handlers, preserving one handler for independent observation.
Queue/socket/effect deadlines, replay denial and exact test expectations remain
unchanged. Hosted load qualification is required; this change is not yet a pass.

The same next candidate adds the installed pinned IDE observer through a
separate actual gateway to the native Listener-survival cohort: exact installed
client hash/version, discovery and unchanged execution identities before/after
Listener replacement, explicit 503 during outage, control denial for the read-only
user and no reconstructed controller proof. This is pending hosted execution;
it cannot qualify native IDE Run/Debug, Qt/browser controls or full v0.8.

At **d523c96b4636c51dedf62a62563469e0de20982e**, the installed pinned IDE native
observer passed hosted Listener jobs in both push 40045966181 and PR 40045970114.
It used the actual installed client (version/hash checked), a separate gateway,
Listener and unchanged Context. It observed ten actual native executions, was
denied control, received 503 while Listener was absent and reconnected to the
original execution identities with no controller proof. All ten native counters
advanced through outage, thirty PIDs stayed unchanged and ten holds/spent slots
remained. The push artifact 12540868163 digest
`a991dd80314dd3c25b56e3b49370c30ee62d830614fc7ffb911b0b17b63abcfb`, CRC and
all 24 source hashes were verified. See
[evidence/listener-survival/ide-observer-summary.json](evidence/listener-survival/ide-observer-summary.json).
Native IDE Run/Debug, active-controller disconnect and full v0.8 remain unqualified.

The final local scoped suite at d523c96 completed **380 tests, two deliberately
deselected Linux positive controls**, zero failures/errors, warnings as errors.
Those controls remain mandatory/unskipped in hosted CI. Ruff and mypy passed.
Clean full-publication preflight exited **1** with all eleven full groups false
and the package still 0.8.0.dev17; no publication occurred.

Final executable candidate **d523c96b4636c51dedf62a62563469e0de20982e** passed
**all eight services/native jobs in both push 40045966181 and PR 40045970114**.
Both portable workflows 40045966101/40045970135 also succeeded. The foundation
suite completed **382 tests, zero failures/errors/skips**, lint/format/mypy and
isolated installed package checks. This includes unchanged strict replay and
ten-independent-effect assertions after the bounded metadata concurrency fix.
PR foundation artifact 12541695642 digest
`78e07b565e46b83eeb3f8873a3ed1feb23b7666594a4b54d713ba6152cc3bf36` and CRC
were verified, and all 119 public source hashes matched d523c96. See
[evidence/native-child-start/dev17-final-foundation.json](evidence/native-child-start/dev17-final-foundation.json).
These results qualify the stated development components only. All eleven full
release groups remain false; public runtime remains disabled.

## dev18 bounded concurrent command admission (in progress)

Latest evidence-head PR run 40046331677 retained a failure at
`test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss`: two
requests returned 503 with durable `native_driver_resource_busy` categories.
Push run 40046325660 and all seven native jobs in both runs passed. The failed
PR foundation archive 12541263559 digest
`ee9dd2354ec97fa5f8f8f2fadf4840af352bca83c195f8cfbe19e9b035c757b5` and CRC
were independently verified. That failed run is not replaced by earlier green
results. This is a distinct command-resource wait bottleneck, after the earlier
metadata admission correction.

A deterministic regression holds actual TRANSPORT sends before receipt reads.
Before correction, only one of ten calls reached this point; the test failed.
The private simulator adapter now permits at most ten independent command
streams (below DSS's sixteen TCP handlers), with immediate capacity denial.
It retains original per-operation identities, per-stage authorization under the
execution mutex, separate durable ledgers, bounded deadlines and no replay.
The normal case requires all ten real streams to reach the receipt barrier,
the eleventh request to produce no effect, and exactly five ACKED rows for each
accepted operation in both ledgers. A second case fences control while all ten
receipts are pending: no call may progress beyond TRANSPORT or execute a command,
all call outcomes remain uncertain, and original owner/epoch/holds are retained.
No native handoff success or full release gate is inferred. Hosted dev18
qualification is pending.

Local dev18 validation: **74 driver/effect tests passed**, including both new
actual-send/receipt-barrier cases. Full scoped local run: **382 passed, two
explicitly deselected host-incompatible Linux positive controls**, warnings as
errors, zero failures. Hosted CI retains both controls unskipped (384 total).
Ruff format/lint, mypy over fifteen server files, dev18 wheel build, isolated
installed version match and service CLI smoke passed. No hosted dev18 result is
claimed yet.
## dev18 exact-source hosted completion and dev19 native control work

Runtime commit `14642765fb5642600d5525105f57d0a6b8bccb1d` passed all eight
services/native jobs in PR run 40112024277 and push run 40112020263. Portable
runs 40112024274 and 40112020176 passed. PR foundation completed **384 tests,
zero failures/errors/skips**, plus lint/format/types and installed package smokes.
Artifact 12567297002 SHA-256
`233adecaf6f5ce60e72acfcf3b32e9a05d332e2cc9c376cfe91227fc036a680a`, its ZIP
CRC and all 119 public source hashes were verified against that runtime commit.
The redacted receipt is
[evidence/native-child-start/dev18-final-foundation.json](evidence/native-child-start/dev18-final-foundation.json).
This validates the bounded independent-command correction; full v0.8 is still
unqualified, including all-763 compatibility and deployment qualification.

The dev19 candidate adds the explicit private native RUN journal described in
[NATIVE_CONTROL_JOURNAL.md](NATIVE_CONTROL_JOURNAL.md). Twenty-five focused tests
pass over actual mTLS, including lost replies, competing admissions, a fence
between admission and IPC, and restart retaining uncertainty/holds. Initial
focused execution exposed missing fixed client routes and a restart-fixture
error; both were corrected. The subsequent focused suite, lint/format and mypy
passed. Hosted native and final full-suite results remain pending for dev19.

The first dev19 full local run retained **406 passed, one failed, two deselected**:
the existing 100-way child-admission test had one winner but only 91 of 99
expected conflict responses. The other eight status/error pairs were not retained
by the old assertion, so no cause is claimed. The assertion now records bounded
status/error counts without changing one-winner/ninety-nine-conflict requirements.
Ten isolated repetitions passed; the full confirmation run then passed **407
tests, two deselected**, warnings as errors. The two managed-host-incompatible
Linux positive controls remain mandatory and unskipped in hosted CI (expected
409 tests). This intermittent original anomaly remains an open qualification risk.
The final strengthened 25 journal tests passed again, including checking the
committed uncertain row before the native send boundary. Ruff/format/mypy passed;
the dev19 wheel built and its isolated installed import/version/CLI smoke passed.
Hosted dev19 native execution and exact-source CI remain pending.

## dev19 hosted evidence and dev20 telemetry admission correction

At **ec9ad5d94022a8915970f0e5ac5c5c2a44e11f60**, push run 40113822680 passed
all eight services/native jobs. PR run 40113825594 passed seven jobs, including
foundation (**409 tests, zero failures/errors/skips**) and the native child cohort,
but failed the DSS cohort. Portable PR 40113825595 passed. Foundation artifact
12567672711 digest
`d1287126cfc78bea43ad02e2a40eac4f57ff948e9fab03c2d0a29fbf8982d7c9`,
CRC and 122 source hashes were verified. Child artifact 12567304316 digest
`d62f544d7936e2ba3a8028d479a927fd2ba423f7564b50233c667bfac86abefa`,
CRC and 25 hashes were verified. Ten workers recorded sixteen original agent
RUN attempts, with six correct consumed child bindings; every IPC acknowledgment
remained uncertain and no family transfer was authorized.
See [foundation](evidence/native-child-start/dev19-foundation.json) and
[child journal](evidence/native-child-start/dev19-child.json) receipts.

The failed PR DSS artifact 12567532971 digest
`fb20c26abb841169572f9df931c619b50012ab6f4094e99ccdfe24ad6f9ea9bc`,
CRC and all 90 source hashes were verified. One TM/RefreshItem call encountered
RemoteDisconnected: 49 driver calls completed, one stayed UNCERTAIN, and all 50
command-stage receipts were ACKED. The affected native procedure failed; the
successful push run does not override this failure.
[Redacted failed-run receipt](evidence/native-context-dss/dev19-failed-telemetry.json).

Inspection found that the three-reader metadata limit covered current_state()
but inherited sample() called get(telemetry) directly. Two deterministic
regressions fail against dev19: ten inherited samples exceed the reader limit at
the actual four-handler HTTP boundary, and a saturated metadata budget still
permits HTTP. Dev20 moves the unchanged three-reader/250 ms admission budget into
get(), so initialization, state and telemetry share it. No deadline, handler
capacity, command receipt rule or retry behavior changes; the legacy transport
and original patch preimages remain unchanged. Both regressions and the complete
79-test metadata/driver/effect group pass after the change. Full local and hosted
dev20 qualification remain pending. This evidence establishes the admission gap;
the hosted disconnect's exact server-side interleaving was not captured.

The final dev20 local suite passed **409 tests, two deselected**, warnings as
errors (166.68 seconds). Ruff/format/mypy and the built, isolated installed dev20
wheel import/version/CLI smoke passed. Hosted CI must run all **411** checks,
including the two Linux positive controls, and the real native DSS cohort.

## Verified dev20 executable checkpoint

Executable **a9c9bb17c4b68e9a53b79f6263ac93f44f0a6695** passed all eight
services/native jobs in PR run 40114793223. The foundation suite passed **411
tests, zero failures/errors/skips**, plus lint/format/types and installed package
checks. Both portable runs 40114793208 and 40114789291 passed. The push native DSS
job passed; final push foundation/child statuses were still in progress at this
checkpoint, so no all-green push claim is made.

PR foundation artifact 12568097164 digest
`a16f1659bb3387905198cb406cba8adf62c24e48229bc3501dbaaf46453968cb`,
CRC and all 122 source hashes were verified. Native DSS artifact 12568435398 digest
`5cf9bc8043cbd9cd3bf4eb9dba5f9f63ff39778082421bf25449384d3e1b3305`,
CRC and all 90 hashes were verified. Its 50 driver calls completed with no
recorded failures: ten commands, ten refreshes and fifty matching ACKED stages
in each authority/driver ledger. Ten workers terminated with ten logical holds
and spent slots retained. Copied-original-config command denial remained active.
See [foundation](evidence/native-context-dss/dev20-foundation.json) and
[native DSS](evidence/native-context-dss/dev20-dss.json) receipts.

The original strict 100-way child-admission race also passed fifty fresh-state
repetitions (38.43 seconds): 5000 admission attempts, 50 winners, 4950 conflicts.
The earlier eight unclassified responses remain unexplained. This stress result
is not evidence that their cause was repaired.
[Reproduction harness and counts](evidence/native-child-start/dev20-race-stress.json).

Clean full-publication preflight still exited **1** with all eleven full gate
groups false and development version 0.8.0.dev20. No merge, tag, release or
production migration occurred.
[Publication preflight](evidence/release-readiness/publication-preflight-dev20.json).

These evidence-only changes preserve all 122 hashed foundation inputs and all
90 native DSS inputs of a9c9bb1. They are saved on a separate qualification branch
to preserve the still-active push validation. Full-family native handoff/resume,
joint native IDE Run/Debug, all-763 compatibility, deployed Compose/Kubernetes
faults/recovery and final security/release acceptance remain incomplete.

Final follow-up: push services/native run **40114789340** completed successfully
at the same a9c9bb1 executable commit. Both PR and push now pass all eight
services/native jobs and both portable workflows pass. The evidence branch can
be integrated without cancelling the original validation. All full-release
gates remain false; no additional runtime functionality is inferred.

## dev21 bounded execution admission correction

The unchanged executable code at documentation head 6e5cecb had another failed
PR foundation run, **40116162199/job 120937765044**: 411 tests, one burst failure,
ten HTTP 500 responses. All seven native jobs and the push workflow passed.
Artifact 12568851330 SHA-256
`2aad062856f053e03041c8ec752cdf609dc811ffcb6a275401a4ac9c58495812`,
CRC and all 122 source hashes were verified. The failure remains retained in
[the redacted receipt](evidence/native-context-dss/dev20-documentation-head-failure.json).

Type-only exception diagnostics reproduced execution_busy in local strict burst
stress: the diagnostic-only source failed repetition 9, and FIFO alone failed
repetition 28. Dev21 adds bounded FIFO admission (64 waiters, the same 250 ms
deadline) and removes redundant execution-mutex admission from identity-only
reads. Each read still uses one consistent state transaction. Mutations and
every actual send retain their final original-grant check and execution mutex;
reads are not effect permits. No socket, metadata or effect deadlines were
increased and no retries were added. The failed hosted run's original exceptions
were not captured, so its precise interleaving is not claimed to be known.

FIFO plus snapshot reads passed 30 fresh-state repetitions: **900 commands,
4500 ACKED stages in each ledger**, unchanged exact success/count assertions.
[Harness, counts and source hashes](evidence/native-context-dss/dev21-burst-stress.json).
The 72 focused authority/driver tests passed. Full local suite: **416 passed,
two deselected**, warnings as errors, 161.68 seconds. Those Linux controls remain
mandatory in hosted CI (418 expected tests). Ruff/format/mypy and isolated dev21
wheel install/import/version/CLI passed. Tests cover non-owner release, cancelled
head, interrupted wait, bounded queue, no barging and real mTLS identity checks
while another action owns the stage lock, followed by post-disconnect rejection.
Exact-source hosted dev21 results are pending; no full gate is promoted.

## dev21 hosted completion; dev22 native before-forward candidate

Runtime **0d31c4905be4b74702b95a566bb07d99cabc6b1a** passed all eight jobs in
both PR 40119871531 and push 40119867008; both portable runs 40119871566 and
40119867010 passed. Foundation completed **418 tests without failures/errors/skips**.
Artifact 12571330675 SHA-256
`e9867abee05118c9f725294802d751b4cb340936fac913d5daf52de7261b3f2d`,
CRC and 124 source hashes were independently checked.
[Receipt](evidence/native-context-dss/dev21-foundation.json).

Dev22 adds a real native Context hook before Executor IPC forwarding. A RUN
message carries the original journal UUID; the native Context authenticates
the owned agent over the existing Unix helper and receives one-shot live
admission through pinned worker-to-Context mTLS. Unknown/replayed IDs or changed
targets never forward. Lost admission responses cannot retry; schema 12 retains
FORWARD_UNPROVEN and fences it on restart. The authenticated helper remains
bounded; no host socket, privilege or new grant is added. The original Executor
queue and other mutation paths are not yet fenced by this component.

The native child cohort must prove sixteen forward rows with identical original
journal identities and ten actual unregistered-RUN probes. Each probe bypasses
the Python wrapper, requires native callback denial and verifies that the
Executor remains PAUSED before legitimate execution. This is an isolated
audit/compute profile; it cannot dispatch satellite commands. Exact native
Context source reproduction and the 74-unit build remain mandatory in CI.

Local: **58 focused checks passed, one hosted-only peer control excluded**;
full suite **422 passed, two deselected**, warnings as errors, 196.11 seconds.
Both Linux controls remain mandatory in hosted CI, for 424 expected tests.
Ruff/format/mypy and isolated dev22 package install/import/version/CLI passed.
Hosted native compilation and before-forward positive/negative evidence are
pending. Neither forwarding admission nor IPC acknowledgment qualifies native
dequeue, family quiescence, handoff/resume or full v0.8 release.
