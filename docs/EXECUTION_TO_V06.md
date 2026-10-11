# Execution through v0.6

Authorized target: finish and commit each release in order through plugin v0.6,
including prerequisite changes and qualification in the sibling openbexi_ide.
The working IDE v0.2 / bounded plugin v0.1 remains the testing baseline while the
original-source runtime is developed in isolated environments.

| Release | State | Required evidence |
| --- | --- | --- |
| v0.2 | In progress; source alpha 0.2.0a1 complete | Native UTIL/DTA link/load, references and errors; EXC control flow; WS recovery; real context/EXEC/CIF setup/cleanup |
| v0.3 | Pending v0.2 | Installed OpenBEXI extension and actual IntelliJ/PyCharm plugin ZIP, verifier and host Run/Debug/removal |
| v0.4 | Pending v0.3 and IDE service prerequisites | Original driver RPC families through DSS, three operating modes, controller fencing and uncertain-effect recovery |
| v0.5 | Pending v0.4 | Every inventory requirement assigned and independently qualified, source/manual conflicts resolved |
| v0.6 | Pending v0.5 | Reproducible distribution, platform matrix, clean installation/removal, upgrades, actual host and DSS-container workflows |

Native work starts with public CPython 3.13 frame/compiler APIs and Python error
ownership in UTIL. DTA keeps the original native types; EXC and warm-start need
behavioral qualification beyond compilation. No compatibility shim may pretend
that removed interpreter stacks or unsupported executor services work.

The first [native UTIL milestone](NATIVE_PORT.md) now links and runs under address
and undefined-behavior sanitizers. Sixteen behavior tests and three owned
interpreter cycles pass. DTA compiles, while its runtime and EXC/WS integration
remain the next v0.2 gates; no later release has been promoted. The original
multiline and line-table analyzers now pass 15 additional runtime checks, bringing
the native syntax probe to 47 of 63 passing units. Static Step/Goto analysis adds
11 passing checks (26 analyzer tests total), including C trace jumps, and brings
the syntax probe to 48 of 63. Full native bindings, bytecode control and warm-start
still require substantive compatibility work.

The [recovery feasibility investigation](RECOVERY_DESIGN.md) passes six isolated
checks using an exact-version private frame adapter. It is not shipped or counted
as full WS recovery; persistence and the original executor integration remain open.

The original [WS storage layer](WS_STORAGE.md) now has 17 passing integrity,
ownership and fresh-process checks. The complete frame graph, atomic checkpoints
and original executor recovery have not yet passed their release gates.

The [variable-monitor port](VARIABLE_MONITOR.md) adds 17 live-frame checks,
bringing the analyzer/watch suite to 43 and the syntax probe to 49 of 63 units.
Ordinary frame inspection and edits use supported CPython APIs. Remaining
executor/WS work is not replaced by the isolated recovery feasibility experiment.

The original [bytecode analyzer](BYTECODE_ANALYSIS.md) adds 14 checks for modern
instructions and source scopes. Analyzer/watch checks now total 57; UTIL has 16,
storage has 17, and three embedded cycles pass. The syntax probe is 50 of 63.
Full executor/service/context and WS recovery integration remain the v0.2 gates.

The [executor frame-access milestone](EXECUTOR_FRAME_PORT.md) adds two passing
utility checks (18 total) and ports the model and two dispatchers. Reading the
original Python 3 Makefiles corrects the inventory: 143 library units across 16
libraries, 135 passing compilation/syntax checks and eight remaining failures.
Python 2-only handlers are excluded by the upstream build, not silently replaced.

The [persistent recovery experiment](PERSISTENT_RECOVERY.md) passes 13 checks
through the real WS storage plus eight in-memory checks. It proves selected
single-frame continuations after SIGKILL in a fresh process, including shared
globals and exception context. Nested callers, original executor integration and
DSS effect recovery remain open; this does not close the v0.2 gate.

The [caller recovery experiment](CALLER_RECOVERY.md) adds eleven fresh-process checks
for logical nested continuation, arguments, closures and exception propagation.
It rejects native C-call boundaries and does not reconstruct physical caller
frames. Original executor/WS integration and DSS effect recovery remain open.

The original [frame factories](FRAME_FACTORY.md) now release their references
correctly across repeated loads. UTIL has 21 passing checks; the library inventory
is 138/143 after isolating private WS headers. The remaining five source failures
are the frame manager and four WS implementation units.

Existing source-alpha evidence is the historical `source-v0.2.0a1` snapshot.
The [frame-manager component port](FRAME_MANAGER.md) adds twelve runtime checks
for live script edits, frame ownership, database sharing and WS filter lifecycle.
The original library inventory is now 139/143; four WS implementations remain.
Full evaluation/recovery, DTA and context integration still gate v0.2.

The [DTA native type milestone](DTA_RUNTIME.md) adds 18 isolated-process checks
and 3,000 container lifetimes across three more interpreter cycles. Native data
ownership, conversion and missing-executor errors now pass. DTA notifications
and prompts through the real CIF remain part of the executor integration gate.

New evidence must identify its exact source and patches. Release tags are created
only after the corresponding acceptance gates pass. Cleanup removes only
demonstrably obsolete project resources and preserves active test services.

The original [cold execution path](COLD_EXECUTION.md) adds eight passing checks
using live CPython frames, original result flags and a qualification dispatcher.
Warm continuation and the full executor/context/CIF dispatcher remain open.

The original [WS frame/data controllers](WS_FRAME_DATA.md) add twelve passing
checks and use the same continuation engine as the recovery experiments. The
inventory reaches 142/143; the top-level WS controller and its whole-stack
integration are still required. The shared engine has 38 passing probe checks.

The [original WS controller and manager recovery](WS_CONTROLLER.md) now add
fourteen integrated checks, including crash recovery and repeated checkpoints
with pending callers. All 143 original library units pass compilation/syntax
checks. Native DTA checkpoint serialization and the actual executor/context/CIF
lifecycle remain the next v0.2 gates; later releases remain pending.

The [native DTA checkpoint milestone](DTA_CHECKPOINTS.md) adds twelve serialization
cases and three integrated procedure crash recoveries with shared native data.
The actual executor/CIF bindings, dispatch and context lifecycle are next;
v0.2 remains in progress and v0.3–v0.6 remain pending.

The [original standalone executor](EXECUTOR_COMMAND.md) now links its 120 source
units and passes 17 command checks with its real dispatcher and automatic CIF.
Explicit imports, native data, Step/Goto, prompt validation, error exit codes,
live output and owned shutdown are covered. Actual executor warm recovery and
context/service integration still gate v0.2; later releases remain pending.
