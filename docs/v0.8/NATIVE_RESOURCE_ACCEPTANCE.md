# Native recovery resource acceptance

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
