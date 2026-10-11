# CPython 3.13 recovery compatibility investigation

The subsequent [persistent recovery experiment](PERSISTENT_RECOVERY.md) now
qualifies thirteen single-frame persistence checks through the original WS
storage, including SIGKILL and a fresh interpreter. The six-check milestone below
describes the earlier in-memory investigation; full executor recovery remains open.

The original SPELL warm-start implementation stores/restores frame instruction
offsets, local/operand stacks, Python 2 try blocks and caller links. CPython 3.13
removed that representation. Public frame accessors and the validated f_lineno
setter are sufficient for ordinary tracing and user-directed jumps, but cannot
restore an arbitrary saved operand stack. Replacing these structures with empty
compatibility objects would falsely claim working recovery.

The next candidate is a small, version-pinned compatibility backend inside the
isolated SPELL runtime. Ordinary IDE Python execution and host plugins continue
to use public interfaces. A host plugin must not load this private ABI into an
arbitrary user interpreter. The experimental backend accepts only GIL-enabled
CPython 3.13.14, checks the version at compile/import time, and is not packaged
in either released wheel.

The experiment lets CPython allocate and own a fresh live frame, then restores
saved slots and the instruction cursor during its first line callback. It does
not pass a manually allocated heap frame to the evaluation loop: modern CPython
expects a thread/generator-owned evaluation frame there. Exception tables belong
to the unchanged code object; active exception state also has to be restored.
There is no invented PyTryBlock equivalent.

Six isolated checks pass under AddressSanitizer and UndefinedBehaviorSanitizer:
module continuation without replaying its prefix, a loop iterator midway through
iteration, function locals/return values, a saved active exception with bare
re-raise and finally, 200 repeated recovery cycles, and a missing checkpoint
error. The [input-bound evidence](RECOVERY_PROBE.json) records their exact scope.
LeakSanitizer remains disabled.

This establishes in-memory single-frame feasibility only. The experiment copies
references and shallow namespace dictionaries, stops its test procedure with an
exception, and does not serialize a checkpoint. Such a stop can run finally
blocks; a real crash-recovery test must terminate a separate process without
unwinding and restore an independently serialized snapshot. Nested caller frames,
arguments, closures, coroutines, persistent object graphs, resource reconnection,
and original SPELL WS integration remain unqualified. No release gate is closed
by this experiment.

Before adopting the backend, integrate it with the existing SPELL WS storage and
executor lifecycle, give checkpoints an explicit format/interpreter/source
identity, reject mismatches and unsupported states before execution, and test
fresh-process recovery. Preserve object aliases and exception context, and prove
that completed DSS effects are not repeated. Qualify the supported platform/ABI
matrix before distributing a native runtime. An interpreter patch upgrade must
rebuild and rerun those checks; it is not an automatic compatible upgrade.

Reproduce the current experiment into a new output directory:

```powershell
docker build --progress=plain -f source_port/experiments/recovery-probe.Dockerfile --output type=local,dest=.qualification/v0.2/recovery-probe-02 .
python source_port/experiments/record_probe.py --evidence .qualification/v0.2/recovery-probe-02
```

The Docker build exports failure diagnostics as well; only the recorder validates
success. Source references are the exact CPython 3.13.14
[frame layout](https://github.com/python/cpython/blob/v3.13.14/Include/internal/pycore_frame.h),
[frame construction](https://github.com/python/cpython/blob/v3.13.14/Objects/frameobject.c)
and [evaluation loop](https://github.com/python/cpython/blob/v3.13.14/Python/ceval.c).
