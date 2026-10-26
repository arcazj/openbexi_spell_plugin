# Dev67 native resource growth: process attribution and next diagnostic

This is **diagnostic only**, not a release receipt. The unchanged hosted dev67
candidate `93dad418c1992c2863374cad53dfcbb3ba93858f` failed both resource
acceptance cases in GitHub Actions run `40397729336`. The host observed the
original eight processes over the full 45-second soak and rejected both profiles
at the precommitted 64 MiB median-window growth threshold. The 1,792 MiB peak
ceiling passed. The 2 GiB/no-swap profile and sanitizer configuration were not
modified.

## Attribution from independently sampled host /proc observations

Measured **first-to-last soak RSS** differences (MiB; distinct from the
acceptance oracle's first/last 10-second *median cgroup* difference):

| Original process | Handoff | Installed IDE |
| --- | ---: | ---: |
| SPELL-Context | +105.6 | +105.7 |
| First SPELL-Executor | +86.3 | +86.1 |
| Second SPELL-Executor | +61.1 | +58.9 |
| Changing spell-host-ipc bridge | +26.9 | +28.8 |
| SPELL-Listener | +0.3 | +4.3 |
| Python agent | +0.5 | +0.4 |

The other bridge and container init were approximately flat. Handoff cgroup
memory.current rose from 1,332.5 to 1,620.2 MiB at observed soak endpoints.
IDE rose from 1,323.3 to 1,613.2 MiB. Those point differences are **not** the
224.9 MiB / 238.8 MiB median-window growth used by the binding oracle.

Live ASan allocations in the Context remained approximately 10 MiB; the Context
ASan heap grew from approximately 489 MiB to 564 MiB during the handoff soak.
This supports allocator-churn/retention investigation; it **does not prove a
live-object memory leak or an allocation-site cause**. The Context and two
Executors together dominate first-to-last growth, so optimizing only the bridge
cannot plausibly be treated as sufficient for full-family acceptance.

Evidence: [handoff artifact](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40397729336)
(id `12687278532`), installed IDE artifact (id `12687004051`),
and the [dev67 qualification receipt](evidence/native-codec/dev67-hosted/qualification-summary.json).

## Next executable investigation

The separate `v08-native-allocation-diagnostic.yml` workflow executes the
same original native-handoff family with the existing bounded malloc-stack
sampler enabled solely for the independent resource fixture. It requires
sampled stacks from the Context and an Executor and retains failure artifacts
without treating their collection as a pass. Enabling it does not weaken the
existing resource limits, thresholds, native admission deadlines, sanitizer
settings, ownership guards or mandatory normal CI. Sampling overhead means
the diagnostic run is **not itself** a full-family resource acceptance result.

Use its new allocation-site stacks to prioritize the live Context/Executor
message dispatch paths, make a small reversible source-bound change, and then
rerun both *non-profiled* recovery families and the full fixed gates. Do not
publish, merge, or call v0.8 qualified based on component/profile receipts.

## 26 October 2026: diagnostic first run

The opt-in hosted native sampler completed successfully as a diagnostic workflow
([run 40408379980](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40408379980),
artifact `12692396250`). The original 45-second handoff remained functionally
valid but resource acceptance failed again: 1,732.8 MiB peak, 222.0 MiB
median-window growth against 1,792/64 MiB. The native original roster and
allocation samples were independently retained; this was not a release pass.

The profiler recorded 3.57 million further allocations in Context and 0.85/0.70
million in the two Executors. Context hot traces include `std::string::reserve`
and a native Context path. The Executor's six reported sites were dominated by
one-off CPython initialization allocations (up to 131,072 bytes), which revealed
an **attribution ranking defect**: sites were sorted by sampled total bytes
instead of allocation repetition. A diagnostic-only change now ranks by sampled
call count, preserving the existing raw count/byte values and six-site bound.
The follow-up hosted diagnostic must locate the actual repeated Executor and
Context call chains before another runtime optimization is attempted. It does
not change memory limits, sanitizer behavior, original process lifetime or
release decisions.
