# DSS lifecycle and uncertain-reply qualification

Candidate `f1ea0337c89838a637c5e58896aaae09994be86c`, server `0.8.0.dev54`, adds
eighteen lifecycle checks to the dev54 fault suite. Production runtime code is
unchanged from qualified source `1182388`. The paired IDE remains
`1ac0b8a` / `1.2.1.dev4`. These are driver/authority components; full v0.8
publication and the driver-fault release gate remain unqualified.

## Executed stage matrix

Each of the five stages is tested with three one-shot failures after the DSS
commits its real stage result and before its production TCP handler writes the
acknowledgement: abrupt process exit, connection close, and a 2.5-second reply
stall crossing the original two-second command deadline. The test-only fault
selector is confined to a separate test subprocess; no production API or retry
path is introduced.

| Failed reply stage | Earlier ACKED stages | Uncertain stage | External commands executed |
| --- | ---: | --- | ---: |
| TRANSPORT | 0 | TRANSPORT | 0 |
| LOADING | 1 | LOADING | 0 |
| RELEASE | 2 | RELEASE | 1 |
| ACKNOWLEDGEMENT | 3 | ACKNOWLEDGEMENT | 1 |
| ONBOARD_EXECUTION | 4 | ONBOARD_EXECUTION | 1 |

All fifteen cases use actual worker mTLS, the Context and driver SQLite ledgers,
and a separate DSS PID. The DSS restarts on the same database and endpoints
with a different PID and the original epoch. Both ledgers preserve the earlier
receipts and uncertain stage. The execution remains `RECOVERY_REQUIRED`, its
worker stays spent, and its reservation remains held. Both the original key
and a fresh key are denied. DSS ingress counts stay exactly one per sent stage,
so server-side deduplication cannot conceal an attempted resend.

## Restart, reset and independent executions

A completed five-stage call survives DSS restart: its old key remains denied,
and an explicitly requested distinct command completes once under the still-live
original grant. An explicit isolated scenario reset changes the DSS epoch;
the existing driver keeps its old binding and sends zero binary command stages.
No automatic rebinding or retry is permitted.

The ten-execution test stalls one RELEASE reply while nine independent original
grants complete all five stages. The nine complete in **370 ms**,
within the existing two-second budget. One execution becomes recovery-required;
the other nine grants remain valid. All ten reservations and spent slots remain
held, and every delivered stage has count one. This load case calls the actual
authority/driver gate directly; it does not attest worker mTLS, native process
identity or Kubernetes Pod identity.

## Qualification and retained failure

[The complete run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40275195710) passes **1,193 service tests**, the separate
**55 overlapping fault probes** and **241 portable tests**. **Twelve of fourteen
core jobs** and all **five ancillary workflows** pass; the core workflow fails
because the native terminal and startup profiles time out in their initial
ten-worker child cohort, before their terminal/stress scenarios begin. There are no failed, errored or
skipped tests in those three suites. These overlapping counts are not additive.
All nineteen artifact digests/ZIPs and recorded source hashes are verified.
Foundation records 196 source inputs;
the fault suite records 178. Candidate
and CI merge trees match. [The source-bound receipt](evidence/dss-lifecycle/qualification-summary.json) is explicitly
failed overall, with the DSS lifecycle component marked passed. Native handoff,
IDE and observers pass. [The native blocker receipt](evidence/dss-lifecycle/native-blockers.json)
retains both failures and the five affected workers: four binding replies exceed
the original four-second deadline, and one forked child remains in the Context
executable without login. Their causes remain unproven. The [eighteen lifecycle
traces](evidence/dss-lifecycle/dss-lifecycle.log) retain the passing driver component.

The initial `3802e73` fault run failed with three failures and seven setup
errors because the new test-only SQLite delivery reader was not explicitly
closed. CPython 3.13 reported fatal unclosed-connection warnings, sometimes
during later test setup. The correction closes each reader and reaps failed
subprocesses. The local actual-reader check confirms the old helper leaves its
connection usable and the corrected helper closes it. The [failed attempt](evidence/dss-lifecycle/initial-attempt.json),
original JUnit/logs, source hashes and archive digest remain retained. Warning
handling, operation deadlines, assertions and production code are unchanged.

These declared faults establish safety under the executed boundaries. They do
not establish the cause of historical dev52 command timeouts or native startup
failures. Broader partitions, controller/network-loss recovery, deployed storage
failure, native/OS review and the remaining full-release requirements still need
qualification. All eleven full-release gate groups remain false.
