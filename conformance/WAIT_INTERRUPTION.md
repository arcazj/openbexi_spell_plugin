# Native wait interruption

The original runtime passed 23 of 24 interruption controls, then acquired another
telemetry sample after reporting `INTERRUPTED` in `telemetry:skip:recovery`.
The retained run is `a19c1d156eb84a1389587e7f8bf9a5a6` in the wait-controls
worktree. The late acquisition began more than 500 ms after the first interrupted
status response; the condition was still interrupted throughout.

`SPELLtimer::stop()` pauses its loop after the current callback. A callback
already pending when INTERRUPT arrives can therefore still enter the scheduler.
The original scheduler callback did not check the interrupted status. It also
released its check mutex before emitting interval messages and completing a
condition, and could reach that notification path after a failed lock attempt.

The checked correction changes only `SPELLscheduler.C`, preserving its class
layout and target time. A callback tries the existing check mutex, returns
quietly if it cannot acquire it or finds `INTERRUPTED`, and retains that mutex
through condition checks, interval notifications and completion. An owning guard
releases the lock if a Python operation raises. The callback does not block on
the mutex because timer replacement may join it while holding that mutex.

The controlled probe compiles the exact original and corrected callback bodies.
For time, expression, child and telemetry conditions, the original callback
performs four checks and emits four messages while interrupted; the correction
performs neither. Active checks, completion and abort still work. Exception and
lock-contention controls also pass with the correction. This probe establishes
control flow and does not substitute for native IPC execution.

The diagnostic library passes all 24 native controls across relative time,
absolute time, telemetry, STEP and SKIP, with independent positive, boundary,
failure and recovery cases. The strict retained-evidence verifier and nine
focused source/report tests pass. See the [diagnostic report](evidence/wait_interrupt.json)
and [build record](../distribution/evidence/wait-interrupt-diagnostic-build.json).

These results qualify no release row by themselves. The eight candidate wait
requirements need the correction in fresh composed packages and the complete
regression sequence before promotion. Full v0.5 still requires all 763 rows.
