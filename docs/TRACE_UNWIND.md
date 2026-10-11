# CPython trace exception cleanup

The original service Close integration exposed skipped Python `finally` cleanup.
A standalone probe, with no SPELL code linked, reproduces the same behavior on
our pinned Linux CPython 3.13.14 image. Both a C trace callback and a Python
`sys.settrace` callback raise inside a `try` loop. Neither cleanup runs on that
image (0/2, process exit 1); both run on the pinned CPython 3.13.15 image (2/2,
process exit 0). This is evidence for these builds and this regression, not a
claim about every tracing pattern or an identified upstream issue number.

[Source and result hashes](TRACE_UNWIND_QUALIFICATION.json) identify both probes.
The native port now pins Linux CPython 3.13.15. Its private continuation engine
also requires exactly 3.13.15; recovery artifacts retain exact interpreter and
source identities, and old checkpoints are not silently accepted. Historical
3.13.14 component reports remain evidence for their original source snapshots.
The official [3.13.15 release page](https://www.python.org/downloads/release/python-31315/)
identifies the interpreter release.

The native trace bridge disables its callback after a dispatch failure and
preserves the pending Python exception while the evaluator unwinds. This prevents
additional dispatch failures from interrupting cleanup. User cleanup still has
to return; this does not promise bounded cancellation of arbitrary Python or
native extension code.

## Reproduce

```powershell
docker build --progress=plain -f source_port/trace-unwind.Dockerfile --output type=local,dest=.qualification/v0.2/trace-current .
Get-Content .qualification/v0.2/trace-current/trace-exit.txt
Get-Content .qualification/v0.2/trace-current/trace-result.txt
```

The Docker build exports diagnostic evidence even if the probe fails. Acceptance
requires `trace-exit.txt` to contain `0` and `TRACE_UNWIND_CHECKS 2/2` in the log.
To reproduce the failing control, add
`--build-arg PYTHON_BASE=python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280`
and use a separate output directory. Its expected diagnostic exit is 1.
