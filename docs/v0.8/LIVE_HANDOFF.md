# Private single-host live-family handoff

The `host-freeze-candidate` native pause profile permits bounded repeated
handoff of an existing native family, up to eight accepted transfers. It requires the retained single-use worker,
all command/prompt/member journals, and the separate host certificate configured
by `host_settlement`. It is disabled by default.

A accepts B's pending claim through the existing controller API. Context first
fences A's mutation capability. The trusted deployment host pauses the exact
prebound Docker container and checks the kernel cgroup-v2 `frozen=1` completion
state. Every originally captured pidfd must remain live. Each registered native
member must match its namespace PID, start ticks, executable hash and immutable
member binding. All processes and threads in the private container are frozen,
including background Python and descendants. A main-Executor PAUSED status is
not accepted as this proof.

Context independently reconciles the sealed member roster, completed native
command handlers, known closed prompt outcomes and driver calls. External
operations require all five ACKED stages with identical Context and independent
driver receipts. Any unresolved result blocks transfer and preserves reservations.
Queued commands that have not crossed final consumption retain their original
owner grants; they cannot consume under B. Open prompts are rejected before A's
acceptance changes authority, so A can resolve them first.

After the host proof, Context atomically assigns B the next owner epoch while
leaving the family paused. C sees the new owner and pause state through the
read-only execution listing. B binds its controller capability and explicitly
requests RUN for the whole family. Other commands are refused until that resume.
The host rechecks the frozen container before authorizing thaw.

The host updates a read-only, nonsecret runtime epoch marker before unpausing.
The original consumed worker obtains a new start-shaped runtime credential and
consumption proof in one delivery over its pinned mTLS channel. Both remain only
in memory. An activation reply lost after commit is never retried. A's runtime
credential and controller capability no longer authorize any operation.

The candidate Executor loads a fixed, source-hashed trusted bootstrap before
driver initialization, even with isolated CPython. The frozen driver sources,
command scheduling and RPC budgets remain unchanged. Original native driver
calls capture the epoch in gRPC metadata before dispatch.
Native admission callbacks capture it before opening their Unix channel. The
worker rejects an old captured epoch instead of stamping it with B's identity.
All new DSS operations carry the newly issued grant in both effect ledgers.
Existing native member records preserve their original family identity; they are
not rewritten as new processes or replayed startup grants.

The host owns `/v1/host/handoff/status`, `/complete`, and `/resume`, using schema
`openbexi.host-handoff/1`, Context/Execution IDs and the current authority
incarnation. Worker activation uses `/v1/worker/handoff-activate` and the old
single-consumer runtime proof. Neither workers nor browser clients can submit
host evidence. C's public view contains no host evidence, runtime credentials or
resume authorization.

The host is part of the trusted deployment boundary. Freeze completion is only
valid while it keeps that container frozen. Host loss, Context restart, expired
barriers, missing receipts, changed process identity and uncertain activation
never authorize automatic resumption or reservation release. The host retains
or terminates the family after failure; it must not unpause it as cleanup.

This candidate seals the already admitted child roster and retires unused
startup RUNs. It rejects all subsequent child creation. A later transfer needs
the previous runtime activation to be complete, settled journals, a fresh barrier,
a fresh host freeze proof and an explicit resume by the next owner. Schema 20
archives completed handoff and pause records in the same transaction that fences
the next round. The original family identity remains unchanged. Every earlier
controller capability, runtime credential and host proof remains fenced, including
when ownership returns to its original user. A ninth transfer is rejected before
revoking the current owner's authority.

Open-prompt transfer, reconnect recovery and Kubernetes freezer attestation
remain separate qualification work. Workers stay single-use and reservations
remain held through handoff. The eight-transfer bound is covered by real mTLS
service tests; the original native process cohort covers two successive transfers.

The dedicated `--native-handoff` qualification runs the rebuilt native runtime
with a root, child and background thread, observes stationary counters during
each host freeze, resumes the same processes first under B and then under A at
epoch 3, rejects delayed native driver packets from both earlier epochs and A's
original queued STEP, checks B's native PAUSE/RUN, and checks DSS receipts from
all three owner epochs. The installed IDE profile additionally checks native
STEP through its source-position change. The cohort verifies C cannot mutate and an
unrelated reservation remains unchanged. Foundation regressions cover real mTLS,
concurrent and lost activation, restart, expiry, forged freezer evidence, prompt
uncertainty and complete/partial/conflicting independent DSS histories.
After continuation, the host obtains a terminal fence, verifies exit of every
original process, reconciles all three owner epochs' DSS receipts and releases only
the finished family's reservations. The unrelated witness and spent-worker
status remain intact.

The repeated-transfer cohort and installed IDE profile passed at
`83113624ff3853d3c4c802a50b48dad4f3703429`: eight original processes, two
three-second freezes, A→B→A ownership, three DSS commands with fifteen matching
stage receipts in each independent ledger, and terminal release preserving the
witness reservation. Its hosted foundation passed 1,065 tests without failures,
errors or skips. The subsequent startup-stress candidate and exact artifact
identities are recorded in the [current component receipt](evidence/repeated-handoff/qualification-summary.json).
The [earlier single-transfer receipt](evidence/native-live-handoff/qualification-summary.json)
remains historical evidence. No full-v0.8 release gate is promoted by this private profile.
