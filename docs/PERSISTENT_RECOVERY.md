# Persistent single-frame recovery experiment

The original `SPELLwsStorage` now participates in a separate-process recovery
experiment. A live frame is captured at a line trace, serialized through the
actual patched native storage class, and committed with file fsync, atomic
replacement and directory fsync. The test worker then kills itself with SIGKILL.
A fresh interpreter reads the checkpoint and continues the saved frame.

Thirteen persistent checks and eight in-memory checks pass with AddressSanitizer
and UndefinedBehaviorSanitizer. LeakSanitizer remains disabled. The prior native
suite also passes: UTIL 18, analysis/watch 57, storage 17, and three owned
interpreter cycles. [Recorded evidence](PERSISTENT_RECOVERY_PROBE.json) binds these
results to the native and experiment source hashes.

The checks cover module and argument-free function continuations, loop iterator
position, aliases/cycles across namespaces and operands, dynamic functions sharing
their original module namespace, mutual recursion, and handled exceptions with
cause/context identity, notes and bare re-raise. A file effect before the crash
appears once. A finally block does not run when the process is killed; it runs
once during the continuation. This file-effect check does not qualify DSS
exactly-once behavior.

The experiment rejects changed source/runtime identity before unpickling, checks
payload integrity, bounds native slot counts and offsets, rejects directly or
container-reachable live files/sockets, and retains the previous checkpoint when
failure is injected before atomic replacement. It also restores an existing
trace callback after either successful or failed experimental execution.

Serialization uses hash-pinned cloudpickle 3.1.2 for short-lived, application-owned
checkpoints on the exact same runtime build. It is not a long-term archive or an
untrusted import format. The upstream [serialization constraints](https://github.com/cloudpipe/cloudpickle/blob/v3.1.2/README.md)
apply. The version-pinned `globals_ref` memo is seeded with the frame namespace;
without this, restored functions silently read a separate, stale globals copy.
The native adapter remains restricted to GIL-enabled CPython 3.13.14 and Linux
x86_64. Namespace and operand aliases are serialized together in one graph.

This is still an experiment, not a completed v0.2 gate. Nested callers are not
resumed, argument/closure/generator/coroutine frames are unsupported, arbitrary
custom object graphs and external resources are unqualified, and historical
traceback frames are not serialized. Integration with the original executor,
warm-start lifecycle, driver/DSS effect tracking and platform packaging remains.
Neither released package installs this experiment or its codec dependency.

Reproduce into a new directory:

```powershell
docker build --progress=plain -f source_port/experiments/persistent-probe.Dockerfile --output type=local,dest=.qualification/v0.2/persistent-probe-qualified .
python source_port/experiments/record_persistent.py --evidence .qualification/v0.2/persistent-probe-qualified
```

The Docker build exports failure diagnostics too; the recorder is the acceptance
check. The original six-check [in-memory report](RECOVERY_PROBE.json) remains a
historical milestone and is not overwritten by these later results.
