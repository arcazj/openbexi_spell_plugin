# v0.8 ordered implementation and acceptance

This is the user's approved implementation order. No stage is waived, renamed
as complete, or replaced by a component test. RELEASE_GATES.json remains the
full-publication authority; all its mandatory checks remain unchanged.
Production migration is not authorized. Frozen v0.7 remains untouched.

## Fixed source pair and integration discipline

Stage 1 branch: work/v0.8-stage1-native-lifecycle, based on plugin
466b7bf5b654514798c4e3ea166ff529767c54e7, paired with IDE
 dd06fe91d9da9cad828ff659adced0e3be80816d (the existing IDE_PAIR.json).
Only explicitly reviewed, source-bound batches are integrated. Formatting,
lint, types, focused regressions and paired regressions precede promotion.
No temporary repository-writing formatter is used. Stage 1 CI is read-only,
retains failed evidence and does not cancel an in-progress candidate.

## Mandatory order (current stage: 1)

| Stage | Required implementation and executed acceptance | State |
|---|---|---|
| 1. Single-owner native lifecycle | Original native startup, RUN, PAUSE, STEP, exact prompt answer, explicit resume, normal finish, authorized abort and error handling; no orphaned work or unsafe reuse; investigate the unresolved LOADED timeout with recorded evidence. | IN PROGRESS |
| 2. Safe ownership transfer | Complete participant inventory, child-start closure, pending/deferred command and prompt outcomes, driver-effect settlement, atomic owner/epoch change, original-provenance preservation and fresh new-owner runtime identity. Prove the A/B/C scenario below and refuse uncertain transfers. | BLOCKED BY STAGE 1 |
| 3. Installed IDE and three user modes | Qualified native Run/Debug through installed openbexi_ide plus plugin; read-only monitoring; development Git conflict checks and immutable executing revisions; browser/WSS liveness, disconnect and gap resynchronization. Test three authenticated users and twenty observers. | BLOCKED BY STAGE 2 |
| 4. Full-system qualification | All 763 compatibility requirements and original driver/native semantics; independent DSS, network and process faults, no uncertain replay; ten real executions/twenty viewers in complete Compose and Kubernetes deployments; actual policy-capable CNI denials, Pod UID/admission, node partition and storage failure; descendant shutdown, restore/upgrade/rollback; bounded load, complete SBOM/licenses/vulnerability disposition and independent security review. | BLOCKED BY STAGE 3 |
| 5. Paired stable publication | Exact stable plugin/IDE source pair, complete acceptance receipts, clean-install smoke of stable artifacts, checksums and runbooks; successful release preflight, then merge/tag/publish. Never publish prelaunch or partial-runtime work as complete v0.8. | BLOCKED BY STAGE 4 |

## Decisive transfer scenario

In Stage 2, then repeated through the installed IDE in Stage 3: User 1 controls
A, B and C concurrently. User 2 observes B and requests control. User 1
explicitly accepts. The system establishes B's complete safe-transfer barrier,
changes only B's owner/epoch, rejects subsequent old-controller operations for
B, and admits User 2's explicit resume. A and C remain unaffected. User 3
stays read-only. Include a real child, background thread, pending prompt,
in-flight DSS operation, disconnects and delayed messages.

An unresolved command, effect or participant must visibly block transfer. No
silent retry, fabricated completion, upgraded old request or second effective
controller is accepted. This scenario does not replace other mandatory tests.

## Stage 1 startup batch

Two defects were reproduced against unchanged native.py:
(1) the reader publishes notifications after connected into a temporary queue
which is then abandoned; (2) more than 256 notifications before an OPEN reply
fill the bounded queue and stop the reader while startup waits without pumping.
A real subprocess-pipe fixture reproduces the OPEN timeout, and deterministic
reader scheduling reproduces the lost notification. These are confirmed bugs,
not proof that they caused the specific historical native LOADED timeout.

The candidate binds the final queue before reader startup and temporarily owns
a bounded 64-event pump during startup requests. Only the original root's
PAUSED notification plus its PAUSED status permits readiness. The runtime
consumer is restored on success/failure. No sent OPEN is retried; queue size
and original request/startup deadlines are not increased.

### Executed local evidence and explicit limitations

Pinned tools: pytest 8.4.2, Ruff 0.14.1, mypy 1.18.2, grpcio 1.84.0,
protobuf 7.36.2, PySide6-Essentials 6.10.3; local CPython 3.13.5.
The paired IDE is installed from its exact source. Hosted CPython is 3.13.16.

- Original implementation: two selected behavioral regressions FAIL
  (notification loss and OPEN reply timeout). Original and failing outcomes
  are retained; not relabeled as passes.
- Patched implementation: all nine startup regressions PASS; focused startup,
  lifecycle, command authority, notifications and native-boundary suite:
  215 PASS, no failures/errors/skips.
- Full paired local suite: 688 tests, 687 PASS / 1 FAIL / 0 skips. The failure
  is test_same_uid_parent_reads_positive_control_but_cannot_read_protected_winner_memory:
  this execution container refuses its required process_vm_readv positive
  control. The test is NOT skipped, weakened or recorded as passed. Hosted
  Ubuntu must execute and pass it before this batch can be accepted.
- An earlier full-run command exceeded its outer timeout before preserving a
  complete result. It is not a pass. The subsequent 687/1 run is complete.
- Ruff check/format and mypy PASS. Development server wheel builds offline.
  The wheel does not contain the separate native host provider; wheel build
  alone does not qualify the native change.

The unchanged baseline failed hosted Stage 1 preflight run 40208226103 on
Ruff formatting in server/tests/test_supply_chain.py before tests executed.
This batch includes Ruff's formatting-only correction to that file, with all
assertions retained. Failed input and outcome artifacts are preserved.

Exact-code hosted full regression and original-native family/owner execution
are mandatory and pending when this startup batch is proposed. Prompt answer,
positive abort, complete termination/error cleanup and the full Stage 1
lifecycle remain unfinished. No release gate or later stage is promoted.
