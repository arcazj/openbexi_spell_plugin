# v0.8 prelaunch Compose and Kubernetes deployment qualification

**Scope:** development package `0.8.0.dev43`, executable candidate
`6a2007bfad816414628702ed4cb45d4e2f8bdf1b`. No native runtime,
ownership transfer, public browser session, Kubernetes worker Job or
production migration is authorized by these receipts. Do not promote either
full-release `compose` or `kubernetes` gate based on a prelaunch test.

## Exact-source GitHub Actions — PASS

| Real hosted test | Source and evidence | Result |
|---|---|---|
| Compose push | [40205101773](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205101773) | PASS |
| Compose PR | [40205105573](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205105573) | PASS |
| Kind v1.32.2 push | [40205101994](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205101994) | PASS |
| Kind v1.32.2 PR | [40205105539](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205105539) | PASS |
| Kubernetes static security validation | [40205101848](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205101848), [40205105536](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40205105536) | PASS |

The downloaded original PR artifacts were checked locally for ZIP integrity
and both `before.json`/`after.json` receipts. Compose artifact SHA-256:
`2f78e01bb5879fd8c71cf3ab1f3ebe2ebf05c24ef322f98bae8c2f6af3378782`.
Kind artifact SHA-256:
`2156cd370eceb8536180fbeb3a540eb9a2bc5987c65d66b79d7af4abb0110979`.

The **same 11 prelaunch assertions** passed in both environments:
three user certificates and independent Context scopes; denied observer write;
disabled public execution; Context A/B blackboard separation; durable
idempotent CAS and rejected wrong revision; Context A restart with changed
incarnation and preserved value; Context B incarnation unchanged; isolation
persisting across that restart. The independent DSS process health probe also
passed. Both records explicitly have `native_runtime_qualified=false`,
`full_v08_qualified=false`, and
`production_migration_authorized=false`.

The Kubernetes source generator returned **23 objects**: Namespace,
ServiceAccount without automatic token, five Deployments, five ClusterIP
Services, three private PVCs, eight NetworkPolicies including default deny.
Default deny is emitted before Pods are created; a separate ephemeral CA
creates independent TLS certificates for each role outside Git. Kubernetes
runs were in disposable kind v1.32.2 clusters; Docker Compose ran five
separate containers with isolated control/driver networks and host-loopback
Gateway ingress only.

## Security and qualification boundaries

- The staging source ships **no native Executor/child worker containers or
  Kubernetes Jobs** and sets `runtime_enabled=false`. It does not prove
  controller transfer, command/prompt completion, dynamic worker admission,
  runtime driver-effect safety or native procedure restart.
- Kind's default `kindnet` CNI **does not enforce NetworkPolicy**.
  Applying eight NetworkPolicy objects is not proof of cross-pod or
  cross-namespace packet isolation. A network-policy-capable CNI and actual
  hostile/partition probes are required.
- This is not a multi-node, fault-injected, high-availability, signed-image,
  production-PKI, durable disaster-recovery or ingress/browser/WSS test.
  SQLite PVC exclusivity and basic restart preservation do not establish
  reliable node partition, restore, upgrade or rollback.
- The original full compatibility, external DSS/driver faults, security/SBOM,
  complete participant and queue/effect barrier, browser/UI three-mode
  execution, native owner transition and stable joint packaging remain open.
- Both repositories' draft pull requests remain unmerged, v0.7 frozen, and
  **all eleven mandatory full v0.8 release gates remain false**.

Review [Compose profile](../../deploy/v0.8/README.md) and
[Kubernetes profile](../../deploy/v0.8/KUBERNETES.md).
