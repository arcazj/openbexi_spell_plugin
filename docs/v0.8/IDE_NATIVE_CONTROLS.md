# Paired IDE controls for an existing native execution

Server `0.8.0.dev44` and the exact IDE pin in `IDE_PAIR.json` add Run/Continue,
Step, Pause, Abort and Close execution to the asynchronous server panel. These
actions control an already provisioned retained native execution. Public worker
provisioning remains unavailable and `runtime_enabled` remains false.

## Enablement and authority

The Context must explicitly enable `native_commands: "owner-queue"`, or
`"owner-terminal-candidate"` for Abort/Close. Its other native admission,
worker, host and settlement profiles must already be configured. The Listener
separately requires `native_command_contexts: ["<configured-context-name>"]`.
Omitting this list disables the command route and its advertised capabilities.
Unknown Context names and invalid list types reject configuration at startup.

The only new public operation is
`POST /v1/contexts/{context_id}/commands`, with the existing native command
payload and a mandatory `Idempotency-Key`. The gateway preserves the pinned
certificate identity; the Listener applies its Context scope; the Context
rechecks live roles, current owner, epoch, generation and the original delivered
controller capability. Copying that capability into another user's client
does not confer authority. Role revocation takes effect before replay lookup.

Health advertises the configured commands allowed by the current user's roles.
Pause, Abort and Close require `execution:control`; Run and Step additionally
require `execution:start`. The UI also requires the selected current owner,
an original cached controller proof and the admitted native lifecycle. Observers
receive no advertised command authority. Server authorization remains decisive
even if a caller bypasses the UI.

The installed client sends each intent once. It does not retry after response
loss, repair an epoch from a read-only listing, silently reacquire a capability,
or fall back to a local execution. Successful queue admission does not prove
that the native command executed. Native admission and settlement journals
remain the source of completion evidence.

## Handoff through the panel

For the private single-host profile, B requests control and A explicitly accepts.
A's cached proof is discarded when acceptance enters REQUESTED/PAUSING, before
the host freeze completes. The separate trusted host proves the original family
is frozen and Context settles the required journals as described in
[LIVE_HANDOFF.md](LIVE_HANDOFF.md).

After ownership moves to B in HANDOFF_PAUSED, B uses Reconnect control to obtain
its own controller proof and explicitly presses Run/Continue. Other native
commands stay disabled until this resume. C can observe B's paused and resumed
ownership but cannot mutate the family. This profile permits one transfer and
does not create new children after transfer.

## Executable qualification

`python scripts/qualify_v08_native_launch.py --native-ide` installs no substitute
client. CI installs the exact paired IDE commit first; the harness checks the
installed package version and client module hash against `IDE_PAIR.json`.
It then starts separate Listener and gateway processes with three distinct
client certificates and the private native Context. These edge processes have
no host-manager interface. Initial worker provisioning remains a separate
trusted-host operation.

The native cohort exercises A/B handoff, C observation, stale-owner denial,
whole-family freeze, B's explicit resume, native Pause/Step/Run and final host
settlement. Step must change the original native current-source-position and
pause again. Four additional cases send Abort and Close through the installed
client while native execution is paused or running. The separate native-terminal
profile retains the full sixteen-case terminal matrix.

Twenty-two service regressions use the actual client through real TLS
gateway/Listener/Context hops. They check all five operations, duplicate queue
admission, stolen proofs, live role revocation, disabled configuration and
A/B/C handoff. Qt tests separately check button enablement, asynchronous actions
and observer denial; the native CI cohort is headless client qualification,
not a claim that a graphical browser or every debugger feature was exercised.

Exact workflow, artifact, source-hash and installed-wheel results are retained
in [the component receipt](evidence/native-ide-controls/qualification-summary.json).
The full release gates remain false. Public launch, variables/breakpoints,
browser/WSS, Git collaboration, repeated transfer and deployed recovery still
require implementation or qualification.
