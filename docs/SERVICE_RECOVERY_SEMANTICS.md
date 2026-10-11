# Native service recovery semantics review

The supplied 2.6.10 source distinguishes a long-running `@SpellService` from an
ordinary procedure. Recovery claims must follow the actual execution path.
The archive identity and manual inventory are recorded in [source review](SOURCE_REVIEW.md).

| Operation | Current evidence / acceptance |
| --- | --- |
| Procedure checkpoint recovery | Qualified ON_LINE and ON_STEP fresh-process crash recovery; see [executor recovery](EXECUTOR_RECOVERY.md). |
| Service Python failure or process loss | Qualified watchdog cold restart in a new native process, with normal replacement shutdown; see [service restart](SERVICE_RESTART.md). |
| Context loss while service remains alive | Qualified same-process pause, control reattachment, resume and normal cleanup in [live reconnection](LIVE_RECONNECT.md). |
| Service checkpoint resumption | Explicitly unsupported. Native API and command requests are qualified to fail before startup, preserving the requested checkpoint. |

## Original source paths

Paths below refer to unchanged source inside `docs/reference/SPELL2.6.10-src.zip`.

- `src/service/src/SPELLserviceMain.C` accepts recovery startup parameters.
- `lib/SPELL_EXC/src/SPELLserviceInterpreter.C` prepares warm-start support,
  installs it on the frame manager and exposes `recover()`.
- `lib/SPELL_EXC/src/SPELLserviceImpl.C::recover()` loads the driver/environment,
  restores frame-manager state, replays the stack and calls `executeInternal(false)`.
- In that same class, `executeInternal()` comments out the call to
  `m_frameManager->execute()` and instead invokes the registered service object's
  `start()`. A restored logical continuation therefore cannot be assumed to run
  through the qualified procedure frame-manager path.
- `lib/SPELL_CTX/src/SPELLserviceManager.C` contains a commented-out recovery
  manager implementation; active watchdog recovery starts a new service.
- `lib/SPELL_CTX/src/SPELLcontext.C::attachExecutor()` contains a service-specific
  GUI-control rejection branch. The active route first calls
  `SPELLexecutorManager::getExecutor()`, which falls back to
  `SPELLserviceManager::getService()`. Registered services therefore use the normal
  executor control path, bypassing that catch/rejection branch. Build 43 observed
  control being granted to the reconnected service; Build 49 qualifies resume and
  normal shutdown. The earlier static-only interpretation
  that all service GUI control was rejected was incorrect.

The supplied 2.4.4 manuals describe procedure recovery and generic driver
services. The reviewed extracted manuals contain no `SpellService` or
`startService` contract for this newer source facility. Generic TM/TC/EV driver
services are different from native registered Python services.

The preserved 763-row language inventory contains no `SpellService`,
`startService` or native service checkpoint artifact. Its snapshot SHA-256 is
`e83b6151366937f96c6cff9c163fbc72b4559ce88123f9698faa0ac4072a33cd`.
This absence does not make the advertised service `-r` path safe: acceptance must
still prevent a requested recovery from silently restarting the service body.

## Checkpoint policy

The port retains upstream cold restart and live reconnection. It rejects service
`-r` requests before importing a service, loading a driver or reading the requested
checkpoint. Direct interpreter initialization and the service implementation's
`recover()` entry point also reject the request. This prevents the incomplete
upstream restore-then-`start()` path from silently rerunning a service body.

The original context adds `-w` to service launches. That compatibility flag remains
accepted, with a diagnostic and checkpoint creation disabled. In-process error
handling cannot claim that a service continuation is recoverable. Ordinary
procedure ON_LINE/ON_STEP recovery is unchanged and remains independently tested.

The new qualification exercises both native API entry points before Python
initialization and the real service command with `-r`, with and without `-w`.
It requires an explicit error, no executed Python body, and unchanged checkpoint
bytes. [Build 52 evidence](NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json)
passes all preceding native gates and ten context tests covering 25 lifecycle
runs. Two API rejections occur before Python initialization; two real command
rejections preserve the input checkpoint. Both process kinds also pass three
live reconnect repetitions, with bounded normal procedure closure.

Native registered-service checkpoints have no contract in the supplied manuals
or language inventory. This policy is an explicit source-port limitation, not
an implementation of service checkpoint resumption. If future requirements add
that contract, it needs its own implementation and qualification. If checkpoint
support is implemented, independent
crash/restart tests must prove that the original service body is not rerun from
its start, persisted state is restored and owned worker threads are recreated
safely. Imports, command-line option acceptance, commented source and ordinary
cold restart cannot satisfy this gate. Full conformance and v0.6 remain open.
