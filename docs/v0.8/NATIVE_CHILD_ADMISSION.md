# Retained child admission authority (development)

Server `0.8.0.dev16` adds explicit Context option `native_children: admission-only`,
requiring the approved catalog, certificate-bound preflight and
`worker_launch: retained-single-use`. Defaults have no child routes. This is
**authority/RPC qualification only**, not native child start/family-pause,
teardown or repeat-semantics qualification.

## Immutable admission and one consumption

Both exact worker-protocol-2 routes require the original assigned certificate,
unchanged parent start grant, current owner/session permissions and the original
single-consumption winner's memory-only proof. Child routes have no pause-report
exception after revocation or fencing.

| Route | Additional payload fields |
|---|---|
| `/v1/worker/child-admit` | request_id, parent_admission_id (null for root parent), entrypoint, arguments_sha256, mode |
| `/v1/worker/child-consume` | child_grant |

`mode` contains exactly Boolean `automatic`, `visible`, `blocking` fields. The
arguments digest, complete mode and request ID bind to the unchanged parent
origin; Context does not stamp its current epoch onto a delayed child request.
The child must be explicitly cataloged at the parent's original revision with
identical complete file inventory, runtime image and driver binding. A catalog
update cannot rebind an admitted parent. Traversal/unapproved bindings fail.

Under the per-execution admission mutex and a short SQLite transaction, Context
reserves the canonical child ProcedureID in the **same namespace** as top-level
runs, journals admission and returns one random child token. Two parents,
alias/top-level races and recursion cannot obtain another logical hold. Nested
parents must be consumed admissions of the same original family. No network or
native wait occurs inside that mutex/transaction.

Schema 10 stores immutable bindings/token hashes, not plaintext authority or
arguments. Only the initial response delivers a token. Identical replay returns
redacted state and `token_delivery: unavailable`; changed payloads conflict.
Consumption is exactly once; lost delivery cannot authorize retry or native
start. Replies state `native_start_qualified: false`. Admission/consumption do
not observe physical native launch. A child does not consume another pool slot
or supply driver authority. No timeout, FINISHED, kill/close or replay releases
holds. Restart invalidates grants/admissions and retains reservations. Audit
failure rolls back reservation/admission or consumption. At most 64 child records
are retained per Context; older binaries cannot reopen schema 10.

## Tested authority and remaining native boundary

Real mTLS checks cover 100 admission races, exactly-one consumption, nested and
alias/top-level collisions, copied proof, catalog changes, forged identity,
revocation, transfer fencing, audit rollback and restart retention. Root
`/consume` is distinguished exactly from `/child-consume`; suffix matching cannot
bypass the consumption-winner proof.

The mandatory native before-RUN hook remains **unimplemented**. The retained
agent does not invoke these routes and continues rejecting unqualified child
notifications. That observer is not a before-RUN gate. A native provider must
enforce admission before every visible/hidden, automatic/manual and
blocking/nonblocking child start, inherit immutable family identity, and qualify
prompt/return/repeat/termination semantics. RPC checks do not promote that gate.
Whole-family queue/effect settlement, handoff/resume and recovery remain release
blockers.


## Verified candidate

At **7d2ab39951e3e250aa5bbb43633641fbd5254a3c**, hosted
[services/native CI](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020149313)
passed all six jobs, including 344 scoped checks (28 child-authority and 12
publication-preflight cases), package checks and the existing native cohorts.
[241 portable checks](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40020147843)
passed. The downloaded foundation artifact passed ZIP digest/CRC checks and all
111 recorded source hashes matched. The [receipt](evidence/child-admission/qualification-summary.json)
qualifies only this authority/RPC component. Native child execution and full
v0.8 remain unqualified. Full publication preflight still exits nonzero.
