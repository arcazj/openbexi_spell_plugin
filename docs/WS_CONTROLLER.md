# Original warm-start controller and frame manager

The original `SPELLwsWarmStartImpl` and `SPELLframeManager` now save and resume
logical caller continuations on GIL-enabled CPython 3.13.14. All 143 original
Python 3 library translation units pass compilation/syntax checks. This closes
the outstanding WS compile failures, not the complete v0.2 runtime release gate.

The WS controller retains the original call/line/stage notifications and working
modes. One return removes one nested frame; reset releases every frame, including
the root. Each checkpoint serializes the entire caller graph together through
the existing atomic codec and original WS storage, preserving shared globals,
values and closure cells. Ordinary class bodies and C callbacks may execute;
publishing a continuation across an active C-call boundary fails explicitly.

Recovery validates every frame before replacing the current graph. The frame
manager builds its inspection models from the logical stack, not `f_back`.
When CPython creates a resumed live frame, the saved model and WS frame rebind to
it before line dispatch. Nested return values flow back into saved caller
expressions. Exceptions enter the saved caller's handler or remove an unhandled
logical caller, preserving the tested finally/context-manager behavior.

Pending caller snapshots remain available while the deepest frame runs. A new
checkpoint can therefore combine the resumed live frames and the remaining
logical callers. In-memory error recovery uses the last recorded line state;
it retains shared mutable objects and does not roll back external effects.
Disk recovery uses the serialized graph committed before process termination.

Procedure initialization now accepts an explicit namespace, retaining the
legacy default when none is supplied. The namespace receives builtins and the
procedure filename, while keeping host objects out of the procedure's globals.
The original multiline parser explicitly selects the running Python grammar;
zero-initialized AST compiler flags had incorrectly rejected positional-only
parameters and exception groups. See CPython's
[compiler flag contract](https://docs.python.org/3.13/c-api/veryhigh.html#c.PyCompilerFlags.cf_feature_version).

[Qualification evidence](NATIVE_WARM_QUALIFICATION.json) records fourteen
controller/manager checks, including SIGKILL followed by a fresh process:

- Nested return expressions, recursive operand stacks and argument kinds.
- Closure sharing and distinct handled exceptions in child and caller.
- Handler/finally propagation, skipped callers, context managers and exception groups.
- Recheckpointing a resumed child and a resumed caller with a new nested call.
- Rejection of C-boundary checkpoints, working modes, reset/cleanup and error recovery.

The earlier native suites also pass: 21 UTIL, 57 analysis/watch, 12 manager,
8 cold-execution, 13 WS frame/data, 17 storage and 18 DTA cases, plus both
three-cycle embedding suites. The shared continuation engine retains its
14 in-memory, 13 persistent and 11 caller experiment checks. ASan/UBSan are
enabled; LeakSanitizer is disabled. Closure-cell shape validation follows the
exact-build [CPython slot layout](https://github.com/python/cpython/blob/v3.13.14/Include/internal/pycore_code.h).

The dispatcher in these integration checks is still the qualification adapter
calling original manager callbacks. The complete original executor, real CIF,
Step-stage dispatch, native DTA checkpoint graph, external resources/dependencies,
DSS effects and Windows remain unqualified. Physical Python caller frames are
not reconstructed. No v0.2 release or later release is promoted by this milestone.

```powershell
docker build --progress=plain -f source_port/experiments/persistent-probe.Dockerfile --output type=local,dest=.qualification/v0.2/native-warm-03 .
python source_port/record_native.py --evidence .qualification/v0.2/native-warm-03 --warm
```
