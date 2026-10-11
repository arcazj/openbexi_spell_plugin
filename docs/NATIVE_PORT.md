# CPython 3.13 native port

The first native milestone ports the original UTIL compiler, frame diagnostics,
line setter and error ownership. It is a tested part of the open v0.2 release,
not a complete native executor. The separate source alpha wheel and its
`source-v0.2.0a1` evidence remain historical artifacts.

All eight original UTIL and nine SYN translation units compile and link into an
actual Python extension with no undefined symbols. Six upstream files have
SHA-256-checked patches; the archive remains unchanged. An added ownership header
and replacement function bodies form the complete, reviewable patch material.
Original licenses and notices remain in the extracted sources.

The compiler uses Py_CompileStringExFlags. Frame reads use public accessors, and
line jumps use CPython's f_lineno setter, including its restrictions on trace
events and invalid exception-block jumps. The test exercises both a Python trace
and an actual C trace callback. This does not yet qualify SPELL Step/Goto's
full executor integration or recovery of suspended execution stacks.

Python exceptions are normalized, translated using the original error codes,
and released with their tracebacks. Every monitor exit balances GIL ownership.
Original controller abort/terminate state distinguishes control signals from a
user exception with the same text. New-instance results and imported modules
have explicit reference ownership. The logger no longer creates Python strings
at shared-library/process startup, before Py_Initialize.

The helper preserves an existing host interpreter, sys.path, argv and builtins.
An embedded interpreter uses isolated configuration, and only its owning thread
may finalize it. Framework loading imports installed modules without injecting
SPELL symbols into builtins. Executor/context configuration remains a later gate.

Qualification uses Linux x86_64 / CPython 3.13.14 / GCC 14.2.0 with AddressSanitizer
and UndefinedBehaviorSanitizer. Sixteen runtime tests pass, including 2,000
exception-payload lifetime checks, 2,000 native instance lifetime checks and 200
native-thread error transitions. A separate executable passes three owned
interpreter initialize/execute/error/finalize cycles and rejects finalization
from another thread. LeakSanitizer is disabled; targeted reference-lifetime
checks do not establish absence of every native leak.

The subsequent analyzer milestone replaces the removed parser tree with the
public `tokenize` API and the obsolete line table with `code.co_lines()`. The
original SPELLastAnalyzer and SPELLlnotab classes link against the same UTIL/SYN
objects. Fifteen additional sanitizer-backed tests cover nested continuations,
strings and f-strings, blank/comment lines, edited files, invalid-source recovery,
backward line changes, exception handlers, large offsets and reference ownership.
Actual Python trace events are checked against the resulting line table.

Blank/comment lines inside brackets now remain part of the continuation; source
edits at an existing filename are reparsed. A failed parse clears the old current
classification. Artificial line zero is not an executable source line, and an
empty line table returns -1 instead of dereferencing an empty list. These fixes
are deliberate corrections to the legacy analyzer, not additional SPELL syntax.

The static Step/Goto analyzer now uses `dis.get_instructions`, resolving modern
CALL instructions, LOAD_GLOBAL operands, inline caches and extended arguments.
Eleven more tests cover literal labels in module/function scopes, INIT, multiline
calls, Unicode, missing targets, duplicate-target compatibility and reference
ownership. Forward/backward C trace jumps use the original analyzer's target map;
CPython rejects entering an exception handler. The Step callable in these three
trace fixtures only records calls: native Step/Goto bindings and full executor
integration remain unqualified. Dynamic arguments and aliases are not invented
as static labels. A missing static target returns -1 instead of dereferencing an
invalid map iterator. Runtime resolution still belongs to the original executor.

The remaining native syntax probe is:

| Component | Compile | Fail | Qualification |
| --- | ---: | ---: | --- |
| UTIL | 8 | 0 | Linked; the behavior scope above is tested |
| DTA | 5 | 0 | Syntax only; no container runtime acceptance yet |
| EXC | 25 | 6 | Four analyzers and variable monitor linked/tested; other units syntax only |
| WS | 12 | 7 | Storage linked/tested; remaining passing units syntax only |

The total is 50 of 63 units compiling, versus 26 in the unchanged-source probe.
Failures still include
opaque frame fields, Python 2 class/instance representations and PyTryBlock.
The native build reports those failures rather than substituting fake structures.

The [WS storage milestone](WS_STORAGE.md) additionally links the original
SPELLwsStorage class and qualifies bounded versioned persistence with 17 checks.
Its format deliberately rejects old/interpreter-incompatible frames. The seven
remaining WS compile failures and full executor recovery are still open.

The [live variable monitor](VARIABLE_MONITOR.md) adds 17 checks for public frame
locals, closure-cell edits, shadowing, notifications and reference ownership.
Together the native suites now have 16 UTIL, 43 analyzer/watch and 17 storage
tests, plus three standalone interpreter lifecycle cycles.

The [bytecode analyzer port](BYTECODE_ANALYSIS.md) adds 14 source/disassembly
checks and raises the analyzer/watch total to 57. The compiler binds source to
code identity with weak ownership; interpreter reinitialization still passes.

The [executor frame port](EXECUTOR_FRAME_PORT.md) adds public frame getters and
two utility checks (18 total). Its corrected inventory follows all 16 original
Python 3 library Makefiles: 135 of 143 units pass compilation/syntax checks.
Eight frame-manager/warm-start units remain open. The historical subset counts
above are preserved as evidence of their original scope.

Build and export into a new evidence directory:

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-goto-01 .
python source_port/record_native.py --evidence .qualification/v0.2/native-goto-01 --goto
```

The Docker build exports diagnostics even after a native compile/test failure;
its exit status alone is not acceptance. `record_native.py` requires successful
UTIL compile/link/runtime/embedding results and binds every copied build input
to the checked-in source. The `--goto` gate also requires all 26 analyzer checks.
See the [Step/Goto analysis evidence](NATIVE_GOTO_QUALIFICATION.json),
the earlier [source/line analyzer evidence](NATIVE_ANALYSIS_QUALIFICATION.json)
and the earlier [UTIL evidence](NATIVE_UTIL_QUALIFICATION.json).
The base image is digest-pinned; Debian tool packages are recorded but are not
yet a reproducible production toolchain. The normal DSS container startup issue
is separate from these successful BuildKit RUN executions.

API references: [frame objects](https://docs.python.org/3.13/c-api/frame.html),
[compilation](https://docs.python.org/3.13/c-api/veryhigh.html) and
[interpreter ownership](https://docs.python.org/3.13/c-api/init.html),
[tokenization](https://docs.python.org/3.13/library/tokenize.html) and
[disassembly and line tables](https://docs.python.org/3.13/library/dis.html).
