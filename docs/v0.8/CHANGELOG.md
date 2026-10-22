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
