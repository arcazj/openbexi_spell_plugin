# G1 independent review and approved implementation contracts

Owner authorization: Jean-Christophe Arcaz, in the review conversation:
**"Approved , move forward"**. This authorizes incorporating the independent
review recommendations and proceeding with staged implementation. It does not
authorize merge, tagging, release publication or production migration.
The owner subsequently directed "Move forward , approve all next steps";
routine implementation, checks and draft-PR updates continue under that
standing authorization. Final merge/publication remains held for a reviewable
qualified result, as stated in the implementation conversation.

Reviewed proposal: `2d02bb1f030eebca61374dbbba34938b30c29e5d`.
The independent review identified six P1 architecture issues and four P2
contract issues. The binding decisions below resolve the design questions;
they are **requirements for implementation**, not passed runtime tests.
G1 is approved for staged implementation under these contracts. C-L retain
their own gates; no implementation or deployment gate is inferred from G1.

## F1: worker admission and Kubernetes duplicate starts

One Job name is not one runtime. A worker must remain stopped before user code
until Context durably consumes one start grant bound to
`(authorityIncarnation, ExecutionID, workerGeneration, workerIncarnation)`.
For Kubernetes, the authenticated worker incarnation includes the immutable
Pod UID, verified against the API and an individually issued workload
credential. A Pod-provided UID, shared ServiceAccount or labels alone are not
authentication. A second Pod/agent cannot consume the same grant or obtain a
replacement by timeout. Every worker message and effect uses that binding.

Jobs use `parallelism: 1`, `completions: 1`, `restartPolicy: Never`,
`backoffLimit: 0` and `podReplacementPolicy: Failed` on supported cluster
versions. These are retry-reduction controls, not an exactly-once guarantee.
The application grant remains mandatory, including after Job recreation.
Replacement requires explicit old-worker shutdown and effect-settlement proof.
No TTL, Job terminal status alone, node eviction or heartbeat loss clears a hold.

## F2: preserve original authority and implement a transfer barrier

Context issues an immutable admission grant when accepting a control/runtime
operation. It includes authority incarnation, execution, epoch, worker binding,
originating connection generation, request ID and operation digest. The worker
can return the grant for validation; it cannot mint one. Context never stamps
its *current* epoch onto a delayed request to authorize it.

Acceptance first enters a per-execution transfer barrier. Close new old-epoch
admission, settle or mark uncertain previously admitted effects, and request
worker quiescence of control/native/prompt queues. Do not acknowledge a
transfer as effective until the barrier is proven. Failure leaves the prior
owner recorded, mutation/effect admission fenced, and recovery required; it
never grants the claimant automatically. After barrier success, CAS
owner/epoch, close the claim and append events in one short transaction.
The new owner must explicitly resume a paused runtime under a new grant.
Acceptance can be asynchronous; the UI notification itself is nonblocking.

Delayed prompt/debug/driver requests retain their original admission identity
and are rejected or settled under that identity. The old worker's autonomous
continuation is not implicitly rebound to a new owner's epoch. A/C are untouched
when B transfers. A runtime already paused before launch can satisfy the barrier
without a running worker; this is not evidence for native pause qualification.

## F3: actual send ordering, stages and lock scope

Lock order is per-execution admission mutex, then short authority SQLite
transaction, then adapter/resource mutex as needed. Never wait for network
receipts or worker pause inside a SQLite write transaction or Context-wide
authority lock. Claim/reconnect/heartbeat for unrelated executions must have
explicit bounded latency even when one adapter is blocked.

Persist effect intent and reserve receipt capacity before sending. The final
live grant check and bounded actual socket write are serialized against
transfer by the same per-execution admission mutex. Release it before waiting
for the external receipt. Each multi-stage write has its own recorded stage
and grant check; transfer waits for settlement of already admitted stages or
becomes recovery-required. It cannot report completion while an old stage
could later be newly admitted. A partial send is uncertain. No new owner,
retry, restored database or transport reconnect can resend an uncertain stage.

The authority and driver ledgers are separate crash boundaries. Persist the
cross-ledger operation ID before any effect; record intent before send and
receipts before declaring settlement. A crash between ledgers means a hold,
never a synthesized receipt. A bounded transport deadline is mandatory.

## F4: safe initial Compose worker profile

Initial v0.8 Compose workers are **single-use per container incarnation**.
There is no automatic reuse or in-agent recreation. A worker starts at most
one native execution family, then exits after proven descendant shutdown; an
uncertain worker remains reserved. Capacity is a fixed pool (initially ten),
replenished by explicit host/operator recreation only after reconciliation.
This operational limitation is preferable to claiming unproven safe reuse.

Native cooperative pause must acknowledge all participating threads/children
and drain native control/prompt queues. If that cannot be proven, Context
fences every effect and reports uncertainty, without claiming PAUSED or killing
a procedure merely because its controller disconnected. Independent host
whole-container pause/shutdown is an authorized recovery operation, not a
Docker socket exposed to Listener/Context/worker. The agent must not pretend
that a parent PID exit, process-group stop or /proc scan proves quiescence.

Automatic worker reuse or delegated cgroup freeze is a later, separately
reviewed extension requiring real descendant, credential and generation tests.
No CAP_SYS_ADMIN, privileged container or host-management service is added.

## F5: mandatory workload admission

Kubernetes uses a dedicated worker namespace per Context, separate from its
authority namespace and storage. RBAC **and** fail-closed workload admission
are both mandatory. Namespace isolation is not a substitute for admission.
Ordinary RBAC cannot restrict Job-create permission by caller-selected labels.

Allow only approved image digests, entrypoints, resource bounds, nonprivileged
worker ServiceAccount and explicit snapshot/worker-certificate volumes. Deny
authority PVCs, driver/Context credentials, arbitrary secret/config/host mounts,
host namespaces, privileged containers, added capabilities and unapproved
init/sidecar/debug containers. Disable worker API token automount. Enforce
Restricted Pod Security and default-deny networking. Policy covers Job
templates and created/updated Pods, not just a CLI's well-behaved requests.
Read/delete ownership is enforced by namespace and authenticated Context
identity; labels are inventory only. Context has no permission to modify the
admission policy, RoleBindings or service-account privileges.

## F6: supported SQLite and replacement profile

Initial supported authority profile is Linux, one process per Context, local
ext4 storage on one host/node, SQLite DELETE journal with synchronous FULL,
and an OS-exclusive lock on the same state directory. No NFS/SMB, copied-live
volume, automatic node relocation or concurrent authoritative replica is
supported. Kubernetes local PV has node affinity, reclaim Retain and a
stop-before-start rollout. CSI/RWOP profiles require separate storage/fencing
qualification; RWO/RWOP alone does not fence external effects.

Each startup creates a fresh unpredictable authority incarnation and revokes
all prior worker/control grants. Recovery preserves logical reservations,
advances epochs and marks active runs RECOVERY_REQUIRED. Manual replacement
or restore requires old process/node and driver-egress fencing, shutdown and
effect settlement proof, credential rotation, and a new incarnation. A lock on
a new volume or an increment from an old backup is never sufficient proof.
The old authority's access must be removed before admitting the replacement.

## F7: acceptance delivery and connection rebinding

Claims bind stable user ID and target connection generation. Validate both
at the transfer CAS. Acceptance replay returns its durable decision, never
plaintext capability or another transfer. Lost token delivery leaves the new
owner recorded; it does not revert to the previous owner. Authenticated owner
rebind rotates capability and increments connection generation atomically,
invalidating old sockets and delayed close callbacks. It is not a transfer.
Durable hashes cannot recover a lost plaintext capability. Live authorization
precedes idempotency-result disclosure, including after role revocation.
Controller-origin operation grants include connection generation; execution
epoch alone is not sufficient to revive an old browser operation.

## F8: native child execution families

The top-level ExecutionID owns a native execution family. Child procedures
inherit its owner, epoch, worker/effect grant and teardown boundary. Nested
logical ProcedureIDs are reserved in Context before native child RUN, in the
same Context-wide reservation namespace as top-level procedures. Recursive or
colliding child starts fail explicitly; no silent exception to uniqueness.
Child source and dependencies belong to the immutable family inventory.
Child prompts/control cannot bypass Context. Native visible/hidden,
blocking/nonblocking and repeat/return semantics must be requalified with this
admission rule; any behavioral deviation needs explicit compatibility approval.
No native child integration is considered complete until that gate passes.

## F9: transport trust and complete route admission

See [SERVER_CONTRACT.md](SERVER_CONTRACT.md). The initial server foundation is
internal TLS 1.3, pinned leaf certificates plus CA/hostname verification, and
explicit role/Context/subject policy. It has no browser session, WSS or worker
launch route. Those future routes stay disabled, rather than trusting a UI
button or generic certificate validity. Source/results/replay/snapshots require
read permission as well as mutation checks. Every new route must enter the
route/role matrix before being exposed. Private native helper ports remain
loopback-only and unreachable from client/worker peers.

## F10: shared-state and resource permissions

Blackboard values are intentionally Context-wide and visible only to authorized
members. CAS is ordering, not authorization. The initial shared write operation
requires `blackboard:admin`; owning one execution grants no Context-wide write
permission. Future per-execution namespaces require that execution's grant.
Driver reset/rebind and global configuration require separate administrator
permission and no unsettled dependent operations. Per-resource mutexes and
declared adapter capabilities govern intentional sharing. Procedure uniqueness
does not grant cross-Context external-resource exclusivity.

## ADR disposition and evidence

| ADR | Approved direction / binding revision |
|---|---|
| 01, 02 | Independent Listener and single Context authorities; F3/F6 |
| 03 | CPython 3.13/native provider; F4/F8 qualification mandatory |
| 04 | Static single-use Compose workers; fenced K8s grants and F1/F4/F5 |
| 05 | Supported single-node local SQLite profile; F6 |
| 06 | Context-wide logical identity including native children; F8 |
| 07, 08 | Original admission provenance, explicit consent, F2/F7 |
| 09 | Proven cooperative pause or fenced recovery; no false PAUSED; F4 |
| 10 | Explicit TLS/role/RPC contracts; F9 and SERVER_CONTRACT.md |
| 11 | Context-bound effects and actual-send/stage settlement; F2/F3/F10 |
| 12 | Separate offline migration/rollback with F6 proof; no downgrade |

Acceptance tests are expanded in ACCEPTANCE_PLAN.md. Runtime results belong
in TEST_REPORT.md and machine-readable evidence. The original review and
baseline remain tied to their original SHA; historical integrity assertions
that runtime source is unchanged must not be rerun as current implementation
claims. User approval resolves the staged-work authorization; it does not
turn an unexecuted deployment test into PASS.
