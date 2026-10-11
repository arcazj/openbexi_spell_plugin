# Original service watchdog restart

The native context watchdog passes two fault-injection scenarios against the
original `SPELL-Service_v3` executable. Both use the original service discovery,
registration, worker pool, context model and IPC stack.

| Fault | Required observation |
| --- | --- |
| Python exception | The first service raises ValueError, retains its error text and executes finally. The watchdog replaces it with a new native process. |
| Process loss | After verifying the child's live executable identity, the test sends SIGKILL to that owned child. The watchdog starts a new native process. |

Both replacements execute native ARGS/IVARS/PROC access and a worker returning
42 before declaring readiness. The old PID must be reaped, the replacement must
use a distinct PID, and closing the context must run the replacement's finally
block and reap it. The crash case deliberately does not require finally from the
killed process. There are exactly two starts per scenario.

This qualifies the original **cold restart** behavior. Context `checkService`
reopens an inactive service with fresh startup parameters. It does not restore a
service checkpoint or demonstrate reconnecting a still-running service after
context loss. Those distinctions remain explicit in the acceptance review.

[NATIVE_SERVICE_RESTART_QUALIFICATION.json](NATIVE_SERVICE_RESTART_QUALIFICATION.json)
records the passing source/artifact identities. Six unittest cases cover 15
context lifecycle runs, including the five controller scenarios, pending-reconnect
cancellation and normal service closure. All preceding component, standalone,
crash-recovery, process/socket and service binding gates also pass. The environment
is GIL-enabled CPython 3.13.15 / Linux x86_64, with ASan and UBSan enabled and leak
sanitizer disabled.

```powershell
docker build --progress=plain -f source_port/context-build.Dockerfile --output type=local,dest=.qualification/v0.2/service-restart-recheck .
../openbexi_ide/.venv/Scripts/python.exe source_port/record_native.py --evidence .qualification/v0.2/service-restart-recheck --service-restart
```

This milestone does not complete v0.2. Child/scheduler/shared-data CIF behavior,
service reconnect/checkpoint semantics and remaining ownership/error-path checks
still require acceptance review. Installed IDE hosts remain a later phase.
