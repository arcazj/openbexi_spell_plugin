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
