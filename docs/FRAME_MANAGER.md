# Original frame manager on CPython 3.13

The source port now links the original `SPELLframeManager`, `SPELLexecutionModel`,
breakpoint, execution-trace and resource-monitor classes with their real CIF,
configuration and procedure-library dependencies. Component tests call the public
manager methods; watch/resource notifications are disabled using their original
configuration flags. No executor or CIF implementation is substituted.

Live script execution uses `PyEval_EvalCode` with the frame's globals and CPython
3.13 locals proxy. Local and closure-cell assignments therefore reach the live
procedure. Database and definition propagation check errors and obey Python
reference ownership. The original `getMainDict()` name refers to `builtins` for
definition filtering; the test exercises that legacy contract explicitly.

Each execution model owns one frame reference. The manager's current-frame slot
borrows from its initial frame or model, so reload no longer decrements an alias
twice. Destruction releases models, definitions, initial frame and code without
recompiling the procedure. Warm-start ownership remains with the interpreter.

The two original WS filter methods are split into `native/ws_filter.cpp`, an
additional compatibility translation unit. Their key set belongs to the current
interpreter dictionary, preventing references from surviving interpreter
finalization. Configured names, modules, callables and SCDB/GDB/PROC are filtered.
Database names are compared as text rather than quoted object representations.
Failed filter replacement preserves the previous set.

[Qualification evidence](NATIVE_MANAGER_QUALIFICATION.json) covers twelve new
component checks: live locals/cells, shadowing, script-error recovery, temporary
object release, 1,000 model/frame lifetimes, repeated database propagation,
missing database and builtin fallback behavior, nested call/return restoration,
definition copying, filter categories and replacement ownership. Previous suites
remain at 21 UTIL, 57 analyzer/watch and 17 storage checks. Three embedded
interpreter cycles additionally verify that the WS filter starts empty each time.
ASan and UBSan are enabled; LeakSanitizer is disabled.

The original library inventory reaches 139/143 compilation/syntax passes. The
remaining four failures are WS dynamic data, static data, frame and controller
implementations. The manager's complete evaluation/recovery loop, original
dispatcher notifications, DTA runtime, context setup and shutdown still need
integration qualification. These component results do not complete v0.2.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-frame-manager-final .
python source_port/record_native.py --evidence .qualification/v0.2/native-frame-manager-final --manager
```
