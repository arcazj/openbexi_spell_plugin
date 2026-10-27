<!-- checkpoint-6dd8218:start -->
# Verified bounded checkpoint at 6dd8218, full release unqualified

Executable `6dd82189a4cdc4f021af3a357ccf747a0b459f98` (`0.8.0.dev72`), paired IDE
`c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`; tested PR merge `4cead70f8c532bd8a0c064b309b22dfa9a1ed475` has
identical tree `e8a9e51741d48c340b1ecf7845e437da6fdb0b7a`.

All 14 core jobs pass, with 1,605 foundation tests and zero failures, errors or
skips. The real 10,000-admission Unix/JSON/peer-pin/epoch-rotation component
passes on CI; the prior local EPERM attempt remains failed and retained.
Both mandatory original-ASan/UBSan/no-swap 45-second memory checks pass:

| Scenario | Growth bytes | Peak bytes | All samples | Soak seconds |
|---|---:|---:|---:|---:|
| Handoff | 51,261,440 | 1,329,967,104 | 48 | 45.550778102 |
| Installed IDE | 51,329,024 | 1,055,313,920 | 47 | 45.616870880 |

Growth remains limited to 67,108,864 bytes, peak to 1,879,048,192, within a
2 GiB cgroup without swap. Original workload, concurrency, sanitizers, deadlines
and whole-cgroup measurement remain intact. Handoff growth is higher than the
preceding 30.30 MiB result; no whole-family improvement is inferred from the
isolated epoch-reader allocation correction.

All nine lifecycle repetitions pass: 72 startup families, three Listener
attempts and three 16-case terminal matrices. Actual native ENOSPC, 17 audit
components and independent extraction of the entire 8 MiB fault image pass.
All 16 core/audit archives verify 1,756 overlapping source bindings and 230 raw
audit files; repetitions verify 1,059 overlapping source bindings and 324 files.
The five ancillary workflows pass only within their 241-test portable,
prelaunch Compose/kind, static manifest and development Python inventory scopes.
Test counts overlap.

The installed-IDE sanitizer hour fails; the handoff hour is still running. The IDE archive retains all
472 observations spanning 991.929476709 seconds, peak 2,147,495,936 bytes and one
sampled OOM kill; an original process exits. All 142 exact-overlay sources and
27 raw audit files verify. These are failed sustained observations, never a
one-hour pass or a substitute for mandatory acceptance. Later successful
startups do not explain the historical registration/worker-exit failures.

See [source-bound receipt](evidence/qualification-6dd8218-20261027.json). All eleven full-release groups remain
false. Full original native/driver/763, public launch/debugger/browser/WSS/Git,
deployed Compose/Kubernetes/fault/restore/upgrade/rollback, complete security
disposition and stable joint artifacts/final installation remain unfinished.
There is no stable v0.8 merge, tag or release. Historical records follow.
<!-- checkpoint-6dd8218:end -->

# Native recovery resource acceptance

Dev65 `4f4a5ec` (run `40386646787`) passes 1,284 service tests, 95 overlapping
fault tests, 241 portable tests, 24 fresh startup cycles and all 16 terminal cases.
Twelve of fourteen core jobs and all five ancillary workflows pass. All nineteen
archives and recorded source hashes are verified, and the tested merge tree matches.
Both original families complete the full 45-second soak, preserve all eight
processes and advance every interval with zero memory-pressure/OOM events.
The fixed resource acceptance still fails in both profiles:

| Profile | Peak MiB | Window growth MiB | Required peak / growth MiB |
| --- | ---: | ---: | ---: |
| Handoff | 2,014.3 | 318.7 | 1,792 / 64 |
| Installed IDE | 1,991.6 | 347.7 | 1,792 / 64 |

The IPC and bridge allocation reductions and the bridge identity correction are
verified component changes. They do not resolve this full-family memory blocker.
No sanitizer settings, workload, soak duration, deadlines or resource thresholds
were relaxed. All eleven full-release gates remain unqualified; public runtime
and publication remain disabled. See the [latest complete receipt](evidence/native-codec/dev65-hosted/qualification-summary.json)
and [implementation/measurement notes](NATIVE_MESSAGE_CODEC.md).

Historical qualification records follow.

Dev59 `5d0d64f` completes both original-family soaks and settlement without OOM,
but **still fails** the fixed resource oracle. Handoff records five limit events,
a 2,147,491,840-byte peak and 201,719,808-byte window growth. Installed IDE has
no limit/OOM events but records a 2,133,803,008-byte peak and 206,489,600-byte
growth. Neither satisfies the 1792 MiB peak and 64 MiB growth requirements.
The codec correction and bounded dev60 diagnostic follow-up are described in
[NATIVE_MESSAGE_CODEC.md](NATIVE_MESSAGE_CODEC.md); prior failures below remain
historical evidence. Full recovery and release qualification remain false.

Dev58 `9e954dedc6ba985bc525fcdb1eb170affa2cd5b7` **fails** the new acceptance.
Core run `40369523732` completes with 12 successes and two failures. Both
handoff and installed-IDE recovery lose the original Context during the added
soak. The independent host samples and Docker state agree on an OOM kill.

| Profile | Samples | Peak resident cgroup bytes | Swap peak bytes | Limit events | OOM events | OOM kills |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Handoff | 42 | 2,147,483,648 | 0 | 52 | 1 | 1 |
| Installed IDE | 40 | 2,147,483,648 | 0 | 164 | 4 | 1 |

The original Context is absent from each final process sample; a running
container is therefore not evidence that the original family survived. The
host's pidfd check correctly fails. The successful-soak receipt and subsequent
resource-acceptance receipt are not emitted because the cohort raises first;
their absence is retained as a failed, incomplete qualification, never a pass.
Raw numeric cgroup/process observations and validation-only event denials are
retained in [the evidence directory](evidence/native-resources/qualification-summary.json).

The Context's latest observed live allocations are approximately 10 MiB while
its allocator heap is approximately 500 MiB. Executor and bridge resident
memory also grows. This narrows the investigation to allocation churn and
allocator retention but does not establish the allocation-site cause or prove
an application leak. The next corrective experiment must profile those sites
and preserve the existing sanitizer settings, authority deadlines and fixed
acceptance oracle. Merely increasing limits, shortening the soak or obtaining a
later green rerun would not resolve the demonstrated failure.

Dev57 allocator telemetry separates live allocations from retained allocator heap.
In one Context, live allocations stayed around 10 MiB while the ASan heap grew
past 500 MiB. The 1 GiB resident profile also permitted 1 GiB of swap; its observed
swap peak approached 664 MiB. This does not establish an application leak or
indefinite stability. ASan/UBSan settings remain unchanged.

Dev58 gives the two-Executor recovery probe the same 2 GiB combined budget as
explicit resident memory, with no swap (`--memory 2048m --memory-swap 2048m`).
Other cohorts keep their existing profiles. This is a diagnostic fixture budget,
not a production sizing recommendation. The public runtime stays disabled.

After A→B→A and same-owner reconnect, the original root, child and background
thread must advance in each of nine five-second intervals, with all original
pidfds alive. The fixture-only budget rises from 120 to 180 seconds to include
this added workload; admission, RPC, driver and lease deadlines are unchanged.

The host verifier requires consistent container identity, complete sampling,
zero swap, zero memory-limit/OOM events, peak resident usage at most 1792 MiB,
and no more than 64 MiB growth between median resident memory in the first and
last ten seconds of the 45-second soak. These thresholds are fixed before the
candidate executes. Failed or missing evidence fails the cohort and is retained.
A pass applies only to this workload and duration, not to a full release gate.

A separate real TLS regression showed explicit empty native events returning
400 at dev57. The frozen v0.7 event/display-buffer port deliberately supports
empty events. Dev58 preserves them as authenticated, idempotent audit records;
the 8192-byte bound, severity/scope rules, ownership and grant checks remain.
Dev57's unclassified RaiseEvent denial remains separately open until its cause
is established; later passes alone are insufficient.
