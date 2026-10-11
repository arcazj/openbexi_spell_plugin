# Execution through v0.6

Authorized target: finish and commit each release in order through plugin v0.6,
including prerequisite changes and qualification in the sibling openbexi_ide.
The working IDE v0.2 / bounded plugin v0.1 remains the testing baseline while the
original-source runtime is developed in isolated environments.

| Release | State | Required evidence |
| --- | --- | --- |
| v0.2 | In progress; source alpha 0.2.0a1 complete | Original native library, EXC/WS recovery, context/EXEC/CIF and service lifecycle, memory/error paths |
| v0.3 | Pending v0.2 | Installed OpenBEXI extension and actual IntelliJ/PyCharm plugin ZIP, verifier and host Run/Debug/removal |
| v0.4 | Pending v0.3 and IDE service prerequisites | Original driver RPC families through DSS, three operating modes, controller fencing and uncertain-effect recovery |
| v0.5 | Pending v0.4 | All 763 inventory requirements independently qualified; source/manual conflicts resolved |
| v0.6 | Pending v0.5 | Reproducible distribution, supported platform matrix, clean installation/removal and upgrades, actual host and DSS-container workflows |

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
| Native DTA checkpoints | 13 serialization cases and three integrated crash recoveries |
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

## Immediate work

Review service reconnect/checkpoint semantics and complete the remaining native
ownership/error-path checks. Then
complete the v0.2 acceptance review before installing the new runtime into IDE
hosts. The isolated original example driver is a template fixture; operational
DSS driver support is a separate v0.4 requirement.

Preserve explicit SPELL imports and the three operating modes: Execution,
Monitoring and Development. Native execution control, GUI control/monitor roles,
and those operating modes are distinct concepts.

Release tags are created only after their acceptance gates pass. Tested partial
milestones may be committed while the parent release remains open. No later
release is promoted based on compilation or import checks alone. Cleanup removes
only demonstrably obsolete project resources and preserves active test services.
