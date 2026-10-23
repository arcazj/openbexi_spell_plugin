# v0.8 work in progress

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
