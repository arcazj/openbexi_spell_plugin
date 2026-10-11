# Native server controller qualification

The original listener, context, server executor and CIF now pass five independent
controller scenarios over the original IPC protocol. This is a v0.2 milestone;
it does not complete the release or establish full SPELL conformance.

| Scenario | Observed behavior |
| --- | --- |
| Execution controls | Breakpoint stops before assignment; explicit variable snapshot reads 21, editing changes it to 40, Step computes 41, Skip bypasses an assignment, and Goto bypasses a guarded failure; final output is 42 |
| Rejected Goto | An invalid line produces the original warning and stays paused; a subsequent valid jump succeeds |
| Pause/resume | The procedure's counter stays fixed across two paused snapshots; changing its stop flag and resuming completes the procedure |
| Abort | A running procedure pauses, receives Abort, reports ABORTED, and executes its Python finally block |
| Prompt | The original Prompt enters PROMPT, exposes the expected question, accepts the original answer-index message, and completes |
| Python failure | The original exception reason is retained and finally executes before closure |

The controls scenario includes configuration inspection and breakpoint removal.
Every procedure closes and the context exits normally without timeout-driven kill
fallback. An additional lifecycle starts with a persisted missing executor and
closes successfully while its reconnect worker is still pending.

## Port changes

CPython permits frame line changes only on the active tracing thread. Original
Skip and Goto command handlers now run there when execution is paused. The
controller mailbox remains serialized, and the original handlers retain command
validation, warnings and status transitions. Rejected jumps keep waiting; they
do not execute the paused statement. Pause publishes its status only after its
wakeup state is ready, preventing a fast resume notification from being cleared.
No private bytecode-stack mutation is used for these commands.

An explicit CIF variable request now refreshes its snapshot even when automatic
watching is disabled. This does not enable automatic watching or emit its update
notifications. A separate native test checks the disabled-watch snapshot.

Reconnect workers have cancellation and are joined by their owner during
shutdown. Failed reconnect models are retired for owner-thread cleanup instead
of deleting the worker from its own callback. The executor persistency table
remains alive until active executors have been removed.

## Evidence and scope

[NATIVE_CONTROLLER_QUALIFICATION.json](NATIVE_CONTROLLER_QUALIFICATION.json)
records source, patch, recipe and artifact hashes for the passing build. It
contains five unittest cases covering 13 context lifecycle runs, all five server
controller scenarios, nine service binding checks, 23 standalone executor checks,
and the preceding native/component/recovery gates. The analyzer/watch suite now
has 58 passing checks. CPython is pinned to 3.13.15 on Linux x86_64 with the GIL;
ASan and UBSan are enabled, while leak sanitizer is disabled.

The reconnect test covers cancellation during shutdown, not the original
120-second expiration path. Child procedures, scheduler/shared-data CIF paths,
service failure/restart/recovery and the remaining ownership/error-path review
still gate the release. This report is not an installed IDE-host qualification.

```powershell
docker build --progress=plain -f source_port/context-build.Dockerfile --output type=local,dest=.qualification/v0.2/controller-recheck .
../openbexi_ide/.venv/Scripts/python.exe source_port/record_native.py --evidence .qualification/v0.2/controller-recheck --controller
```

The recorder rejects failed behavior gates or mismatched source/artifact hashes.
A successful Docker export by itself does not establish runtime acceptance.
