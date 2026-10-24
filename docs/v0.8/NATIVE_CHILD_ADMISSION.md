# Retained child admission authority (development)

Server `0.8.0.dev16` introduced explicit Context option `native_children: admission-only`,
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

The default retained profile continues rejecting child notifications. The
separate dev17 native provider below now invokes these routes before physical
spawn. An OPEN observer alone is not a before-RUN gate. A native provider must
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

## Qualified automatic before-spawn component (dev17)

The separate `--native-child-gate` profile builds a new native Context executable
from the frozen v0.7 image's own source archive and recipe provenance. It requires
exact reproduction of that composition and checked original translation-unit
hashes before adding a gate at the beginning of `SPELLexecutor::start()`. The
check precedes IPC setup, process replacement and physical spawn, covering the
supported visible/hidden and automatic/manual child paths. Services, reconnect,
warm recovery and conditional starts are explicitly denied in this profile.
Published v0.7 binaries and source recipes remain unchanged.

An agent-owned Unix endpoint authenticates the exact Context executable, its
owned Listener parent and its original process incarnation using Linux
`SO_PEERCRED` and `pidfd`. Native Context authenticates the agent's PID and UID.
The initial root must match the consumed root source, arguments and mode. Each
child must have an admitted parent; original-family mTLS admission and one-time
consumption both complete before the native callback can proceed. Native
arguments bind by SHA-256 of their exact UTF-8 representation; they are not
executed or logged by the provider. Lost replies, changed identity, duplicate
native instances and failed live authorization deny launch and retain holds.
The approved catalog now admits up to 64 entries to include children, while the
worker pool remains bounded at ten and child admissions at 64 retained records.

The existing OPEN observer is retained as an additional consistency check, and
the original visible-child client sends its initial RUN once. It is not the
admission boundary. The new native cohort requests ten roots and ten children,
checks simultaneous physical processes and consumed authority rows, and retains
all twenty logical holds. At `b644d56223f0a859819c19afef0f5f5b1d18a06e`, the
[hosted child job](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40041544143)
passed: ten roots and ten automatic blocking children (five visible/five hidden),
forty native PIDs, actual argument transfer, direct native GUI and same-UID peer
denial, spent-grant physical clone denial, and thirty-five original lifecycle EV
receipts. Hidden automatic children preserve the original absence of a start EV;
none is fabricated. ZIP digest/CRC and all twenty-three repository source hashes
were independently checked. See the [redacted receipt](evidence/native-child-start/qualification-summary.json). Manual mode, nested native execution, denied
native starts, child prompts/returns/repeat, native driver attribution and
whole-family settlement still need their own native qualification. The RPC
mode/nested tests alone do not establish those native behaviors. Public runtime,
effective transfer/resume, recovery and full release gates remain disabled or
unqualified.

The original native manager assigns its first child instance suffix `#0`.
The provider accepts canonical zero-based suffixes while retaining exact source,
parent, grant, one-consumption and replay checks; negative/padded suffixes remain
invalid. Native instance numbers are not authority epochs.

The agent now requires `PR_SET_DUMPABLE=0`, verified by `PR_GET_DUMPABLE`, before
reading configuration or spawning native processes. This protects its memory-only
consumption proof independently of same-UID ptrace defaults. Workers must still
drop all capabilities, including `CAP_SYS_PTRACE`. The kernel documents this
boundary in [Yama](https://docs.kernel.org/admin-guide/LSM/Yama.html). A real parent
memory-reader test includes a successful read before protection and denial after
protection; unavailable positive controls fail rather than count as protection.
This is agent-memory protection, not an arbitrary-procedure sandbox or full
family-participant/recovery proof.

At **9bbae553b863b40129111f2d904a5cdf33891706**, the expanded hosted native
cohort also completed one visible automatic blocking grandchild under child 0.
The trusted host verified 41 simultaneous native PIDs, eleven consumed child
admissions, the exact consumed same-family parent link, 37 original EV receipts
and 21 retained logical holds. The archive digest/CRC and all 23 source hashes
were verified; see [nested receipt](evidence/native-child-start/nested-summary.json).
This qualifies that nested component only. Other modes, denied/error/prompt/return
semantics, driver attribution and full-family pause/handoff/resume remain pending.
