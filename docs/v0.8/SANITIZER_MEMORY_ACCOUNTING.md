# Measured sustained sanitizer retention

Executable reference: `892914f10f12bd9a3043a69e07f363a143445ec3`, paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. This executable passes the original
mandatory 45-second handoff and installed-IDE checks at 30.30 / 52.55 MiB growth
against 64 MiB. Both longer original-sanitizer hour attempts lose an original
process before one hour. Neither outcome is promoted to full v0.8 acceptance.

The separately identified accounting branch
`6055274d29e63e3ac5fee47cd2c061e613552939` applies a reproducible, read-only
diagnostic overlay to that reference. It preserves original ASan/UBSan options,
no-swap policy, cgroup accounting, concurrency, deadlines and workload. Its
five-minute comparison retains all samples and still fails growth:

| Scenario | Growth bytes | Peak bytes | Observations | Artifact |
|---|---:|---:|---:|---:|
| Handoff | 471,771,136 | 1,758,613,504 | 54 accounting dumps | 12771083418 |
| Installed IDE | 438,962,176 | 1,445,920,768 | 54 accounting dumps | 12772428361 |

The observation calls the linked runtime's
[`__asan_print_accumulated_stats`](https://github.com/gcc-mirror/gcc/blob/master/libsanitizer/asan/asan_stats.cpp).
It does not purge quarantine, trim, adjust allocator options, change sanitizer
error reporting or subtract any usage from the resource oracle. A compiled
component checks unchanged current-allocation and heap counters before/after
the call and complete cross-process diagnostic framing. These observations
are diagnostic, not a new acceptance profile.

At the last observed handoff dumps:

| Process | Last sampled live bytes | Global quarantine bytes at last dump | Quarantined user bytes |
|---|---:|---:|---:|
| Context 37 | 10,282,657 | 197,752,586 | 191,878,922 |
| Executor 98 | 9,391,839 | 251,226,122 | 246,253,578 |
| Executor 145 | 9,147,394 | 206,919,251 | 200,406,611 |
| Active bridge 80 | 1,487,768 | 20,984,101 | 17,436,965 |
| Idle bridge 43 | 1,481,978 | 0 | 0 |

These are independently timed last observations, not a simultaneous accounting
sum. Per-thread quarantine, rounding, redzones, allocator metadata, thread
resources and sanitizer shadow memory also matter. The frozen Listener remains
in whole-cgroup measurement but was not instrumented internally. The sampler's
`free_bytes` counter is not a direct quarantine-size measurement.

The runtime reports zero megabytes really freed in these dumps while its freed
allocation totals and quarantine increase. StackDepot remains at the printed
9 MiB allocation scale. Context's 10,240-byte allocator class has 72,572 KiB RSS;
the root Executor's 5,120-byte class has 162,576 KiB RSS. This distinguishes
retention of freed objects from the much smaller sampled live allocation totals;
it does not establish absence of a leak or identify every allocation path.

Frequency-ranked native samples locate repeated request-ID strings, CIF stack
copies, line audit payloads and trace-dispatch filename copies. They do not
identify all large-byte callers. Branch
`325feb57fff5cb48665f177c6ed6c3dd78b5658c` ranks the same bounded samples by
allocation bytes to identify those callers before another runtime correction.
Its real-hook components preserve totals, free accounting and default ranking.
The actual native result is pending.

The current hour's installed-IDE final cgroup sample has zero OOM/kill counters;
the later Docker state records `OOMKilled=true`. Both are preserved, including
their order. The kernel victim PID is not proven by those two observations.
The separate historical optimized early exit at `58e6f6c` still has no established
cause and is not attributed to these sanitizer OOM observations.

Raw archives, every native input, the exact combined overlay, all 108 accounting
observations and every audit-file digest verify. See
[the source-bound checkpoint](evidence/qualification-892914f-20261027.json) and
[the hosted accounting run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40585862261).
All eleven full-release groups remain false.
