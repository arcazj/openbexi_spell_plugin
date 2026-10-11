# Recovery through the original executor

The [executor warm qualification](NATIVE_EXECUTOR_WARM_QUALIFICATION.json) extends
the original standalone command checks to 23 cases. Real procedures are killed
with SIGKILL after a checkpoint and resumed in fresh executor processes. Both
ON_LINE and ON_STEP recover nested return expressions, native data constraints,
and shared ARGS, IVARS and PROC references without rerunning module setup.

The native Step binding requests a checkpoint at the next safe line event,
after Step returns and before that line executes. Capturing the caller while
inside the C binding is invalid on this CPython version because its value-stack
pointer is unavailable. ON_LINE continues to save at supported line boundaries.

The exact-build continuation format is now `SPELL-continuation/2`. It serializes
the runtime-owned ARGS, IVARS, PROC, SCDB and GDB values in the same object graph
as the saved callers. After validating the graph, recovery installs those objects
in the new `spell.runtime` namespace. Procedure aliases therefore refer to the
same objects used by the active bindings. It does not serialize the complete
driver registry or reconnect arbitrary external resources.

Native DataContainer and Var types identify their owning `libSPELL_DTA_v3` module.
Serialization no longer depends on whether the optional Python adapter alias was
imported first. The DTA checkpoint suite now includes thirteen independent cases.

`-r` enables warm recovery without requiring a separate `-w`. Recovery still uses
the original paired ASRUN file. Missing recovery files, changed source and damaged
checkpoint payloads fail with a nonzero status. A recovering process writes to a
distinct checkpoint name, preserving its input checkpoint on success and failure.
Cleanup acquires the GIL before releasing Python-owned state. Startup failures in
CIF construction, configuration and procedure loading are caught by the command.

Reproduce on the pinned Linux build:

```powershell
docker build --progress=plain -f source_port/executor-build.Dockerfile --output type=local,dest=.qualification/v0.2/executor-recovery .
python source_port/record_native.py --evidence .qualification/v0.2/executor-recovery --executor-warm
```

The component and continuation suites are required by the recorder as well as the
command tests. Qualification remains Linux x86_64, GIL-enabled CPython 3.13.14,
with ASan/UBSan and without LeakSanitizer. Caller recovery is logical continuation;
it does not reconstruct physical Python `f_back` links. Application-owned
checkpoints are trusted input, not an untrusted interchange format.

v0.2 remains open for native context/service lifecycle and complete controller,
CIF, child-procedure and scheduler behavior. Broader executor recovery scenarios,
external effects and installed host/platform workflows remain explicit gates.

During this milestone, targeted Docker cleanup removed 32 obsolete project cache
records. Docker's reported build-cache usage fell from 12.648 GB to 5.484 GB,
reclaiming approximately 7.165 GB. Remaining referenced cache records, the DSS
image, unrelated images/containers and volumes were preserved. This is logical
Docker storage reclamation, not a claim that its host disk image was compacted.
