# Native startup diagnostics and fresh-family stress

Development candidate `0.8.0.dev45` added observation of the existing native
startup path. It changes no admission decisions, native scheduling, retry policy
or timeouts. The historical root-LOADED failure and the dev44 admitted-child
failure have no established cause. A subsequent passing run is not a fix receipt.

## Retained evidence

The composed native source writes one bounded `V08_START` JSON line per stage.
A successful member traverses twelve markers: entered, admitted, ipc-ready,
spawn-requested, fork-entered, fork-returned, process-started, login-entered,
login-published, login-observed, binding-requested and member-bound. A failed
fork can emit fork-failed. Each record contains only a fixed stage, PID,
monotonic timestamp and opaque member correlation key. The key is not an
authorization token or a cryptographic identity proof.

`host_runtime/native/startup_trace.H` uses one best-effort bounded write per
record. The marker code runs in the existing parent-side startup boundaries;
it introduces no child-side allocation after fork. Frozen source composition
and unique patch anchors are checked before compiling the candidate runtime.

`host_runtime/python/startup_diagnostics.py` reads a bounded process/task
snapshot and the fixed stage records. It never reads arguments or environment
variables. It permits only named runtime executables, limits process/task and
trace counts, and rejects malformed records. The worker emits this snapshot
before session cleanup. The qualification collector also captures a snapshot
from a still-live stalled worker before removing its container.

To investigate a failure, retain the original artifact and its SHA256 first.
Check the exact candidate and source hashes, then inspect the failed worker's
`*.startup.json`, `native-startup-diagnostics` event and native log. Group stages
by member key and inspect the last observed boundary alongside task state and
kernel wait channel. Absence of a marker narrows the observation; it does not
alone establish a cause. Keep child admission, member-binding and final native
RUN consumption as separate events when comparing the Context journal.

## Executed stress profile

```bash
python scripts/qualify_v08_native_launch.py --native-startup-stress
```

CI builds the immutable candidate native image and executes the existing
ten-worker root/child cohort, then creates 24 additional fresh root/child
families. Every cycle has new credentials, Context state and a single-use
worker. It waits for actual child execution, closes the active child, proves
original process exit and independently settles the family before releasing
its reservations. The unrelated witness remains reserved. Each completed
cycle retains its evidence before its Context/container/network are retired.

The same image is reused; consumed workers and failed operations are not.
Twenty-four passing cycles establish that bounded executed sample. They do
not establish the cause of either historical intermittent failure or promote
the full native-family release gate. Exact outcomes and source identities are
in the [component receipt](evidence/repeated-handoff/qualification-summary.json)
and [stage evidence index](evidence/repeated-handoff/startup-diagnostics.json).

## Current dev54 follow-up failure

Candidate `f1ea033` / run `40275195710` fails both native terminal and startup
jobs in their initial ten-worker root/child cohort. Neither reaches its later
sixteen-case terminal matrix or twenty-four fresh-family cycles. Four terminal
workers reach child binding but lose the reply at the original four-second
native deadline; the agent records late BrokenPipe replies. A startup worker
reaches process-started without login and retains a child PID whose executable
is still SPELL-Context, with sleeping futex tasks. These observations distinguish
two investigation paths; they establish neither underlying cause nor a fix.

[The failure receipt](evidence/dss-lifecycle/native-blockers.json) retains exact
job/artifact/source identities, both failed results, five worker event logs and
process snapshots. Diagnose binding queue/dispatch/transport timing separately
from fork-to-exec progress. Uncertain starts stay spent; no timeout extension,
automatic replay or later green run can substitute for a demonstrated correction.

## Dev55 follow-up

The parent launch markers now use `spawn-entered` and `spawn-returned`; the
parser retains older fork stage names for historical logs. Bounded
`native-admission-timing` records cover successful and failed callbacks.
[The spawn correction](NATIVE_SPAWN.md) and
[dev55 receipt](evidence/controller-network/qualification-summary.json) retain
passing terminal and fresh-family profiles. These samples do not establish the
causes of the retained dev54 binding and pre-login failures.
