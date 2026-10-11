# Original variable monitor on CPython 3.13

SPELLvariableMonitor now uses public PyFrame_GetGlobals/PyFrame_GetLocals APIs.
CPython 3.13's optimized-locals proxy updates running function locals and closure
cells directly; the removed fast-locals synchronization is not emulated. The
original listener, variable-information structures and monitor interface remain.

Global and local scopes remain separate even when a local shadows a global.
Unqualified lookup resolves the local first. A module frame does not duplicate
the same namespace as both globals and locals. The monitor reports additions,
value/type changes, deletions and values that become filtered from display.
Unchanged values produce no notification.

Edits evaluate the exact expression in the frame's namespace. The port removes
the legacy replacement of double quotes with single quotes, which could corrupt
valid strings. Empty-input/`<empty>` assignment still means an empty string;
display uses consistent Python repr. Invalid names/expressions fail without
performing the assignment. Authorization remains the executor/controller's job,
not this internal monitor class.

Namespace entries are snapshotted before formatting, because repr may run user
code and mutate the live mapping. A failing repr displays `<unprintable>` and
does not leave a pending Python error. Owned snapshots and temporary type/value
references are released. The existing global-reference accessor keeps its
borrowed-reference contract. The monitor still borrows its frame/listener from
the execution model; the qualification adapter explicitly closes its owned frame
handle to avoid a capsule/frame reference cycle.

Internal database names, configured ignored variables, private names, callables
and modules retain their exclusions. Ordinary watches do not import the driver
framework. If the actual original Database class is already loaded, its instances
remain excluded. Integration of that loaded class with the complete native
runtime is still part of the remaining framework qualification.

Seventeen added sanitizer-backed tests pass: live locals, write-through edits,
closure cells, shadowing, notification types, filtering, Unicode/quotes/empty
values, failed-expression recovery, failing/mutating repr, module namespaces,
2,000 global-reference lookups, 200 frame/value lifetime cycles, and no implicit
framework imports. The combined analyzer suite has 43 tests; UTIL's 16 tests,
WS storage's 17 tests and three embedded-interpreter cycles also pass.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-watch-final .
python source_port/record_native.py --evidence .qualification/v0.2/native-watch-final --watch
```

See [the input-bound evidence](NATIVE_WATCH_QUALIFICATION.json). These are Linux
x86_64 CPython 3.13 native checks, not acceptance of the complete SPELL executor
or host debugger. Full v0.2 remains open. Public API reference:
[CPython frame objects](https://docs.python.org/3.13/c-api/frame.html).
