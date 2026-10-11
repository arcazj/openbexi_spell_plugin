# Original manager cold execution

The original frame manager now executes freshly compiled procedures with
`PyEval_EvalCode`. CPython allocates the live frames; inspection frames created
by `PyFrame_New` are never passed to the interpreter evaluator. Module locals
and globals share the procedure namespace, including nested function lookups.

The manager retains the original execution result and error flags. Abort and
terminate setters preserve their Python exception until evaluation unwinds,
so procedure `finally` blocks execute and the original result distinguishes
abort, error and termination. Failed reloads clear stale frame access. Scripts
can initialize the procedure namespace before its first execution.

[Evidence](NATIVE_COLD_QUALIFICATION.json) records eight additional checks under
ASan/UBSan: nested calls, handled and unhandled exceptions, control exceptions,
live local edits, pre-execution scripts, failed reloads, 300 reloads with code
weak references, and restoration of a previously installed trace. The earlier
21 UTIL, 57 analysis/watch, 12 manager, 17 storage and 18 DTA checks pass, as do
both three-cycle embedding suites. LeakSanitizer remains disabled.

The qualification dispatcher calls the original manager's public frame callbacks.
It is not the complete original executor dispatcher. Warm recovery is explicitly
rejected until the continuation adapter is integrated. Real executor, CIF, driver
and context lifecycle qualification still gate v0.2; no later release is promoted.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-cold-02 .
python source_port/record_native.py --evidence .qualification/v0.2/native-cold-02 --cold
```
