# Controlled reliability fault reproduction

Dev54 adds a reproducible fault suite, fixes a confirmed native admission
deadline defect, and corrects prelaunch readiness and image-version checks.
The causes of the retained dev52 DSS timeout and historical native startup
failures remain unestablished. These controlled experiments
provide diagnostic signatures; they do not retrospectively identify a cause.

Run `python scripts/qualify_v08_faults.py` on Linux with the pinned
`server/requirements-test.lock` tools. The runner retains its source hashes,
JUnit result, complete test log and bounded `reliability-faults.jsonl` records,
including failed attempts. Its separate CI job now runs 55 cases and rejects skips. The original 37-case
checkpoint below is extended by [eighteen DSS lifecycle cases](DSS_LIFECYCLE.md).

## Confirmed defect and correction

The production native wait checked its absolute deadline before `poll`, then
accepted readiness without checking the clock again. A thread resuming after
its deadline could therefore accept stale readiness. The compiled reproducer
delays delivery of real pipe readiness by 350 ms: before the fix, a 300 ms probe
returned success at 360 ms. That regression fails on the original header and
passes after the correction. [The local before/after evidence](evidence/fault-reproduction/native-deadline-regression.json)
retains both results.

Admission now checks the original deadline after readiness and again before
accepting a complete `ALLOW` reply. Hosted tests also delay consumption of a
real Unix-socket reply beyond four seconds and require rejection. The production
four-second deadline is unchanged. No reconnect, request replay, new grant or
deadline extension was added.

## Executed fault signatures

The timings below are from the first dev54 attempt, `fb04f3d`, retained in
[the initial trace](evidence/fault-reproduction/initial-fault-signatures.log).
The final exact candidate repeats all 37 probes successfully and retains its
own [trace](evidence/fault-reproduction/reliability-faults.log).

The DSS cases use real worker mTLS, actual Context and driver SQLite ledgers,
and a separate DSS process. Each command uses the existing two-second option.
Uncertainty recording may finish after that effect deadline; no later command
stage is authorized by the expired deadline.

| Injected fault | Observed timing | Durable result | External commands |
|---|---|---|---:|
| Writer held before RELEASE admission | RELEASE send/admission fails after 2,161 ms | TRANSPORT and LOADING ACKED; no RELEASE intent | 0 |
| LOADING receipt commit delayed | LOADING settlement takes 2,167 ms; next RELEASE deadline fails | TRANSPORT and LOADING ACKED; no RELEASE intent | 0 |
| DSS RELEASE receipt delayed | RELEASE receipt wait fails after 1,973 ms | Two ACKED stages and RELEASE UNCERTAIN | 1 |
| DSS RELEASE receipt dropped | RELEASE receipt wait fails after 1 ms | Two ACKED stages and RELEASE UNCERTAIN | 1 |

All four executions retain their reservations, spent workers and recovery fence.
Both an original-key retry and a new-key attempt are denied without another
send or external execution. The retained dev52 report contains aggregate counts
of twenty ACKED rows and ten uncertain calls; it lacks the phase timings needed
to distinguish a writer wait, commit delay or other pre-send scheduling delay.

The post-binding cases use the compiled production Unix client and real Context
mTLS/member persistence. The admitted peer role and process pins are explicit
fixtures; these cases do not attest a native process tree or immutable image.

| Reply after durable member binding | Native outcome | Provider observation |
|---|---|---|
| Timely | ALLOW accepted at 14 ms | One binding and one connection |
| Dropped | `reply_lost` at 6 ms | Binding followed by reply-phase `BrokenPipeError` |
| Delayed 4.2 seconds | `deadline_expired` at 4,003 ms | Binding followed by reply-phase `BrokenPipeError` at 4,206 ms |

Each case retains one `REGISTERED_UNPROVEN` binding and its reservation.
Rebinding the same member or replacing its PID is denied. The two failure modes
produce the same provider-side error but different native reasons, demonstrating
why both sides are needed to diagnose the historical acknowledgement loss.

## Prelaunch readiness and version regression

The first dev54 attempt passed all fourteen core jobs but failed the kind
probe with Context B HTTP 503. Readiness had checked only Context A.
The correction requires A and B in the same successful read-only health pass
within the original shared 65-second budget. TLS pin mismatches still fail
immediately; mutating acceptance operations are not retried.
Docker/Compose/Kubernetes image markers also now agree with package dev54.
Five local regression cases go from four failures to five passes.
[Before/after evidence](evidence/fault-reproduction/prelaunch-readiness-regression.json)
retains the original error, artifact digest and workload status. The underlying
reason for B's transient HTTP 503 is not established by this readiness repair.

## Qualification boundary

Exact candidate `11823881f0c1c5daf770611687ae21ce41aec271` passes
**1,175 service tests**, **37 overlapping fault probes** and **241 portable
tests**, all with zero failures, errors or skips. All **fourteen core jobs**
and **five ancillary workflows** pass, including both Compose and kind
before/after restart checks with dev54 images.
All nineteen archives match their GitHub SHA-256 digests and pass ZIP integrity;
every recorded repository source hash matches the candidate. Foundation records
194 inputs, the fault suite 176, and the portable subset 191. The candidate and
CI merge trees are identical.
[The final receipt](evidence/fault-reproduction/qualification-summary.json) records full source identity,
native profile checks and explicit scope limits.

All eleven full-release gate groups remain unqualified. The next historical
diagnosis requires a captured spontaneous failure with phase timings and both
native/provider records, or a reproduction establishing the same causal
mechanism from the original evidence. These injected faults and subsequent
passing native samples do not establish the historical causes.

The current test/harness candidate `f1ea033` passes all 55 fault cases and 1,193
service tests. Production runtime is unchanged from the dev54 checkpoint above.
[The lifecycle receipt](evidence/dss-lifecycle/qualification-summary.json) retains the expanded result and failed harness attempt.
