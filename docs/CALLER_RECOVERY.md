# Logical caller recovery experiment

Eleven additional fresh-process checks now cover a saved Python caller chain.
The worker captures live frames and their own handled exceptions, saves them
together through the original WS storage, and dies with SIGKILL. The next
interpreter resumes the deepest frame, then transfers its return value to each
suspended caller's operand stack and saved return offset. Positional-only,
keyword-only, default and variadic arguments are restored, along with closure
cells shared between callers.

Exception propagation follows the saved code's exception table. Restoring an
instruction pointer and raising directly from the first trace callback is not
sufficient: the evaluator's local instruction cursor still refers to that initial
trace point. The experiment instead reads handler ranges/depths with `dis`,
restores the handler operand stack, and enters the saved handler. Checks cover
parent handlers and finally blocks, propagation through multiple callers,
context-manager suppression, exception groups and different active exceptions
in child and parent frames.

The [input-bound report](CALLER_RECOVERY_PROBE.json) includes eleven caller checks,
thirteen prior single-frame persistence checks and ten in-memory checks, all
passing under ASan/UBSan. The original native suite still passes: UTIL 18,
analysis/watch 57, WS storage 17, and three embedded interpreter cycles.
LeakSanitizer is disabled.

This is logical continuation: the original physical Python `f_back` chain is not
reconstructed. Introspection sees the new evaluation calls. Native C-call
boundaries are rejected before checkpoint publication, rather than discarding a
live C continuation. Captures also reject generator/coroutine frames and chains
over 128 Python frames. Arbitrary custom resource graphs, imported dependency
identity, historical traceback reconstruction, Windows and other interpreter
builds remain unqualified. Original executor/WS lifecycle integration and DSS
effect recovery are still release gates. No released package installs the probe.

The adapter is restricted to GIL-enabled CPython 3.13.14. Relevant interpreter
references are the [CALL/RETURN implementations](https://github.com/python/cpython/blob/v3.13.14/Python/generated_cases.c.h)
and [exception unwinding](https://github.com/python/cpython/blob/v3.13.14/Python/ceval.c).
The same exact-build, short-lived application-owned checkpoint restrictions as
the [single-frame experiment](PERSISTENT_RECOVERY.md) apply.

```powershell
docker build --progress=plain -f source_port/experiments/persistent-probe.Dockerfile --output type=local,dest=.qualification/v0.2/recovery-chain-final .
python source_port/experiments/record_persistent.py --evidence .qualification/v0.2/recovery-chain-final --chain
```
