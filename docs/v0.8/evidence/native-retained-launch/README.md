# Retained native qualification summary

qualification-summary.json records the verified c8b286c native compute result,
public source hashes and workflow references. It intentionally omits raw logs,
host/endpoint/process/execution identities, private paths and credentials.
Original detailed artifacts remain in their existing GitHub Actions runs.

Ten real native procedures ran together; thirty distinct native processes were
verified. All ten containers terminated, twenty lifecycle events were durably
journalled and every logical/worker hold remained retained. The positive
handoff attempt occurred after container termination and remained BLOCKED;
there is no native quiescence/owner-CAS pass.

Failure history is retained in CI. Missing aliases and strict CA key usage
prevented initial startup. A resource/startup failure had its original cause
masked by cleanup; later runs preserve both errors and use verified baseline
resources with staggered startup. The concurrency requirement stayed unchanged.
Native controllers themselves emit lifecycle events; denied real EV calls
correctly failed earlier completion tests. Actual durable Context event handling
resolved that issue without fabricated acknowledgements or ignored errors. The
separate metadata overload failure led to bounded v0.8 client admission, with no
legacy transport/preimage edits or effect retries.

The c8b286c candidate also passed the physical cloned-worker denial check and
218 scoped tests, including event quota/race regressions. A new container using
the original certificate, incarnation and spent grant failed before native
startup. The same-candidate portable compatibility PR passed 241 tests. Full v0.8 remains unqualified: external native TC/TM, safe
pause/child/handoff/recovery, IDE native execution/browser/WSS, complete
compatibility, production deployments and independent release/security gates
remain pending.
