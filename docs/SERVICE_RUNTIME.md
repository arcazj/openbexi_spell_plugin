# Native service qualification

The original 2.6.10 service design is retained: `SpellService` discovers and
registers a Python service with the native procedure manager, the context owns a
watchdog, and the service executable runs its implementation. This document
records the binding checks and the first real service-process lifecycle.

The current passing source snapshot is recorded in
[NATIVE_SERVICE_QUALIFICATION.json](NATIVE_SERVICE_QUALIFICATION.json). The earlier
[binding-only report](NATIVE_SERVICE_BINDINGS_QUALIFICATION.json) remains historical
evidence for its own commit.

## Registration and owned workers

The source-derived helper calls `spell.runtime._register_service` explicitly.
The private name prevents framework wildcard imports from replacing the native
callable with its public Python wrapper. No builtins are injected. A runtime
without the native registration callable reports services unsupported; attempting
registration raises an error instead of silently returning false.

Native registration evaluates each metadata method once, validates nonempty text
and rejects embedded NULs, preserves Python exceptions,
translates C++ failures, and rejects duplicate names. The original native service
model owns the Python wrapper. The constructor filename works for both a class
function and an instance method under Python 3.13. Registration happens after
successful construction, and failed construction/registration stops owned workers.

The watchdog callable owns its native callback through a capsule. Replacing a
watchdog cancels and joins its previous thread. Service cleanup joins repeating
workers, closes the standard-library thread pool, and rejects further submissions.
Native manager cleanup releases service models before interpreter finalization.
The complete RPC framework continues to require a fresh interpreter process.

The nine binding checks exercise explicit registration, invalid arguments,
invalid metadata, single metadata evaluation and error preservation, duplicate
names, worker results and exceptions, repeating
workers, watchdog argument/error boundaries, and watchdog replacement. Additional
postconditions require unchanged builtins and no remaining owned Python threads.
Tests use the real native manager and native watchdog callback with ASan/UBSan;
leak sanitizer remains disabled.

Shutdown qualification also exposed original IPC/process defects. Incoming
request/message completion is now signaled on exceptional and early-return paths,
so a failed reply cannot strand the cleanup queue. Erasing a completed processor
does not increment an invalidated iterator; the cleaner shutdown flag is guarded
by its mutex. Listener termination is consumed by `sigwait` on the owner thread
instead of running logging and joins from an asynchronous signal handler. Child
processes explicitly unblock their termination signals before `exec`; `waitpid`
retries `EINTR` without falsely reporting child death. Failed child `exec` uses
async-signal-safe reporting and `_exit`. Server shutdown joins the accept/cleanup
thread before removing its remaining clients. Client cleanup detaches the channel
under the client lock, leaves a stable null map entry for pending processors, and
deletes the channel outside that lock. Pending removals use a locked snapshot,
so connection callbacks cannot invalidate the removal loop.

Regression evidence includes four request/message completion cases, four child
signal-mask checks, an interrupted monitor wait, and the existing twenty restart
and four descriptor-reuse cases. Both original listener/context scenarios repeat
three times; each real server executor must exit normally without force-kill
fallback. These checks cover observed shutdown failures, not a complete IPC
concurrency audit.

## Real service process

The original context watchdog discovers the service and launches
`SPELL-Service_v3`. The peer checks the live process executable through `/proc`,
then verifies native `ARGS`, `IVARS` and `PROC`, explicit imports, and a worker
result of 42. Closing the context stops its watchdogs first, sends the original
Close command, executes the service's Python `finally` block, joins owned workers,
and reaps the child without force-kill fallback. Six existing context/server
lifecycles also pass in the same build (seven lifecycle runs total).

CIF startup now explicitly distinguishes service identities from procedure
instances. It preserves the original service name instead of appending `#0`, so
control and logout messages address the same identity as the context. Service
ASRUN output records `# SERVICE: <name>` rather than looking up an ordinary
procedure model that does not exist. Controller completion publishes FINISHED
after Close so a normal child exit is not reported as a startup failure.
Request admission uses scoped mutex ownership; Close no longer locks a mutex on
one worker and unlocks it on another thread during cleanup.

This lifecycle also exposed a CPython trace-unwind regression in the previously
pinned 3.13.14 build. A standalone probe reproduces skipped cleanup without SPELL;
the same checks pass on 3.13.15. The native build and exact-version continuation
engine now pin 3.13.15. All preceding component, standalone and crash-recovery
checks pass again. See [trace-unwind evidence](TRACE_UNWIND.md).

Broader controller/CIF tests, service failure/restart/recovery and remaining
native ownership/error-path checks still gate v0.2. This successful service
lifecycle does not establish full service conformance.

## Reproduce

```powershell
docker build --progress=plain -f source_port/context-build.Dockerfile --output type=local,dest=.qualification/v0.2/service-recheck .
../openbexi_ide/.venv/Scripts/python.exe source_port/record_native.py --evidence .qualification/v0.2/service-recheck --service
```

The recorder requires the existing component, standalone, warm-recovery and
context/server gates, validates source and artifact hashes, and exports a separate
`NATIVE_SERVICE_QUALIFICATION.json` milestone. Build success alone is not
runtime acceptance.

## Project maintenance

After the context/server milestone, reviewed obsolete project build-cache records
were pruned by exact ID. Docker's logical cache inventory decreased by
10,304,141,718 bytes across 34 removed records. The current DSS image, unrelated
images, containers and volumes were preserved. This is cache accounting, not a
claim that Docker's Windows virtual disk was physically compacted.
