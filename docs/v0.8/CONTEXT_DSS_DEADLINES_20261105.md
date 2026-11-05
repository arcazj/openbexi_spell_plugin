# Context/DSS deadlines and memory attribution — November 5

Foundation passes on the reference Linux runner: **1,823 tests in 547.880 seconds, zero failures, errors or skips**, with the original 600-second suite limit and validated `-g1` fixture optimization. The three original concurrent checks pass in the final matched local and Linux runs, including separate live-heartbeat regressions. Storage-stall failures remain preserved; this is not an unconditional concurrency or release qualification.

The production runtime remains `c5529d02a49c89a8919b965ffb4eb43498eb0cdf`. No request deadline, SQLite durability setting, sanitizer option, workload rate, audit retention rule or memory acceptance limit changed. The earlier [investigation](ROOT_CAUSE_20261105.md) remains a historical record.

## The three checks, individually

`scripts/profile_context_deadlines.py` invokes these original `test_native_driver.py` checks separately, with their original inputs and assertions:

| Check | Original deadline | Preserved workload |
| --- | ---: | --- |
| `test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss[2]` | 2 s | Three bursts of ten real mTLS requests; five stages; original receipts and both ledgers checked |
| Same check, `[3]` | 3 s | Identical workload with its original deadline |
| `test_ten_pending_receipts_bound_eleventh_rpc_without_effect[complete]` | 1.5 s | Ten preconnected pending receipts, original join/hold, eleventh-call rejection and no-effect checks |

Each final environment runs three repetitions with instrumentation and three without it per check: 18 independent trials. The diagnostic records Context and DSS lock waits, FIFO ledger and execution mutex waits, SQLite COMMIT durations, real `fsync`/`fdatasync`/`pwrite64` calls, and RPC preparation, authority, connect, send, receipt and settlement phases. The separate DSS process is instrumented too. Instrumentation preserves calls, return values, exceptions and synchronization. Its overhead is visible; uninstrumented controls are retained.

| Environment | Pass | Fail | Interpretation |
| --- | ---: | ---: | --- |
| Local original runner, durable short path, idle repetition | 18 | 0 | Pass under measured idle conditions |
| Local pinned comparison container | 18 | 0 | Matches the reference container's inputs and libraries |
| Linux pinned comparison container, run `42004654161` | 18 | 0 | Paired comparison |
| Linux reference Python, same run | 18 | 0 | Reference environment also passes |
| Local durable-volume trial overlapping image build/writeback | 7 | 11 | Contended diagnostic, not an idle baseline |
| Earlier Linux reference run `42004497810` | 17 | 1 | Uninstrumented original 2-second burst expired; retained counterexample |

The matched local and reference environments have equal Python and SQLite versions, all 13 dependency versions, 200 input hashes and 33 mapped binary hashes. Host kernels and storage differ. Initial diagnostic setup failures (missing Git in the image and observer import rewriting under `-W error`) are retained separately from application deadline failures.

Maximum observed durations below are milliseconds across the three profiled repetitions. These are overlapping categories, not additive costs.

| Check / environment | Context commit | Driver commit | DSS commit | Ledger wait | Execution wait | Receipt wait |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 s / local matched | 21.442 | 21.850 | 10.690 | 259.216 | 0.084 | 5.214 |
| 2 s / Linux matched | 5.943 | 7.797 | 4.998 | 53.779 | 0.033 | 5.194 |
| 3 s / local matched | 29.493 | 19.930 | 8.750 | 285.278 | 0.065 | 4.485 |
| 3 s / Linux matched | 12.396 | 14.049 | 8.020 | 62.146 | 0.032 | 8.611 |
| 1.5 s / local matched | 23.674 | 55.239 | 5.955 | 261.409 | 0.035 | 5.670 |
| 1.5 s / Linux matched | 14.193 | 13.280 | 5.374 | 68.317 | 0.030 | 3.694 |

The contended 3-second failure contains a 1,484.311 ms ledger wait. The union of overlapping commit intervals covers 1,458.578 ms; the union of real durable sync intervals covers 1,448.007 ms, or 97.55% of that wait. A Context commit takes 314.499 ms and its database `fdatasync` takes 309.606 ms. Execution mutex waits remain below 0.1 ms. The 1.5-second case reaches a 1,628.422 ms ledger wait. These traces identify serialized durable I/O as the measured critical path; they do not justify weakening commits or shortening the protected transaction.

The earlier hosted failure prevents a Windows-only diagnosis: cgroup full I/O pressure rises from 12,300,534 to 14,353,536 microseconds during that uninstrumented burst. Without per-call timings for that particular control, its internal cause is not proved. Native startup failures from previous investigations also cannot be retroactively attributed to these isolated measurements.

`Transport.command` timing includes preparation before its protected command deadline. A total span slightly above two seconds in a passing check is not itself a deadline violation. Raw phase timings, database fixtures, outcomes and cgroup telemetry are retained.

## Concurrent heartbeats and foundation

`test_driver_deadline_heartbeats.py` runs each original concurrent oracle while renewing a real controller lease over the pinned route. It uses the minimum supported five-second lease, preserves the two-second heartbeat response bound and checks all renewal outcomes. Local: three cases, 93 renewals, zero failures, maximum 41.851 ms. Reference: all 27 concurrency/liveness tests pass; the three concurrent cases record 31 renewals, zero failures, maximum 40.473 ms.

[Reference follow-up run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/42006387996) binds the complete foundation result to `540c0e0ba957a82b98f3c13a416da28cd52acd65`. Lint, formatting, types and the complete suite pass. The journal has contiguous sequences, 1,823 successful setup/call/teardown reports and an explicit successful session finish. All 290 recorded input hashes match; one Windows checkout file requires comparison to its identical Git blob because of line endings. No broad local qualification was repeated.

## Memory capture

The first reference 300-second workload completed 303.075 seconds with eight original processes and 177 controller renewals without failure. Its diagnostic observer stopped after seven startup samples, so it is **not** a complete memory trace. A separate 45-second reproduction retained the previously discarded stderr and established the observer cause: `ValueError: ASan diagnostic statistics exceeded bound`.

The diagnostic parser now retains complete marker-delimited blocks inside the existing 256 KiB log window instead of aborting observation at 16 KiB. Interleaved statistics remain explicitly marked and cannot be treated as unambiguous process counters. Six boundary/interleaving cases and 29 recorded blocks pass replay checks. This is an observer correction, not a memory correction.

The [corrected capture](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/42010285687), source `47ebd1c091e0299213f9ee3978cf4e74d513fddf`, completes **303.491 seconds** with 169 resource samples, including 143 in the soak, all eight original process identities, verified native instrumentation, 178 successful controller renewals, zero observer errors, zero swap and zero memory-limit events. All progress intervals advance. The original memory oracle fails solely on growth: **319,567,872 bytes (304.76 MiB)** versus **67,108,864 bytes (64 MiB)**. The sampled run is diagnostic and is not an improvement comparison against the earlier uninstrumented local baseline.

First/last ten-second window medians give this decomposition. Live-byte counters are asynchronous; the receipt retains their ages. These overlapping measures are never added to each other or subtracted from the original oracle.

| Role / namespace PID | Anonymous growth | Live allocated-byte change |
| --- | ---: | ---: |
| Executor 101 | 169,807,872 bytes (161.94 MiB) | +3,182 |
| Executor 148 | 83,771,392 bytes (79.89 MiB) | 0 |
| Context 37 | 39,800,832 bytes (37.96 MiB) | +5,770 |
| Active bridge 83 | 12,357,632 bytes (11.79 MiB) | -813 |
| Listener 20 | 5,453,824 bytes | Not instrumented for allocator counters |
| Bridge 42 | 2,375,680 bytes | 0 |

Cgroup anonymous growth is 314,701,824 bytes; file growth is 4,352,000 bytes. File growth includes 4,341,760 bytes of shmem and must not be counted twice. This is predominantly anonymous retention, not a newly demonstrated accumulation of durable audit pages.

Unambiguous ASan blocks show Context global quarantine increasing from 139,962,998 bytes at soak +39.729 s to 150,542,768 at +300.479 s. The active bridge increases from 2,097,259 bytes at +39.789 s to 7,340,528 at +301.449 s. Executor 101 rises from 136,691,792 to 250,280,144 bytes; Executor 148 from 124,005,457 to 179,747,889. These sparse, differently timed counters are not full-window deltas or a complete byte-for-byte explanation of RSS. Four Context blocks and one Executor block are interleaved and excluded from these counter comparisons. Full process/allocator observations and the complete soak remain available; sample-stack misses and incomplete site records are explicit.

Exact exported ELF hashes match the run's native build receipt before source-line symbolization. Context sites include `SPELLipcInput::dispatch`, the message-copy path through `SPELLclientIPC::sendMessage`, and `SPELLexecutorManager::buildExecutorInfo` string assembly. The active bridge includes JSON DOM parsing at `private_bridge.cpp:93` and mailbox preparation through `performRequest` at line 106 of the diagnostic overlay. Many sampled sites have matching frees; unmatched samples are upper bounds because free-hook misses occur. The leading Executor sampled sites end with 286,720, 176,128 and 241,664 allocated bytes, each matched by observed frees. Together with nearly flat live totals and rising quarantine, this supports allocator/sanitizer retention from allocation churn, not a demonstrated growing live-object leak.

**No conforming production memory correction is established.** Removing locks or durable commits does not address this measured anonymous growth. Context/bridge-only allocation changes are not established as sufficient given the Executor contribution. Reducing workload, Python buffer semantics or sanitizer quarantine would change the required experiment. The previous unsafe buffer experiment remains rejected. The next correction must reduce demonstrated allocation churn while preserving ownership, buffer lifetimes and all original checks, then pass a fresh unmodified 300-second acceptance. Neither original one-hour scenario was attempted in this investigation.

## Evidence and recovery

The [machine receipt](evidence/context-deadlines-20261105/qualification.json) and supporting summaries record exact sources, limits, run identities and remaining gates. Raw evidence remains under `F:/openbexi-builds/v08-qualification-20261104/context-deadlines-20261105/`; downloaded follow-up artifacts are under `F:/openbexi-builds/deadline-artifacts/`. ZIP checksums and CRCs were verified. Failed trials and historical records remain intact.

No production runtime correction, complete memory acceptance, one-hour scenario, deployment qualification or release-gate promotion is claimed by the deadline passes alone.
