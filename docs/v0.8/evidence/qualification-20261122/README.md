# IDE and SPELL joint qualification

**Hold the stable release.** The November 22 qualification tested IDE 1.2.2 at `fadac70d574760cbe21c5e5512a384dddfa36e80` with SPELL 0.8.0 at `47e0cb376dac1e49e1f6745318c0eb3e43b2ec4d`. The simulator SDK is 0.1.0. Published IDE 1.2.1 at `08c314fb` passed ordinary Windows Python Run/Debug. Its controller reserved a native procedure but could not launch it. That published pair has a separate **FAIL** verdict. [Artifact hashes and exact images](product-identities.json) · [Gate decisions](qualification.json)

| Gate | Verdict | Observation and outstanding work |
| --- | --- | --- |
| Services and concurrency | **NOT RUN** | Ten native Jobs ran together. The 100-way public start race produced one admission and 99 conflicts. Complete the remaining isolation and partition cases. [Evidence](kubernetes-native-jobs.json) |
| Native execution and memory | **FAIL** | The original five-minute sanitizer workloads exceeded 64 MiB. Both original one-hour workloads remain gated. [Evidence](runtime-comparison.json) |
| Inherited compatibility | **FAIL** | 318 IDs passed every dimension, 27 have a reproduced failure and 418 lack a complete verdict. [Evidence](compatibility-outcomes.json) |
| Driver and simulator | **FAIL** | Original GENERIC telemetry and command cases passed. Hosted command bursts still missed their deadlines under durable storage contention. [Evidence](deadline-results.json) |
| Installed IDEs and browser | **BLOCKED** | The 23-client browser exercised live handoff and reconnect. Real project Run and Debug in IntelliJ IDEA and PyCharm require user onboarding. [Evidence](public-live-final.json) |
| Compose deployment | **NOT RUN** | Backup, restore, rollback and storage failure have real receipts. The complete component-loss and effect-isolation matrix remains open. [Evidence](compose-active-storage-fault.json) |
| Kubernetes | **BLOCKED** | The three-node KinD cluster ran and fenced native Jobs. The target operator and representative cluster are outstanding. [Evidence](kubernetes-native-jobs.json) |
| Operational recovery | **BLOCKED** | A replacement authority rejected the old proof and preserved audit history. Representative multi-host storage and DSS recovery remain open. [Evidence](compose-recovery.json) |
| Security | **BLOCKED** | The final role images have inventories and notices. The desktop has one scanner-critical finding and the implemented system needs independent review. [Evidence](advisory-dispositions.json) |
| Hosted qualification | **FAIL** | Hosted foundation results and all job outcomes are indexed. Mandatory memory and timing failures remain open. [Evidence](hosted-runs.json) |
| Packaging and publication | **BLOCKED** | Six exact wheel/sdist pairs passed license and checksum checks. Stable release downloads require all mandatory gates to pass. [Evidence](package-licenses.json) |

The full release group uses **NOT RUN** when its complete required matrix has never finished and its individual results are recorded separately. G0/A and G1/B have scoped historical passes. The ledger records each G0–G9, A–L and F1–F10 requirement. [Underlying requirements](qualification.json) · [Acceptance plan](../../ACCEPTANCE_PLAN.md)

## Native memory and response time

| Five-minute workload | ASan growth | ASan resident peak | Optimized growth | Swap |
| --- | ---: | ---: | ---: | ---: |
| Controller handoff | 259.07 MiB | 1,193.95 MiB | 3.46 MiB | 0 |
| Installed IDE | 308.17 MiB | 1,250.93 MiB | 3.36 MiB | 0 |

The sanitizer runs span 302.745 and 302.448 seconds on IDE `3ec9d4d9` and SPELL `c7292d39`. They include all eight processes and compare the first and last ten-second medians for the cgroup. The optimized comparison used SPELL `7afd6f`. In earlier one-hour runs, sanitizer peaks reached 1,962.57 and 1,968.03 MiB, above the 1,792 MiB limit. Both still grew during the last ten minutes. The reference short sanitizer tests passed. The failed five-minute prerequisite left both original one-hour jobs skipped. [Original five-minute and gated jobs](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45092025727) · [Optimized comparison](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45093419521)

Three isolated CPython progress writers grew by 258.71 MiB under the sanitizer and by 0.42 MiB optimized. Sampled native allocations had matched frees. Reusing Context log storage reduced allocations for 10,000 requests from 50,000 to 10,003 while preserving the log bytes. The intended deployment's worker and node memory budgets are outstanding. Keep the 64 MiB growth rule, 1,792 MiB peak, 2 GiB cgroup and zero-swap criteria. [Memory attribution](native-memory.json)

The original 2-second, 3-second and 1.5-second deadlines remain in force. A failed three-second burst included 1,214.5 ms waiting for the ledger, overlapping 1,191.5 ms of durable synchronization. A separate 4a native terminal child fixture reached its own 768 MiB cgroup limit and the kernel recorded an OOM kill. [Driver latency](deadline-results.json) · [Terminal fixture](terminal-close-child-4a28557a.json)

## Installed users and deployment

The selected Windows distribution is online. The clean environment fetched seven third-party wheels from public PyPI and verified all six staged product wheels after installation. Ordinary Run/Debug preceded SPELL installation. The installed Qt owner answered Y to the native question. A separately authenticated observer saw the same FINISHED result. Both SDKs produced the same JetBrains ZIP. Two installed Development windows resolved a real same-file Git conflict. [Online install](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/online-install-47e0cb37.json) · [Windows native prompt](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/online-native-prompt-47e.json) · [Git case](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/git-conflict-47e.json) · [JetBrains host evidence](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/jetbrains.json)

On the final single-host worker, three users and twenty additional observers opened separate authenticated Chromium sessions. The original root and child stayed paused through A→B→A and an authenticated reconnect. B answered the original prompt once. All twenty observers saw completion, and stale or read-only controls returned 403. The preceding 4a delivery trial stopped at a busy command poll. The corrected Context held the operation before delivery until the next authorized poll. [Final browser and kernel receipts](public-live-final.json) · [First delivery failure](public-live-4a28557a.json) · [Reproduction bundle](public-live-tools.zip)

On the earlier `655f5b5a` local KinD deployment, ten real Jobs overlapped for 11.715489 seconds across two worker nodes. Twenty observers saw all ten finish. The worker now creates and owns its private 0700 audit directory on each PVC. After an active worker and authority were fenced, the replacement on the original PVC retained all eleven pre-loss audit events and rejected the old proof. [KinD concurrency and fencing](kubernetes-native-jobs.json)

All 46 missing historic captures were recovered. The source-scoped native accounting uses each requirement's original positive, boundary, failure and recovery oracles. The real GENERIC telemetry and command checks passed 80/80 and 8/8. The row ledger preserves every missing or failing dimension. [All 763 IDs](compatibility-outcomes.json) · [Recovered captures](compatibility-capture-recovery.json) · [GENERIC results](compatibility-generic.json)

The preceding delivery build passed 1,839 foundation tests in 415.288 seconds. [Hosted foundation](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45099071796) The rebuilt Debian desktop passed X11 Python Run/Debug and pinned Chromium/noVNC. Its libxml2 version is still listed as vulnerable for Debian Trixie. The advisory register links each image observation to its disposition and identifies the supplier fixes and review still needed. [Desktop inputs](desktop-inputs.json) · [Image inventories](image-notices-47e0cb37.json) · [Debian security tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653)

The publication guard is enforced on clean checkouts. Stable tags, release downloads and any production migration are conditional on their respective authorizations. [Publication check](publication-preflight-996.json) · [Release ledger](../../RELEASE_GATES.json) · [Hosted job outcomes](hosted-runs.json)
