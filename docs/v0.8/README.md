> **Qualification status:** full v0.8 remains unqualified. [Current results and next work](CURRENT_STATUS.md) supersede historical summaries below; original evidence and acceptance limits remain binding.

<!-- ROOT CAUSE FOLLOWTHROUGH 20261105 -->
> **Latest investigation:** [Context/DSS deadlines and complete memory trace](CONTEXT_DSS_DEADLINES_20261105.md): matched concurrent checks and live heartbeats pass; reference foundation passes all 1,823 tests in 547.880 seconds. The complete 303.491-second diagnostic still fails memory growth (304.76 MiB versus 64 MiB), with zero swap. All original limits and failed evidence are retained; no memory correction or release qualification is claimed.
<!-- END ROOT CAUSE FOLLOWTHROUGH 20261105 -->

# SPELL v0.8 implementation and qualification

**SPELL v0.8-rc1 and IDE v1.2.1 are published and unqualified.** Start with [current status](CURRENT_STATUS.md), [release readiness](RELEASE_READINESS.md), [known limitations](KNOWN_LIMITATIONS.md), [release gates](RELEASE_GATES.json) and [the current receipt](evidence/qualification-reference-runner-20261105.json). All eleven full-release groups remain open.

The latest reference foundation passes 1,823 cases in 547.880 seconds, retaining the original limit and compiler optimization. Matched concurrent checks and real heartbeats pass under measured conditions. The complete 303.491-second Context/bridge diagnostic still fails memory growth at 319,567,872 bytes against 67,108,864 allowed, with zero swap. Earlier local/hosted 45-second passes and failed runs remain preserved; both original hours and full acceptance remain open.

## Continue qualification

1. Read the [environment contract](QUALIFICATION_ENVIRONMENTS.json), [local runner prerequisites](LOCAL_QUALIFICATION_RUNNER.md), [memory requirements](NATIVE_RESOURCE_ACCEPTANCE.md) and [test report](TEST_REPORT.md).
2. Use the [acceptance plan](ACCEPTANCE_PLAN.md), [compatibility matrix](SPELL_COMPATIBILITY_MATRIX.md), [deployment qualification](DEPLOYMENT_QUALIFICATION.md) and [security/recovery requirements](SECURITY_AND_RECOVERY.md) without narrowing their original scope.
3. Track the production-like enforced-NetworkPolicy cluster and independent implemented-system reviewer as external prerequisites. Continue implementation work while those resources remain unavailable.
4. Preserve exact subjects and failed evidence. Later documentation, package versions and desktop health are not additional runtime qualification.

## Architecture and implementation references

- [Verified v0.7 baseline](BASELINE_V07.md), [legacy reference](LEGACY_REFERENCE.md), [process/port map](PROCESS_AND_PORT_MAP.md) and [gap analysis](GAP_ANALYSIS.md).
- [Architecture](ARCHITECTURE.md), [decisions](ARCHITECTURE_DECISIONS.md), [protocol register](PROTOCOL_REGISTER.md), [ownership protocol](CONTROL_OWNERSHIP_PROTOCOL.md) and [sequence diagrams](SEQUENCE_DIAGRAMS.md).
- [Architecture review](ARCHITECTURE_REVIEW.md) and [binding G1 resolutions](G1_REVIEW_RESOLUTION.md). That earlier architecture review does not satisfy the mandatory independent review of the implemented system.
- [Server foundation](../../server/README.md), [authority](EXECUTION_AUTHORITY.md), [worker/source preflight](WORKER_PREFLIGHT.md), [native launch](NATIVE_LAUNCH.md), [IDE controls](IDE_NATIVE_CONTROLS.md) and [Compose/Kubernetes staging](../../deploy/v0.8/README.md).
- [Source/dependency qualification](SUPPLY_CHAIN_QUALIFICATION.md), [risks](RISKS.md), [changelog](CHANGELOG.md) and editable [diagrams](diagrams/README.md).

Published server/host/shared/DSS packages use 0.8.0rc1; the separate root SDK remains 0.1.0. Public v0.8 runtime provisioning remains disabled. Private retained-worker cohorts do not establish the full public IDE/browser workflow. The local desktop still contains the v0.7 native baseline.

Historical design documents and diagrams preserve the stages they describe. Their proposed components, old candidate IDs and bounded results do not override [current qualification](CURRENT_STATUS.md) or establish a qualified stable v0.8 release.
