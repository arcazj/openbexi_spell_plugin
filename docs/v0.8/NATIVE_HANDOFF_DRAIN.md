# Drain transport before host freeze

The follow-up workflow for `5ec942985689c06b0bff2f1f820ab54928d8547d`
failed in the native handoff, native IDE and startup-stress profiles. Earlier
dev47 successes do not qualify these later attempts. The failed artifacts are
12622378963, 12622453888 and 12623042788 in workflow 40257178288.

The handoff artifact records a status query captured before freeze, rejected
after the epoch changed. The IDE artifact records a command-poll TLS exchange
interrupted by freeze, then BrokenPipeError after thaw. Both failures terminated
the agent before the next activation. These are distinct from startup failures.

Development candidate dev48 adds an explicit transport-drain checkpoint before
each host freeze. The host writes the current runtime marker to its existing
read-only control mount. The agent finishes its current loop iteration and waits
for its counted outgoing RPCs to complete, then holds new RPC admission. Its
acknowledgement reports only transport idle, with `quiescence_proven: false`.
Native root, child and background execution remain subject to the existing
independent cgroup freeze, original process handles and settled-journal checks.

Deleting the prepare marker cannot resume the agent. It requires a new runtime
marker and a successful, original one-shot activation receipt. Lost activation
replies remain held and are never retried. Earlier native packets still retain
their captured identity and are denied. The preparatory marker grants no owner
or worker authority and is not accepted as host freeze evidence.

The startup-stress artifact has all ten roots and nine children bound. Its tenth
child reaches `binding-requested` but receives a Fault; the previous diagnostic
discarded its status/code/cause. Directory cleanup then overwrote the primary
exception. Dev48 retains those bounded error categories and preserves the first
failure separately from cleanup failures. It attempts all resource cleanup and
does not delete potentially live bind-mount state after failed container removal.
This is not an established fix for the historical native startup fault.

Qualification must include focused mTLS regression tests, all service checks,
the rebuilt native handoff and paired IDE profiles, terminal cases and fresh
startup stress at the exact candidate. Full-v0.8 release gates remain blocked
until their complete acceptance criteria pass.

## Executed dev48 checkpoint

Candidate `40f38fb10690652819b367eafd9695f3ad0c69ce`, paired with IDE
`faf2052ba764cbc147ef05f261164853e08489c8`, passed all thirteen jobs in workflow
40258910955 and all four deployment/inventory workflows. Its 1,094 service tests
include the real-mTLS drain and failure-preserving cleanup regressions.
Both actual-native and installed-IDE profiles record three zero-active-RPC
drains, two ownership transfers and a same-owner reconnect with the same eight
processes. The sixteen-case terminal matrix and twenty-four fresh root/child
startup-and-settlement cycles pass. Historical startup causes remain unresolved.

Twenty distinct installed IDE certificate identities now concurrently observe
ten native executions across Listener SIGKILL and replacement. All thirty native
PIDs survive, every procedure advances, every observer remains read-only and
outage reads fail closed. No browser/WSS result is inferred.

The initial dev48 kind runs exposed a separate image-tag mismatch: CI loaded
dev47 while the renderer requested dev48. Building and loading image tags
directly from the renderer fixes that mismatch. The corrected kind prelaunch
workflow passes and retains bounded status for all five ready workloads. Failed
runs remain in [the image-mismatch receipt](evidence/native-handoff-drain/kind-tag-mismatch.json).

Seventeen final artifact digests/ZIP checks and their recorded repository source
hashes were verified. See [the qualification receipt](evidence/native-handoff-drain/qualification-summary.json),
[retained prior failures](evidence/native-handoff-drain/prior-failures.json)
and [the test report](TEST_REPORT.md). All eleven full-release gates remain false.
