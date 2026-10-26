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
