# Cooperative background Python barrier (development)

Server development version `0.8.0.dev15` retains the dev14 fenced native pause
contract. The additional **private qualification profile**
`--native-thread-barrier` installs a candidate GPL host session and a fixed
operator library from a read-only mount. Its worker config requires both
`pause_probe: true` and `thread_barrier_probe: true`; Context still requires
`native_pause: fenced-probe` and retained single-use workers. Defaults, the
published v0.7 image and the original native patch preimages are preserved.

The component uses CPython 3.13 `sys.monitoring` LINE callbacks in tool slot 3.
It does not replace the native debugger's existing trace. An occupied tool slot
fails startup. Only code filenames inside the approved immutable snapshot are
observed. The entrypoint module identifies the main procedure thread, which
remains the responsibility of the original native pause controller. Other
observed Python threads acquire a retained identity and acknowledge a one-shot
barrier before executing their next monitored line. A thread first entering
snapshot code after pause is requested also parks before that line.

This is **cooperative observation, not a security boundary or complete thread
inventory**. Dynamically generated code, libraries outside the snapshot, native
threads/extensions, asynchronous I/O and child processes are not covered.
Procedure code can interfere with Python instrumentation; security and hostile
procedure qualification are separate gates. An observed thread that disappears
without acknowledgment remains unproved; it is not removed by a PID/liveness
scan. Native children and control/prompt queues remain unqualified. No Context
endpoint accepts this component as positive whole-family proof.

## Bounded private protocol

The operator library starts one diagnostic helper on **127.0.0.1:36991** inside
each isolated worker. There is no host bind, Docker socket, added privilege or
management service. Procedure code in that container can request a hold; this
route cannot grant ownership, admit effects, release holds, or resume anything.
It is not a controller transport. The host qualification checks its actual
loopback bind. Worker network isolation remains independently tested.

One bounded JSON line (256 bytes maximum) accepts exactly `action` and a canonical
UUID `barrier_id`. Actions are `pause` and `snapshot`; **there is no resume**.
The first pause binds the single-use barrier and one-second monotonic deadline.
Identical replay preserves that deadline; another identity is rejected. Capacity
is bounded to 64 observed participants and 2048 monitored snapshot code objects.
Deadline expiry, missing participants, capacity exhaustion or monitoring
configuration changes cannot produce an observed-thread success. Late
acknowledgments do not clear an expired result. Parked threads remain held after
deadline expiry, lost responses, invalid requests or authority-channel loss.
Independent host teardown owns qualification cleanup.

Reports expose counts and scope, never grants, certificates, source or memory.
Even an observed-thread acknowledgment always reports `quiescence_proven: false`
and `effective_transfer: false`. The worker then requests original main pause
and sends the existing status-only diagnostic to Context. Lost delivery reuses
the cached diagnostic; it does not redo pause or consumption.

## Qualification and limits

The new real-CPython component checks cover concurrent threads, a late entrant,
C-call timeout/late acknowledgment, a disappeared participant, original tracing,
monitoring configuration changes, local protocol identity/replay and denied
resume. A separate native matrix cohort must run at the candidate SHA. It
requires main B PAUSED **and a stable background counter**, one observed thread
acknowledged, nine unrelated native completions, unchanged owner/epoch, retained
holds and bounded unrelated-controller latency. The original negative probe
must still demonstrate that main pause alone leaves the counter advancing.

Local component checks do not qualify native integration. A passing native
thread cohort qualifies only this observed Python-thread component. Successful
whole-family pause, child admission, effect/queue settlement, ownership CAS and
an explicitly admitted new-owner resume remain unfinished. Public runtime and
`native_pause_qualified`/`full_v08_qualified` remain false. See
[NATIVE_PAUSE.md](NATIVE_PAUSE.md) and [TEST_REPORT.md](TEST_REPORT.md).

Reference: [CPython 3.13 execution monitoring](https://docs.python.org/3.13/library/sys.monitoring.html).
