# v0.8 development changelog

## 0.8.0.dev55 — controller/network fault boundaries and native spawn

- Add seven real TLS recovery cases covering committed close/rebind/activation reply loss, killed controller client and unreachable TLS. Require old-grant fencing, bounded observer reads, retained holds and no automatic resume/replay. Host proof remains an explicit fixture; abrupt-loss liveness detection remains unimplemented.
- Replace frozen composed native fork/exec with posix_spawn; preserve parent/child identity, shell/environment/descriptors and the ported termination-signal policy. Nine compiled checks reproduce an inherited callback stall and verify preserved behavior. Add bounded native admission phase timing.
- Retain the initial wrong-source build failures and full-suite failures, plus the second stale-count/diagnostic-assertion and in-place epoch writer failures. Correct the source preimage, signal policy and test inventories without relaxing deadlines or assertions about authority.
- Exact `81b8b41` passes 1,210 service tests, 71 overlapping fault probes, 241 portable tests, fourteen core jobs and five ancillary workflows. Nineteen archives/source inventories are verified. Historical causes and all eleven full-release gates remain open. See [controller/network recovery](CONTROLLER_NETWORK_RECOVERY.md), [native spawn](NATIVE_SPAWN.md) and [the receipt](evidence/controller-network/qualification-summary.json).

## Dev54 qualification follow-up — DSS lifecycle and independent execution faults

- Add eighteen cases covering process death, connection cut and reply stall after every DSS stage commit, same-database restart, scenario reset and nine independent grants beside one uncertain execution. Both old and new request keys stay denied for uncertain outcomes; exact ingress counts expose hidden replay attempts.
- Correct unclosed SQLite evidence readers in the new test harness and reap failed subprocesses. Keep the failed initial artifact, original JUnit/logs and local reader regression; warnings remain fatal. Production runtime stays unchanged from `1182388`.
- Candidate `f1ea033` passes 1,193 service tests, 55 overlapping fault probes and 241 portable tests. Twelve of fourteen core jobs and five ancillary workflows pass. Native terminal/startup preambles fail; retain their five affected-worker traces and keep the overall candidate blocked. All nineteen archives/source inventories, including failures, are verified. [DSS lifecycle report](DSS_LIFECYCLE.md). Historical causes and all eleven full-release gates remain open.

## 0.8.0.dev54 — controlled faults and native deadline enforcement

- Reject native readiness and complete ALLOW replies consumed after the original deadline. The compiled pipe regression fails before the correction; production admission retains its four-second budget and adds no reconnect or request replay.
- Add real mTLS/SQLite/DSS fault injection for writer/commit delays and delayed/lost receipts, plus compiled Unix client reply loss after durable Context binding. Native binding peer roles/process pins remain explicit fixtures. Uncertain outcomes retain holds and deny original-key and new-key retries.
- Fix prelaunch readiness checking only Context A: require both A and B within one existing 65-second budget. Keep TLS pin failures immediate. Align Docker/Compose/Kubernetes markers with dev54 and add package-version consistency coverage. Preserve the original kind HTTP 503 failure and fail-before/pass-after results.
- Exact candidate `1182388` passes 1,175 service tests, 37 overlapping fault probes and 241 portable tests; fourteen core jobs and five ancillary workflows; nineteen verified artifact archives and their recorded source hashes. IDE remains pinned to `1ac0b8a` / `1.2.1.dev4`. Historical DSS/startup causes and all eleven full-release gates remain open. See [the fault report](FAULT_REPRODUCTION.md).

## 0.8.0.dev53 — bounded DSS command diagnostics

- Retain the dev52 native terminal failure: ten uncertain command calls and twenty ACKED stages before child admission. Other twelve core jobs, 1,144 service tests and four ancillary workflows pass; no all-green checkpoint is inferred.
- Record fixed phase/stage labels and bounded numeric timings on failed commands, plus per-stage ledger counts. No payloads, credentials or exception messages are recorded. Existing deadlines, live authority checks, durable ledgers and no-replay behavior remain unchanged.
- Five deterministic timing/failure-path tests pass locally; the historical timeout cause remains unestablished. Exact candidate `d01fc30` passes 1,149 hosted service tests, 241 portable checks, thirteen core jobs and five ancillary workflows; all eleven full-release gate groups remain false. The initial 300-second full-suite harness stopped after 1,003 passing progress markers with no failed/error marker and no final JUnit; its failed artifact is retained. The finite suite budget is now 600 seconds with a 15-minute job budget. Individual operation deadlines and assertions are unchanged.

## 0.8.0.dev52 — completed session cleanup

- Fix Disconnect after native reconnect when the original session is already closed: require the original authenticated subject, current permission, inactive state and durable original close receipt before acknowledging a fresh cleanup request. Never repeat fencing or complete a pending close under a different key.
- Preserve dev51 hosted evidence: 1,141 passing tests and one failed Qt Disconnect assertion. The same integration test remains mandatory unchanged. Two local regressions fail before the repair; 106 authority/contract/control tests pass afterwards, including pending-close recovery across restart. The unchanged Qt integration test now passes among all 1,144 hosted service tests. The separate native terminal cohort failed on ten DSS command timeouts; twelve other core jobs pass.

## 0.8.0.dev51 — desktop reconnect session repair

- Pair IDE 1ac0b8a / 1.2.1.dev4. A cached stale controller proof no longer hides explicit reconnect after a server disconnect. Live reconnect uses a fresh session. Other execution sessions remain available until explicit Disconnect closes every known session with stable per-session close keys.
- Add actual Qt-panel / Gateway / Listener / Context TLS integration coverage for reconnect, paused rebind and explicit resume admission. Native process/freezer evidence remains separately required.
- Local 51-case IDE client/panel suite passes; three pre-fix regressions retain their failures. The complete paired IDE workflow passes 272 tests with one Windows-only skip; the final dev53 native/component recheck also passes. No full release gate is promoted.

## Development package 0.8.0.dev50

- Fix the reproduced signal-interruption failure in native admission waits. Continue only the original socket/packet offset, within the original four-second deadline; retain fail-closed peer identity, lost reply and denial behavior.
- Add compiled transport regressions and bounded phase/timing diagnostics. All thirteen core jobs, 1,141 hosted tests and four deployment/inventory workflows pass at `e519882`; no full-release gate is closed.
- Retain the dev49 follow-up failure: two children were bound server-side but the native peer closed before ALLOW. The historical cause remains unproven. See [NATIVE_ADMISSION_CHANNEL.md](NATIVE_ADMISSION_CHANNEL.md).

## Development package 0.8.0.dev49

- Preserve the original unanswered zero-timeout native prompt across host-proven handoff; require a fresh owner reply after explicit resume.
- Validate reply controller fields against the current runtime grant while retaining the original family/member/definition identity. Keep timed/unclassified prompts and queued/uncertain replies blocked.
- Carry prompt replies through the pinned installed IDE's authenticated request transport and the private Listener authority operation. Preserve certificate identity and live permission/ownership checks.
- Verify 1,119 hosted service tests, all thirteen core jobs and four deployment/inventory workflows at `dc66d32`. Retain four failed intermediate artifacts and the corrected consumed-versus-selected qualification assertion.
- Keep all eleven full-release gates false. See [NATIVE_PROMPT_HANDOFF.md](NATIVE_PROMPT_HANDOFF.md) and [RELEASE_READINESS.md](RELEASE_READINESS.md).

## Development package 0.8.0.dev48

- Drain in-flight agent transport before independent host freeze, fixing the
  retained captured-query and interrupted-TLS handoff failures. Preserve
  one-shot activation and fail closed after a lost activation reply.
- Preserve primary qualification failures separately from cleanup errors;
  retain bounded admission error categories and live state after failed removal.
- Qualify twenty distinct installed IDE observer identities across Listener
  loss with ten advancing native executions and thirty unchanged native PIDs.
- Build/load kind image tags from the manifest renderer, fixing the dev47/dev48
  mismatch; retain bounded workload status before cluster deletion.
- Verify 1,094 service tests, thirteen core jobs, sixteen terminal cases,
  twenty-four fresh startup/settlement cycles and four deployment/inventory
  workflows at `40f38fb`. Historical startup causes and all eleven full-release
  gates remain unresolved. See [TEST_REPORT.md](TEST_REPORT.md) and
  [RELEASE_READINESS.md](RELEASE_READINESS.md).

## Historical planning baseline

* Start `feature/v0.8-server-architecture` from latest remote master, including
  the merged v0.8 requirements, while preserving published v0.7 and local edits.
* Audit actual v0.7 service/worker/driver boundaries and distinguish session-wide
  durable control from local per-procedure ownership.
* Collect current GitHub metadata, source inventories, legacy manual references,
  37 passing baseline regressions and one installed native/DSS process trace.
* Propose ADRs, per-execution consent/fencing protocol, static Compose workers,
  K8s Jobs, isolation/recovery policy and mandatory acceptance gates.
* Add editable as-is/target/legacy diagrams and a reviewable architecture package.

No v0.8 production implementation, release or schema migration yet.

## Approved G1 resolutions and initial C/D foundation

- Record independent findings F1-F10 and owner authorization; bind worker
  incarnations, transfer barriers, actual-send ordering, single-use workers,
  mandatory admission and the supported authority storage profile.
- Add separate internal Listener/Context package with TLS 1.3, certificate pins,
  scoped RPC, Context ACLs and durable blackboard CAS. Execution is disabled.
- Add 51 local Python 3.13 foundation tests, failure evidence, package smoke and
  hosted foundation CI. Full runtime/deployment/release gates remain pending.

## Development package 0.8.0.dev2: durable prelaunch authority

- Add bounded transactional logical reservations, explicit connection bindings,
  per-execution claims/consent, owner-only rebind and secret-free replay.
- Add immutable controller-origin start admission and one-time worker consumption
  as private integration seams; no worker RPC or native launcher is exposed.
- Serialize prelaunch transfer against consumption; block post-consumption
  transfer/rebind, preserve holds and fence grants on restart.
- Add concurrency, denial, response-loss, audit/storage and process-death tests.
  Source/image declarations are not verified inventories. Native/driver/browser/
  Compose/Kubernetes and full compatibility gates remain pending.


## Development package 0.8.0.dev3: approved sources and worker preflight

- Build bounded canonical source manifests from exact verified Git objects;
  bind aliases, revision, image and driver metadata to operator-approved policy.
- Add registered single-host worker certificate roles and durable challenge/verify
  preflight, with original-binding, expiry, replay, capacity and restart fencing.
- Add a non-executing worker CLI that verifies its actual source directory using
  no-follow descriptors; reject changed/extra/missing/link/special source files.
- Guard private Context start admission and consumption on verified preflight.
  Native launch/consume/driver routes remain absent; Kubernetes identity, image
  and mount attestation, native/driver/browser/deployment gates remain pending.
