# Original standalone executor on CPython 3.13

The original `SPELL-ExecutorCmd_v3` now links and runs with its original automatic
CIF, executor, controller, scheduler, dispatcher and example driver. The build
uses the 13 libraries selected by the upstream command Makefile: 120 original
translation units. It does not combine the separate context-process executor
class with the procedure executor.

The [qualification report](NATIVE_EXECUTOR_COMMAND_QUALIFICATION.json) records
17 passing command checks on Linux x86_64, CPython 3.13.14 with the GIL, GCC 14.2,
AddressSanitizer and UndefinedBehaviorSanitizer. LeakSanitizer is disabled.
All 143 upstream library units also pass the component compilation checks.

The command checks cover explicit imports, Unicode arguments in native
DataContainer instances, ordinary script paths, nested calls, Step/Goto, native
data notifications, automatic prompts, invalid binding arguments, syntax and
runtime failures, handled exceptions, Finish and Abort, and output visible before
process exit. Invalid prompt answers now fail with an explanatory error instead
of indexing outside the answer options. The example driver is the original
template with eight import corrections; it is not an operational DSS driver.

Procedures import SPELL explicitly:

```python
from spell.lang.functions import Display
from spell.runtime import Step, Goto, ARGS, PROC

Step('start', 'Start procedure')
Display('Running in the original executor')
```

The interpreter-local `spell.runtime` namespace holds the installed bindings;
SPELL no longer adds names to Python builtins. Native bindings are heap types
and resolve their serialized references to the current runtime. Three embedded
native-only interpreter cycles cover 2,400 binding type lifetimes. One complete
framework lifetime covers another 800. The RPC framework cannot be initialized
again after finalization in the same process; the helper rejects that operation
and requires a fresh executor process. Native-only helper cycles remain supported.

Shutdown stops and joins native workers, releases frame and binding ownership,
and finalizes the owned interpreter. Python streams are unbuffered for CLI
monitoring. Procedure failures return a nonzero exit code.

Reproduce from the repository root:

```powershell
docker build --progress=plain -f source_port/executor-build.Dockerfile --output type=local,dest=.qualification/v0.2/executor .
python source_port/record_native.py --evidence .qualification/v0.2/executor --executor-command
```

Within the built Linux environment the original command accepts:

```text
SPELL-ExecutorCmd_v3 -f procedure.py -c config/server/server.xml -n example
```

`-g` supplies the argument dictionary and `-a` supplies an automatic answer file.
The configuration is an original SPELL server/context/driver layout. The test
configuration uses empty local databases and no external control system.

This historical milestone did not complete v0.2. Later milestones qualify
[actual executor recovery](EXECUTOR_RECOVERY.md) and the
[context/service lifecycle](SERVICE_RUNTIME.md). Broader CIF/child/scheduler
control and external resource recovery remain separate gates. Finish/Abort tests assert termination and status; they do not
qualify all finally-block semantics. Compiled-away Step labels are not qualified
Goto targets. Operational DSS integration and IDE distributions belong to later
release gates.
