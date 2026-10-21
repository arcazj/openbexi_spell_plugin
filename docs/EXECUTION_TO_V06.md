# Execution through v0.6

The execution target now extends through stable v1.0, with each accepted release
committed and pushed to GitHub master. See [the current plan](STABLE_RELEASE_PLAN.md).
This document retains the foundation and v0.6 prerequisite history, including
changes and qualification in the sibling openbexi_ide.
The working IDE v0.2 / bounded plugin v0.1 remains the desktop testing baseline.
The original-source native foundation v0.2 is now qualified in its separate Linux
environment. Local host v0.3 and GENERIC DSS drivers/modes v0.4 are accepted;
IDE v0.3 supplies the neutral durable authority. Full v0.5 language conformance and v0.6 distribution are accepted.

| Release | State | Required evidence |
| --- | --- | --- |
| v0.2 | Complete; installed native package 0.2.0 qualified | Original native library, EXC/WS recovery, context/EXEC/CIF and service lifecycle, memory/error paths |
| v0.3 | Complete; installed artifacts and all three actual hosts qualified | Installed OpenBEXI extension and actual IntelliJ/PyCharm plugin ZIP, verifier and host Run/Debug/removal |
| v0.4 | Complete for the declared GENERIC simulator profile; see DRIVER_QUALIFICATION.json | Original driver RPC families through DSS, three operating modes, controller fencing and uncertain-effect recovery |
| v0.5 | Complete: 763 qualified, none open | All 763 inventory requirements independently qualified; source/manual conflicts resolved |
| v0.6 | Complete on the declared platform matrix; see V06_QUALIFICATION.json | Supported platform matrix, versioned upgrades, final installed host and DSS workflows |

The [v0.5 record](V05_CONFORMANCE_QUALIFICATION.json) binds all 61 native suites
(2,157 raw checks) to the qualified installed image and identical offline builds.
Final installed-host workflows and distribution gates pass in the
[v0.6 record](V06_QUALIFICATION.json). Historical records retain their original artifact scope.

## Native foundation

The authoritative Python 3 Makefiles define 143 library source units in 16
libraries. All 143 compile in the isolated Linux x86_64, GIL-enabled CPython
3.13.15 qualification environment. The original standalone executor links its
120 source units through one shared native runtime, so imported DTA and the
executor use the same singleton graph.

The current component and standalone evidence covers:

| Area | Evidence |
| --- | --- |
| UTIL/compiler/frame/error ownership | 22 behavior checks and three owned interpreter cycles |
| Original analyzer, bytecode, Step/Goto analysis and live variables | 58 checks |
| Frame manager and cold execution | 12 manager checks and eight execution checks |
| WS storage and frame graph | 17 storage checks and 13 frame/data checks |
| Original WS controller and logical continuation | 14 integrated checks plus 38 shared continuation probe checks |
| Native DTA | 18 runtime cases, 3,000 container lifetimes across three cycles |
| Native DTA checkpoints | 14 serialization cases and three integrated crash recoveries |
| Native executor bindings | 2,400 type lifetimes across three native-only interpreter cycles; 800 in one full-framework process |
| Actual standalone executor | 23 command checks, including ON_LINE and ON_STEP SIGKILL/fresh-process recovery |

Reports identify exact source, patch, recipe and artifact hashes. Historical
milestone reports describe their own source snapshots; their earlier compilation
counts are not the current build status. See [native port](NATIVE_PORT.md),
[bytecode analysis](BYTECODE_ANALYSIS.md), [frame manager](FRAME_MANAGER.md),
[DTA](DTA_RUNTIME.md), [cold execution](COLD_EXECUTION.md),
[WS controller](WS_CONTROLLER.md), [DTA checkpoints](DTA_CHECKPOINTS.md),
[executor command](EXECUTOR_COMMAND.md) and [executor recovery](EXECUTOR_RECOVERY.md).

Recovery preserves a logical caller graph and shared runtime data. It does not
reconstruct physical CPython caller frames. Checkpoints are trusted application
artifacts with exact interpreter/source identities. The full RPC framework uses
a fresh process for each interpreter lifetime; gRPC reinitialization in the same
process is explicitly rejected. Sanitizer qualification currently enables ASan
and UBSan; leak sanitizer is disabled.

The [context/server milestone](CONTEXT_SERVER.md) adds two passing original IPC
integration tests, normal server executor shutdown, twenty callback-driven
process restarts, fast child exit checks and four descriptor reuse cases.

The [service milestone](SERVICE_RUNTIME.md) adds nine checks of native
registration, metadata errors, worker results/errors and watchdog lifecycle, with
all owned threads joined before finalization. The real service executable also
runs native runtime data and a worker, receives Close, executes Python `finally`,
and exits normally. Together with the repeated context/server tests this passes
seven original IPC lifecycle runs. The CPython 3.13.15 upgrade is backed by
[isolated trace-unwind evidence](TRACE_UNWIND.md) and reruns of every preceding gate.

The [controller milestone](CONTROLLER_RUNTIME.md) adds five actual server
scenarios and missing-executor reconnect cancellation. Its 13 lifecycle runs
qualify breakpoints, variable inspection/editing, Step/Skip/Goto, rejected Goto,
pause/resume, abort cleanup, prompt response and retained Python errors.

The [service restart milestone](SERVICE_RESTART.md) passes Python-failure and
process-loss injection through the original watchdog. Both require a new verified
native executable, reaped previous child, worker result and normal context
shutdown. All 15 lifecycle runs pass; this is cold restart, not service checkpoint
resumption or live-service reconnection.

The [CIF milestone](CIF_RUNTIME.md) adds real blocking parent/child execution,
shared-data type/key/deletion checks and timed WaitFor. It fixes a child-launch
lock cycle and passes all 18 lifecycle runs with the preceding native gates.

The [ownership milestone](IPC_OWNERSHIP.md) qualifies failed-socket descriptor
accounting, atomic worker admission/drain, eight concurrent requests cancelled by
two disconnect callers and process listener unregistration. All preceding native
gates and 18 lifecycle runs pass. Native installation, reconnect semantics and
remaining ownership review still gate v0.2.

The [installed native package](NATIVE_PACKAGE.md), developer alpha 0.2.0a2,
passes five fresh-image installation checks, removal and all preceding native
gates. Two packages from the same native build are byte-identical. It includes
the real native runtime and corresponding sources; service reconnect/recovery
review and v0.2 acceptance remain open.

The [context ownership milestone](CONTEXT_OWNERSHIP.md) adds service-specific
login completion, pending-service ownership/watchdog fencing, monotonic status
waits and post-disconnect send checks. All preceding native gates and 19 lifecycle
runs pass. Live context reconnection and service checkpoint semantics remain open.

The [live reconnection milestone](LIVE_RECONNECT.md) now passes all nine context
tests and 21 lifecycle runs, plus every preceding native gate. Both a native
procedure and service survive context SIGKILL, pause without duplicate execution,
regain explicit GUI control, resume in the same process and close normally with
Python cleanup and child reaping. Key exchange is cancellable, reconnect channels
have an owned worker, and fractional native time arithmetic has eight checks.
The installed 0.2.0a2 wheel remains its earlier source snapshot.

The [service recovery policy](SERVICE_RECOVERY_SEMANTICS.md) resolves the incomplete
upstream native-service checkpoint path by rejecting recovery before startup and
preserving the requested file. Cold restart and live reconnection remain supported;
ordinary procedure checkpoint recovery is unchanged. The stricter IPC suite also
qualifies terminal close/pause races with three reconnect repetitions per process
kind. All preceding native gates, ten context tests and 25 lifecycle runs pass.

## Immediate work

Current checkpoint: [the v0.4 driver profile](DRIVER_RUNTIME.md) and
[its acceptance manifest](DRIVER_QUALIFICATION.json) supersede the historical
prerequisite status below. Continue with v0.5; do not repeat the completed
original RPC relay, immutable native release, binary/Kafka transport or authority
integration. Unsupported driver contracts remain explicit conformance work.

The [installed 0.2.0 artifact](NATIVE_PACKAGE.md) now passes seven fresh-image
checks, removal, byte-identical packaging from one qualified build and the full
native gate. The v0.2 foundation is accepted on Linux x86_64 / CPython 3.13.15.
The [host integration release](HOST_RUNTIME.md) now passes the native 0.3.0
package gate, ten native adapter cases, repeated output/stack stress, installed
CLI lifecycle checks and all three actual host Run/Debug/prompt/Stop/removal
workflows. Plugin Verifier accepts the tested PyCharm and IntelliJ builds.
[The host manifest](HOST_QUALIFICATION.json) binds the exact source, image, wheel,
ZIP and evidence identities. Continue with the neutral IDE durable service and
original DSS driver contracts for v0.4.
The isolated original example driver is a template fixture; operational
DSS driver support is a separate v0.4 requirement.

The subsequent [native shared Development prerequisite](SHARED_RUNTIME.md) adds
the optional `openbexi-spell-shared==0.4.0.dev1` provider. It uses the accepted
native 0.3.0 image unchanged, with captured source/runtime bindings, whole-container
pause, native prompts/results and durable restart holds. It does not close v0.4;
continue with original DSS driver contracts, operational effect receipts and
approved native Execution. Preserve the existing host acceptance artifacts.

Preserve explicit SPELL imports and the three operating modes: Execution,
Monitoring and Development. Native execution control, GUI control/monitor roles,
and those operating modes are distinct concepts.

Release tags are created only after their acceptance gates pass. Tested partial
milestones may be committed while the parent release remains open. No later
release is promoted based on compilation or import checks alone. Cleanup removes
only demonstrably obsolete project resources and preserves active test services.
