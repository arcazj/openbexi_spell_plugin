# IDE and SPELL joint qualification

**Hold the stable release.** IDE 1.2.2 (`3ec9d4d9`) and SPELL 0.8.0 (`99686362`) are the tested candidate pair. The published IDE 1.2.1 stopped at native reservation. The four SPELL runtime packages use 0.8.0 and the simulator SDK uses 0.1.0. Windows distribution uses online installation. [Exact subjects and artifact hashes](product-identities.json) · [Eleven gate verdicts](qualification.json)

## Native memory

The original instrumented family ran both short scenarios within the approved limits on the hosted reference runner. The five-minute runs on SPELL `c7292d39` and IDE `3ec9d4d9` failed the 64 MiB growth criterion. Growth compares the first and last ten-second medians for the whole cgroup. Both runs measured all eight original processes.

| Original sanitizer workload | Elapsed | Growth | Resident peak | Swap | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Controller handoff | 302.745 s | 259.07 MiB | 1,193.95 MiB | 0 | FAIL |
| Installed IDE | 302.448 s | 308.17 MiB | 1,250.93 MiB | 0 | FAIL |

The 1,792 MiB peak and 2 GiB container limits were preserved. The one-hour scenarios were skipped. Real disk-full and audit restart checks passed in the same workflow. [Five-minute runs and audit jobs](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45092025727)

On the optimized build, five-minute growth was 3.46 MiB for controller handoff and 3.36 MiB through the installed IDE. Both runs used zero swap. The original 45-second sanitizer checks also passed on `99686362`. The optimized Listener, Context, Executor, bridge and shared runtime rebuilt at that commit each matched the earlier delivered binary byte for byte. [Optimized comparison](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45093419521) · [Native build and application identities](product-identities.json)

Three isolated progress writers grew by 258.71 MiB with the sanitizer and 0.42 MiB optimized over five minutes. The same sampled executor allocations had matching frees in the original trace. Reusing bounded Context log storage reduced allocations for 10,000 requests from 50,000 to 10,003 with identical log bytes. Local short runs stopped on request deadlines before entering the soak. Deployment headroom for ten procedures requires an operator-provided memory budget. [Native memory evidence](native-memory.json)

## Installed products

On fresh Windows, ordinary Python Run and Debug passed before SPELL installation. With the candidate wheels, a controller and observer both saw native `FINISHED` for the same execution. Completed roots retained their reservation until authority settlement. The rebuilt Debian desktop passed X11 Python Run/Debug and a Chromium noVNC connection. [Windows public launch](public-launch-final.json) · [Desktop inputs](desktop-inputs.json) · [Product and runner receipts](product-identities.json)

IntelliJ IDEA and PyCharm loaded the candidate ZIP. The packaged Swing workspace exercised native commands and observed completion. Project-level Run/Debug in the actual host processes is pending the users' JetBrains agreement decisions. [Windows host evidence](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/jetbrains.json)

All 46 previously missing historical captures were recovered and verified by SHA-256. The row-by-row matrix records which of the 763 inherited requirements have current, complete native evidence. [Capture recovery](compatibility-capture-recovery.json) · [Native coverage](compatibility-native-inventory.json)

## Operations and controls

Ten different procedures ran concurrently for 11.575 seconds. Twenty authenticated observers saw all ten finish. One of 100 competing launch intents was admitted and 99 received HTTP 409. A separate Chromium run exercised 23 independent mTLS identities and WSS sessions. All twenty browser observers saw the native completion, and each observer's attempted mutation was denied. A–B–A transfer of a reserved procedure passed. Transfer during active native execution put the family into recovery and fenced both users. [Load evidence](https://github.com/arcazj/openbexi_ide/blob/qualification/ide-spell-20261122/docs/evidence/ide-1.2.1/qualification-20261122/windows/public-api-load.json) · [Authenticated Chromium run](public-browser.json)

On three hosted Kubernetes nodes, Calico denied Gateway access to DSS and Context while the legitimate callers connected before and after each denial. A separate Context recovered its durable state after restart. On isolated Compose storage, an operator captured a real paused root, restored into a fresh volume, rolled back to the published RC1, and upgraded again. The server rejected the old controller proof and worker certificate. All 15 pre-checkpoint audit rows and the original ASRUN survived. [Kubernetes policy and restart](kubernetes-network.json) · [Compose recovery](compose-recovery.json)

The hosted foundation passed 1,838 tests in 411.649 seconds with zero skips. A separate two-second command-burst test failed while its controller heartbeats remained within their deadlines. The release still requires complete native compatibility, representative cluster and operator evidence, and independent assessment of the installed system and its dependencies. [Foundation and Windows jobs](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/45093674176) · [Driver deadlines](deadline-results.json) · [Image inventories](image-supply-chain.json)

[Release ledger](../../RELEASE_GATES.json) · [Original acceptance plan](../../ACCEPTANCE_PLAN.md) · [Every hosted job and artifact digest](hosted-runs.json)
