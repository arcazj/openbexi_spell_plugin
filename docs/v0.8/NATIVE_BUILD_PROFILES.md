# Explicit native build profiles and original-family endurance

This adds a build target and qualification workloads. It is not a stable release
receipt and does not close any existing mandatory gate.

## Scope and immutable controls

Base commit: `2747c66b7a9fed7de206b045558724c3528e0fca`.
Base tree: `b5ae78f03a886bad2143938010200bceaec9424c`.
The existing admission builder, 45-second recovery assessor, owner/lease/RPC
limits, effect settlement, original process identity rules, IDE pair and
`RELEASE_GATES.json` remain unchanged. No previously failing result is promoted.
The separate experiment continues to keep its workload edits in a disposable
worktree with exact preimage and executed-source digests. It no longer rewrites
the native builder to select compiler optimization or sanitizers.

## Tracked build target

`host_runtime/build_native_profile.py` has explicit `asan-o1`, `asan-o2`, and
`optimized` profiles. Every explicit profile rebuilds Context, Executor,
Listener, the common shared runtime and the IPC bridge from the same verified
frozen composition. It imports the existing composition/graph helpers rather
than substituting prebuilt native executables.

`asan-o2` and `optimized` both use `-O2`; their sanitizer policy differs.
Both profiles have the same source graph and Listener/DTA wiring. The builder
records Python/compiler identity, component/source digests, ELF dependencies,
profile and instrumentation. It rejects a mixed instrumented/uninstrumented
family. Independent host observations still verify the actually mapped runtime.
The optimized build exposes no fabricated sanitizer allocator counters.

The offline Docker target accepts a **prepared, digest-pinned toolchain image**
containing the frozen native wheel, required headers/libraries, and GIL-enabled
CPython 3.13.15+ in the 3.13 series. It has no package-index or apt network access:

```bash
python scripts/build_v08_native_profile.py \
  --toolchain-image '<prepared-image>@sha256:<64-hex-digest>' --profile optimized
```

The helper rejects mutable tags and dirty source trees, records the source tree
and commit epoch, disables network and cache during the build, and emits a
source-bound build receipt. This establishes an explicit repeatable build path;
a second independent bit-for-bit rebuild has not yet been certified. Hosted
comparison jobs still retain their normal online toolchain provisioning logs,
so their success alone is not proof of an offline reproducible release package.

## Controlled comparisons and endurance

The comparison workflow includes the existing sanitizer/O1 no-swap baseline,
optimized/O2 no-swap, sanitizer/O2 no-swap, and encrypted-swap experiments. The
O2 pair isolates sanitizer selection while retaining the same optimization.

Two additional optimized/no-swap jobs execute a 3,600-second same-family soak:
controller handoff and the pinned installed-IDE path. The original A->B->A and
same-owner reconnect prelude is retained. At 20 minutes another A->B->A plus a
same-owner disconnect/reconnect runs; at 40 minutes a further A->B->A runs.
This produces six total accepted transfers and two same-owner reconnects. The
eight original processes are held by pidfds; no new procedure family is created.
Eight identity rotations exactly respects the existing runtime cap of eight.

Each added transition checks old-proof rejection, host-observed freezer
quiescence, explicit resume, original-process survival, observer state and
continued root/background/child progress. The initial independent DSS effect
receipts are still checked unchanged; the additional transitions do not claim
additional driver replay-test coverage.

The endurance receipt records RPC p50/p95/p99/max latency, transitions, original
process counts, total and late-window RAM growth, per-process thread observations,
anonymous/file cgroup accounting and available live/retained allocator counters.
Latency is measured, not certified against a new production service-level target.
The original 2-GiB/no-swap, 1,792-MiB peak and 64-MiB window-growth criteria are
not increased. An hour-long run may legitimately fail these stricter-duration
checks; failure evidence must be retained, not relabelled as a pass.

## Isolated encrypted-swap preparation

Default behavior continues to refuse pre-existing swap. The dedicated hosted
workflow explicitly permits temporary isolation of one allowlisted, root-owned,
unused regular runner swap file. Identity, size, permissions, available RAM and
zero usage are checked before changing that one resource. Unknown, busy or
multiple devices are refused. The existing backing file is never deleted or
rewritten, and must be restored after the encrypted experiment finishes.

Every hosted preparation attempt emits `swap-setup.json`, including preflight
refusals and cleanup failures. Cleanup failures retain backing storage and fail
closed. No production host, Kubernetes node, fstab or swappiness is modified.
The encrypted profile retains its 2-GiB RAM plus 2-GiB swap budget and measures
combined usage; availability without observed swap use proves no benefit.

## Execution evidence and remaining gates

Local validation: 174 profile/resource/swap-protocol tests and 87 native/component
regressions passed, with no failures, errors or skips. The accelerated protocol
test uses an injected clock and simulated host; it is not an actual hour-long
Docker execution. Compiled component regressions use ASan/UBSan. Local Python
3.13.5 does not satisfy the full native target; the version guard was preserved.
An earlier combined test invocation reached the tool time limit, so only the
completed split suites are counted.

CI resumes the existing foundation/native scenarios, portable compatibility
subset, Compose, kind/static Kubernetes and supply-chain jobs. Browser/debugger
features, full 763-requirement native compatibility, production-like cluster
failure recovery, independent security review and stable joint packaging still
require their own implementation and source-bound evidence. Prelaunch jobs
cannot stand in for those requirements. `scripts/check_v08_release.py` remains
the fail-closed publication decision; no tag, merge or stable release is made.
