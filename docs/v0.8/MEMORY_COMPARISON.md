# Native memory comparison — experimental, not release qualification

The owner approved a comparison of the unchanged sanitizer profile, an optimized
native build, and a bounded swap-enabled resilience profile. These experiments
**do not fix or waive the native memory-growth blocker**, change any mandatory
release gate, enable public runtime, or authorize production migration.

## Executable profiles

The dedicated workflow runs both `handoff` and `ide` for each profile. All jobs
use the same checkout revision, the pinned IDE in `IDE_PAIR.json`, and the same
recovery workload. The independent host must retain the original eight processes
through A→B→A handoffs, controller loss and explicit reconnect. The subsequent
soak is 300 seconds, with progress checks every five seconds. This is a bounded
sample, not proof of indefinite stability or complete production capacity.

| Profile | Native instrumentation | RAM / allowed swap | Experimental memory acceptance |
| --- | --- | --- | --- |
| `asan-noswap` | Existing ASan/UBSan configuration | 2 GiB / 0 | ≤1,792 MiB resident peak; ≤64 MiB window growth |
| `optimized-noswap` | `-O2`, no ASan/UBSan in the rebuilt native family | 2 GiB / 0 | Same resident peak/growth limits |
| `asan-swap` | Existing ASan/UBSan configuration | 2 GiB / 2 GiB | ≤2 GiB resident peak; ≤3,584 MiB sampled RAM+swap; ≤64 MiB RAM+swap window growth |

The normal 45-second sanitizer/no-swap recovery jobs remain unchanged. A pass in
this separate workflow cannot promote them or any full-v0.8 gate. The swap
profile has a different total resource budget; it is not an equivalent-capacity
fix experiment. The combined metric is the sum of cgroup charged RAM and swap,
not an assertion about live application objects. Its peak is explicitly sampled.

A swap-enabled run with no observed swap use records `swap_exercised: false` and
cannot demonstrate swap benefit. All profiles reject OOM, missing observations,
changed process identities, missing native roles and mismatched instrumentation.
The swap profile records RAM-limit/reclaim events instead of treating those
alone as a failure; it still rejects swap allocation failure and ongoing total
growth. The existing RPC/admission/driver/lease deadlines and effect-replay rules
are not changed. Existing recovery checks enforce their own functional deadlines;
this harness does not yet establish a new p95/p99 latency service-level objective.

## Optimized build scope and safeguards

Only a disposable detached worktree is transformed. Exact source preimage hashes
must match before any transformation is written. Its manifest and patch are
retained along with both original and executed source hashes.

The optimized image rebuilds Context, Executor, Listener, the shared native
library and the bridge. The Listener is launched through a generated wrapper
which preserves the frozen launcher's Python/library environment, including
`PYTHONMALLOC=malloc`, but selects the rebuilt Listener. The experimental DTA
shim selects the rebuilt shared library. Those wiring changes are explicit in
the retained build receipt. This is **not a stable production package**.

`readelf` checks reject sanitizer-linked candidate artifacts. Independent host
observations verify actual native process mappings during the soak, preventing a
mixed optimized/sanitized family from passing. Sanitizer allocator counters are
unavailable in the optimized build; no zero or fabricated live-allocation data
is substituted. `/proc` and cgroup observations remain mandatory in all modes.

## Swap isolation

`v08_memory_swap_ci.sh` refuses to run outside a GitHub-hosted Linux runner. It
also refuses existing host swap rather than disabling or silently using it.
The helper allocates one bounded 2 GiB backing file, opens dm-crypt with a fresh
random key, and enables that device as swap. The key is never written to the
repository, disk, logs or artifacts. The normal-account harness verifies the
mapped device identity, encryption type and capacity before running.

Cleanup disables only this experiment's swap and removes its mapper, loop and
file. A failed swapoff retains backing storage and fails closed. No `fstab`,
swappiness, existing swap, production host or Kubernetes node is modified.
Container swap allowance is `--memory=2048m --memory-swap=4096m`; Docker's second
flag is the **combined** RAM+swap allowance, not an additional 4 GiB.

## Local validation / execution

```bash
python -m pytest -q server/tests/test_v08_memory_experiment.py server/tests/test_native_resource_probe.py
python scripts/qualify_v08_memory_comparison.py --profile optimized-noswap --scenario handoff --soak-seconds 300 --prepare-only
# Non-root Linux Docker/cgroup-v2 host with existing harness prerequisites:
python scripts/qualify_v08_memory_comparison.py --profile asan-noswap --scenario handoff --soak-seconds 300
python scripts/qualify_v08_memory_comparison.py --profile optimized-noswap --scenario ide --soak-seconds 300
```

`--prepare-only` validates and records an overlay; it reports `executed: false`
and `passed: false`. The swap profile is provisioned only by the dedicated hosted
workflow, not by silently reconfiguring an operator's computer.

Reports use `openbexi.native-memory-comparison/1` and
`openbexi.native-memory-comparison-resources/1`, never the mandatory acceptance
receipt schema. Failed and incomplete cases remain failures. All reports retain
`full_v08_qualified: false` and `eligible_for_publication: false`.

## Sources

- Docker memory/swap semantics: https://docs.docker.com/engine/containers/resource_constraints/
- Linux cgroup-v2 accounting: https://docs.kernel.org/admin-guide/cgroup-v2.html
- ASan memory overhead: https://clang.llvm.org/docs/AddressSanitizer.html

Hosted native comparison results are pending at implementation time. Local unit,
overlay and stub-compiler results must not be described as hosted recovery passes.
