# Native process spawn correction

The dev54 startup failure retained a child PID still executing SPELL-Context,
with no Executor login. That observation does not establish its underlying cause.
Dev55 separately demonstrates a process-launch hazard: a registered child fork
callback waiting on an inherited locked mutex prevents the old launch method
from reaching exec. The same compiled experiment completes with `posix_spawn`.

The candidate replaces only the frozen composed `SPELLprocess::popen` method.
The full archive/port/composition is reproduced before patching, and the method's
exact SHA-256 preimage is checked. The shell remains `/bin/bash -c`; command,
environment, current directory, inherited descriptors, parent identity and child
wait status are preserved. Spawn errors raise through the original process-error
path before a started event. There is one attempt, with no replacement/replay.

The ported runtime explicitly unblocks SIGINT, SIGTERM, SIGHUP and SIGQUIT in
the child. Spawn attributes preserve that policy while retaining unrelated
blocked signals and leaving the parent thread's mask unchanged. The patch does
not remove this prior correction.

## Executed regression

`server/tests/test_native_spawn.py` compiles the exact frozen method and the
patcher's actual output, then launches real Linux child processes. Nine checks
cover the inherited callback stall, environment/arguments/current directory/file
descriptor and PID preservation, exit/signal status, signal-mask policy, explicit
spawn failure and source-preimage rejection. Stalled test children are killed and
reaped. This demonstrates the declared callback hazard; it does not prove that
the historical CI child stalled in that callback or establish every spawn case.

The first dev55 candidate `d86c9ed` guarded the unported archive method instead
of the installed composed method. Six native profile builds rejected that
preimage before launching any candidate processes. The corrected candidate
`bf9e6bb` uses the reproduced composed method and adds the signal-mask regression.
Failed-build results and source identities are retained separately from the
corrected candidate's qualification.

## Admission timing

The agent now emits at most 512 `native-admission-timing` records per server.
Records carry the allowlisted request kind, an opaque member correlation key,
monotonic accept timestamp, total elapsed time and authentication/frame/epoch/
dispatch/reply durations. Outcomes distinguish allow, deny and lost reply.
No credential, request body or raw member identifier is logged. These records
complement native startup stages and `native-admission-transport-failed` records
to investigate the separate historical binding-deadline failures.

The original four-second native admission deadline is unchanged. Successful
stress samples do not retrospectively explain old failures. Full native-family
and release qualification remain open.

## Source-bound qualification

Candidate `81b8b41be71a3420241ed8163535e65518987226` passes the available hosted component profiles.
1,210 service tests, 71 overlapping fault probes and 241 portable tests pass, with zero failures/errors/skips. All fourteen core jobs and five ancillary workflows pass. All nineteen artifact archives and recorded source hashes are verified. Seven controller/network cases and nine compiled spawn cases pass. All eleven full-release gates remain unqualified.
[The receipt](evidence/controller-network/qualification-summary.json) and [executed run](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40278694435) retain the exact result.
