# Native forced-pause cancellation

The second independent native build from `120ed73` failed the unchanged context
lifecycle gate. Its service reconnect test recorded a forced pause at
15:08:27.635, context close at 15:08:28.017, and service process completion at
15:08:28.842. The pause still timed out at 15:08:32.635. All six native binaries
were byte-identical to the passing first build. The failed pair, exact native
logs, source snapshot and hashes remain in the follow-up worktree under
`.qualification/v0.6/rebuild/ff3c8de019b44988b7154ba18682706e`.

The original port checked `m_closing` only on entry to `forcePause()`. An active
wait therefore survived a concurrent close. The separate checked recipe
`source_port/shutdown_pause_patches.py` changes only this method in the original
context-side `SPELLexecutor.C`. It preserves the five-second absolute deadline,
distinguishes target status from cancellation, and observes atomic close or
terminal process flags between bounded event waits. The public `waitStatus`
method, header, central port recipe and original lifecycle assertions are
unchanged.

The focused C++ probe exercises ten controls against the original native class:
already closing, already finished, successful pause and interrupt, close and
process completion during each active wait, a genuine timeout with unrelated
notifications, and the unchanged ordinary status wait. Each scenario uses one
process-owned native model with a synchronized virtual command dispatcher. It
does not claim IPC transport or model teardown coverage. A discarded first
fixture destroyed uninitialized IPC models on the stack and exposed a surviving
trash thread; its sanitizer failure remains in `candidate-build-06.log`.
Separate processes retain those models for their complete lifetime. The
unchanged full context gate supplies actual native IPC/lifecycle evidence.

The first full context run passed all native checks, but Windows extraction of
its retained tar exceeded the ordinary path length limit. The original wrapper
failure remains unchanged. `collect_shutdown_pause.py` recovered that archive
using checked extended paths and verified all 663 files. The runner now uses
those paths directly; a fresh unchanged native run validates its complete
collection path before final canonical recording.

The diagnostic image retains both baseline and candidate logs, exact original,
ported and patched source, compiler/link commands, object hashes and executable
hashes. `record_shutdown_pause.py` requires the exact five baseline failures,
all ten corrected controls, and the complete unchanged context gate with
25 lifecycles and two service checkpoint rejection checks. Its canonical record
binds immutable raw reports and both raw and Git-compatible LF source hashes.

This tranche allocates no manual clauses and does not accept either release.
It does not fix the separately observed out-of-order RUNNING/PAUSED delivery,
guarantee real-time cancellation, or eliminate the check/command dispatch race.
The independent child lifecycle recipe modifies another block in the same
source file; integrating both requires an explicit checked composition chain.
A new reviewed source freeze and two complete independent wheel builds remain
necessary after this diagnostic correction.
