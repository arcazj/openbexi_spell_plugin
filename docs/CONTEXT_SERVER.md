# Original context and server executor

This v0.2 milestone qualifies the original listener/context IPC lifecycle and a
context-launched native server executor. **v0.2 remains open** for the native
service lifecycle and broader controller/CIF behavior. The installed bounded
plugin v0.1 and neutral IDE v0.2 remain the working user baseline.

The [qualification report](NATIVE_CONTEXT_QUALIFICATION.json) records the exact
archive, patches, recipes, binaries and logs from `native-context-12`. All
preceding component checks and the 23 standalone executor cases pass in the same
build. Qualification uses Linux x86_64, GIL-enabled CPython 3.13.14, ASan and UBSan;
leak sanitizer is disabled.

## What runs

The builder reads the original program Makefiles and links `SPELL-Listener`,
`SPELL-Context`, `SPELL-Executor_v3` and `SPELL-Service_v3`. Listener/context keep
their original separate class graph. Server/service share the executor runtime
with imported native DTA, preventing duplicate executor singletons. Service
compilation is recorded; service runtime qualification is still pending.

Two integration tests pass through the original IPC serializer and interfaces:

1. The listener launches the context, exposes its client port and status, then
   closes the context through IPC. The context and listener exit normally.
2. A client logs into the context and opens an indexed Python 3 procedure. The
   procedure explicitly imports SPELL, reads native `ARGS`, waits for the visible
   Run command, sends CIF notifications and writes the independently checked
   result `42`. The client closes the executor and context. Native logs must show
   a completed executor main loop and a successful child exit; force-kill
   fallbacks fail the test.

The fixture uses the original example driver with its eight recorded import
corrections and local databases. The example driver reports unsupported event
injection at startup. It is a template used to exercise native execution, not an
operational DSS driver or evidence for the three operating modes.

Process/socket regression checks also pass: exit statuses 0 and 7, twenty
callback-driven process replacements while another thread waits, duplicate
identifier rejection, and four close/shutdown cases that reuse the freed file
descriptor and verify later cleanup cannot close its replacement.

## Corrections to the original code

- Arm the context finish event before publishing readiness; clean up its driver
  under the GIL and let the interpreter owner restore its saved thread state
  during finalization.
- Retain process monitors across callbacks and concurrent waits, publish them
  before starting their threads, reap each child once, and compare listener
  iterators with the correct map. Intentional shutdown suppresses automatic
  context respawn, including a second check after the respawn delay.
- Give the IPC channel sole ownership of its socket. Client destruction also
  cleans up a lost connection. Descriptor close/shutdown is idempotent, including
  socket destruction, and readiness uses atomic state where introduced.
- Catch server startup errors, return the real execution exit code, honor the
  time identifier option and explicitly shut down the interpreter/CIF.
- Release the GIL while joining CIF workers. Cancel notification retry loops
  when closing starts: a detached client cannot acknowledge a final status.
  Cancellation does not report a fabricated acknowledgment.

These are SHA-checked edits of the supplied source. Original notices and the
source archive remain intact.

## Reproduce

From the plugin repository in PowerShell:

```powershell
docker build --progress=plain -f source_port/context-build.Dockerfile --output type=local,dest=.qualification/v0.2/context-recheck .
../openbexi_ide/.venv/Scripts/python.exe source_port/record_native.py --evidence .qualification/v0.2/context-recheck --context
```

The build exports diagnostics even when a test fails. The recorder rejects failed
checks, changed source/recipe hashes, altered binaries and incomplete evidence.
Only run it when deliberately replacing this milestone's evidence. Historical
executor/WS reports remain separate snapshots.

Next: qualify the original service lifecycle, interactive and failure controls,
shared data, child procedures and scheduler behavior before the v0.2 release
review. Installed IDE host qualification follows v0.2.
