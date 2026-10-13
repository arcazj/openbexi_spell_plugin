# Native Until and Message checkpoint

Nine actual traced main.py procedures qualify two COMMON rows: Until and Message.
Each row has positive, boundary, failure and recovery checks; a separate integer
Interval control checks the existing behavior. This does not qualify the whole
WaitFor function, telemetry waits, interruption/resumption, Delay, all Interval
semantics or other cross-family modifiers.

LRM 2.4.4 pp112-113 require an absolute Until target and allow TIME or date/time
text. Pages58-59 describe Message updates at Interval boundaries alongside the
remaining time. The native tests use independent Python UTC/monotonic clocks,
original WAITING/FINISHED states, exact MSG_WRITE text and actual decreasing
COUNTDOWN notifications terminating at SUCCESS/0. No registry/helper/scheduler
method is replaced. The controller retains all original as-run traces.

The baseline image627f1b3a529e3581618dc739a4f0029c11e29f8ca654a58b284076f9214db708
failed five of eight initial scenarios. Until=1 was accepted as a relative
one-second wait. A malformed date left pending Python exception state and escaped
as SystemError, preventing a procedure from catching the original SPELL failure.
Fractional Interval values (.6 and .2) produced no Message, although countdowns
continued. An independent integer-Interval control passed on the same baseline.
The failed raw run remains at `.qualification/v0.5/scheduler/76bd037b0ef04fca8d570379a2e97b28`;
the passing control remains at `scheduler/110216d46b3446698bdc24e2c7897757`.

Three checked changes preserve the original source and notices:

* `SPELLexecutorUtils.C`: modifier-only Until now calls the existing
  setTimeCondition parser, which rejects numbers and relative times.
* `SPELLexecutorPython.C`: Executor_StartWait clears a pending Python exception
  before constructing the public SPELL exception in its existing catch block.
* `SPELLscheduler.C`: notification-period positivity compares complete SPELLtime
  values. The unsigned-seconds overload previously ignored fractional fields.

Future absolute TIME and string targets cannot finish before their UTC deadline.
Past targets, including epoch zero, return promptly. Numeric, relative and
malformed Until values fail before WAITING, and a later valid target recovers in
the same executor. Progress messages preserve UTF-8 and newlines, use ordinary
and list intervals, and have independent minimum count/spacing checks. Missing,
empty and non-string messages fail before waiting, followed by valid recovery.

The candidate is `sha256:98ed7bca58beade4a871c325c07f9e857ec479a504efa6d3de2892829948e2aa`.
It derives from exact integrated diagnostic
`sha256:dc15d9f1f6de3ab00a8a90bc70c0bd2a7bab473b0e18202ea1df087d1085b471`:
the complete composed spell tree and all six runtime binaries are carried
together. Thus it also retains the newer native IPC/TIME and Python Verify fixes.
That diagnostic originally failed an obsolete DTA test fixture combining mutually
exclusive Range and Expected; it is not represented as an accepted release.
The scheduler overlay is a separate candidate and does not mutate the independent
full-build pair or historical accepted images.

`source_port/scheduler_patches.py` checks the original archive and exact ported
preimages. The build retains original/ported/patched source, recipes, compiler
commands, binary hashes and both inherited composition manifests under
`/opt/scheduler-native-patch`. Compiler and runtime base tags were checked against
the exact image IDs before and after the retained build. Native manifests and
actual installed files are hash-bound into the runtime report.

Run `python conformance/run_scheduler.py --image <exact-image>` and then
`python conformance/scheduler_report.py <raw-result.json>`. The report requires
all nine clean native results, real as-run traces, both complete four-dimension
sets and matching source/runtime hashes. It qualifies only the two named rows;
full v0.5 and dependent v0.6 acceptance remain false.
