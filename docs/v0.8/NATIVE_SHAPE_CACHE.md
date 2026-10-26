# Native message cache shape correction

This is a measured runtime correction, not full v0.8 acceptance.

The source baseline is `153b2edf5571d887f30c83a1075faef7765f250e`, tree
`f9a82b26f6c762f76328fbcb6c22c7d1e82b40f1`. The exact-source archive and its
Git tree were independently verified before editing.

## Reproduced cause

The bounded native property-map cache selected its last returned map regardless
of field inventory. Native LINE, ACK and control traffic interleave different
shapes. Each copy therefore erased one shape's nodes and allocated the next
shape's nodes. A focused interleaving reproducer fails against the baseline:
40,000 copies across four shapes allocate 260,000 map nodes / 24,960,000 bytes,
exactly the same as the frozen implementation for this workload.

The correction searches for an exact key inventory. When an unused slot exists,
an unmatched shape is built independently rather than destroying another cached
shape. At the unchanged 32-map capacity, unmatched shapes can reuse the last map.
The 64-field / 64-KiB-per-map retention bounds, nonblocking try-lock, independent
live-message ownership, wire bytes, class layout and all authority decisions are
unchanged. Empty and oversized inventories do not consume cached maps.

## Executed component evidence

The same reproducer now performs **zero allocations after warm-up**; the message
class remains 176 bytes. The assertion was executed and failed before the runtime
change, then passed afterward. It includes distinct inventories of equal size,
so matching only field count is insufficient.

The real frozen/patched C++ message implementations were compiled with AddressSanitizer
and UndefinedBehaviorSanitizer. Unrelated logging/Python includes use the existing
component fixtures; these tests are not a complete native-runtime execution.

- 27 native storage, codec and allocation-profiler checks pass, including mixed
  shapes, independent copies, binary/Unicode values, stale-field removal,
  eight-thread contention, bounded retention, wire framing and malformed input.
- 39 recovery resource, cleanup, diagnostic-scope and memory-limit checks pass.
- Ruff 0.14.1 lint and formatting pass for the changed Python test.

The local environment is CPython 3.13.5 / pytest 9.0.2. Hosted pinned-toolchain
qualification is separate and mandatory. See the source-bound local receipt in
`evidence/native-shape-cache/local-component-summary.json`.

## Required hosted verdict

Both normal (non-profiled) original-family recovery jobs must still pass:
`--native-handoff` and `--native-ide`. The oracle remains a 45-second soak,
eight original processes, a 2-GiB/no-swap limit, at most 1,792 MiB peak and
64 MiB median-window growth, with no memory-pressure/OOM events.

The allocation result above does not imply those cgroup measurements pass.
No release gate, publication, production migration or public-runtime enablement
is authorized by this component receipt alone.

## Hosted first correction and saturated-cache follow-up

The first correction, candidate `ad5ccc14ba485806dd391cbad3765f732e0941ea`,
completed both normal recovery profiles in run `40416255833`. The exact CI merge
tree matches the tested candidate. Both archive digests/CRC checks and all 131
source hashes in each profile are verified. Both families preserve eight original
processes, advance every interval and finish terminal settlement. The fixed
resource oracle still fails only window growth:

| Profile | Peak MiB | Window growth MiB | Fixed limit MiB |
| --- | ---: | ---: | ---: |
| Handoff | 1,584.2 | 180.3 | 1,792 peak / 64 growth |
| Installed IDE | 1,590.7 | 199.9 | 1,792 peak / 64 growth |

The allocation-frequency diagnostic still finds message copies among the main
Context allocation sites. A second regression reproduces a distinct full-cache
problem: after startup fills all 32 slots with unrelated layouts, fallback always
replaces the same last slot. Interleaved new layouts then repeatedly evict each
other while the other 31 cached layouts are never reused.

The follow-up rotates the eviction victim at the same fixed capacity. Exact
layout matching still runs first. No allocation budget, lock fallback, message
ownership, wire behavior, sanitizer setting or recovery deadline changes.
The full-cache reproducer fails at the first correction with 260,000 allocations
/ 24,960,000 bytes; rotating eviction reduces it to zero after three warm-up passes.
The original empty-cache regression also stays at zero after warm-up.

All 28 native checks and 39 recovery guards pass locally without failures,
errors or skips. Ruff lint and formatting pass for the complete server tree.
These component results do not qualify the new native family. Both normal hosted
recovery profiles must execute again; no release gate is promoted.
The source-bound follow-up receipt is
`evidence/native-shape-cache/full-cache-component-summary.json`.

### Concurrent stream integration

The 67 local checks above were executed on `ad5ccc1` plus rotating eviction.
While they ran, `621cbe79c47b419996f2b97ad9e71e60f9b4e5e6` added separate native
stream reuse and versioned the package `0.8.0.dev68`. Those changes are preserved
intact as the integration parent; this patch changes none of their files. The
combined source tree requires fresh local and hosted qualification. The existing
exact-source snapshot workflow is invoked for that integration candidate; it
does not grant a release pass or alter any acceptance threshold.
