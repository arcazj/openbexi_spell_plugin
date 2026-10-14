# Native procedure checkpoint source identity and context recovery

This correction uses the original `SPELLprocedureManager::getProcFile(instance)`
resolution in `prepareWarmStart`, matching `prepareExecution`. Script mode keeps
its original physical source path. Instance and timestamp checkpoint names stay
unchanged. The separately checked context correction composes after the DATA
context fix and accepts the recorder's actual single `.wsp` envelope plus its
original exact `.ASRUN` companion. It rejects empty, path-like or control-bearing
stems and matches the complete WSP filename. The recorder still verifies its
version, CRC, payload and source/runtime identity.

All behavior checks use the installed original NativeSession, context, executor,
IPC and procedure manager. A private launcher wrapper changes only the generated
fixture's `SaveStateMode` before the original listener starts; subsequent calls
execute the original installed launcher. There are no instance-name source
aliases or synthetic WSS/WSD files. The source recipes verify the complete
original archive and composed preimages before modifying either native unit.

`checkpoint_identity_run.py` exercises both ON_LINE and ON_STEP. Error controls
cover module, named and nested uncaught exceptions followed by CMD_RECOVER and
failing user actions that keep the executor paused. Recovery controls cover real
checkpoint metadata, concurrent instances of the same source with different
ARGS/state, actual kill/reopen without replaying module effects, changed source,
CRC corruption, missing/empty WSP and ASRUN, partial names and six invalid stems.
Failures include cleanup, connection and sanitizer errors. The gate runner uses
the original standalone23 and context10 suites, including the two explicit
native service checkpoint rejection controls.

The diagnostic image keeps the audited original wheel/RECORD and explicitly
records its native overlay. It is not an accepted distribution. Fresh integrated
rebuild and qualification are still required. The existing language-evaluation
PY rows explicitly exclude checkpoint/recovery support; this evidence does not
expand or double-count those contracts. Live external resources, asynchronous
and cross-thread continuations and native service recovery remain excluded.

Retained intermediate reports include the original main#1 source-resolution
failure, obsolete WSS/WSD preflight rejection, asynchronous status/registration
fixture ordering errors, the live-file-resource guard, and invalid STRING prompt
configuration. Only complete final runs and unchanged full gates enter the strict
`checkpoint_identity_report.py` checkpoint; intermediate failures remain raw
qualification evidence.

Changed-source and corrupt-file startup rejection is established by an ordered,
procedure-specific fatal native MSG_ERROR containing the exact integrity reason,
with no new effects and unchanged input checkpoint bytes. The retained runtime
trace then reports UNINIT. Stable terminal ERROR display and subsequent recovery
UI behavior are outside this tranche; no successful or runnable recovery is
claimed for the rejected state.
