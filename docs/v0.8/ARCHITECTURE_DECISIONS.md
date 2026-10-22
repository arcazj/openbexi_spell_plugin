# Proposed architecture decisions

All ADRs are `TARGET-v0.8`, **pending owner and independent architecture/security
review**. Recording a decision here is not approval or implementation evidence.

| ADR | Proposed decision | Rationale / rejected alternative | Gate |
|---|---|---|---|
| ADR-01 | One separate Listener process; Contexts have independent lifetimes | Gateway restart must not kill workers. Reusing a UI-owned service conflates lifetime and authority. | C |
| ADR-02 | One authority process per ContextID; all management functions inside it | No standalone Management Service. Do not deploy concurrent authoritative replicas. | D |
| ADR-03 | Isolated worker runtime per active execution; CPython 3.13 native SPELL provider | Retain accepted runtime behavior rather than rewrite the language or mechanically restore old source. Native helper processes remain private implementation details. | E/G |
| ADR-04 | Compose static worker pool, one active Executor per worker container; K8s one Job/Pod per execution | Compose cannot create per-run containers itself. A fixed pool needs no Docker socket or new privileged management service. K8s Context has narrow Job RBAC. | E/G6/G7 |
| ADR-05 | SQLite per Context, OS-exclusive authority lock and FULL synchronous transactions | Reuse the audited single-authority pattern; no new database/broker service. Storage must support correct local locking/fsync. No shared multi-writer/HA claim. | D/J |
| ADR-06 | Unique active `(ContextID, ProcedureID)` reservation; Git revision is metadata, not lock identity | Renaming/reversion must not bypass a reservation; aliases stay explicit. Same ID in a different Context is allowed by default. | E |
| ADR-07 | Stable authenticated user identity, per-execution ownership and epoch; connection-bound control capability | A user's ownership of one run cannot affect another; stale sessions must not regain capability. | F |
| ADR-08 | One pending claim per execution; only current owner accepts | Deterministic bounded policy; no queue fairness surprises and no implicit takeover. | F |
| ADR-09 | Heartbeat/grace is control state, independent of execution; after grace fence mutation and freeze safely | Never kill a procedure merely because its controller disconnected; never infer administrative approval. | F/J |
| ADR-10 | HTTPS REST/JSON + WSS outside; mTLS versioned JSON RPC between services; framed DAP within worker | Same Context/worker application contract across deployments; no Unix socket across Pods. Preserve original loopback gRPC driver facade. Select/pin HTTP/WSS libraries during implementation with license/security checks. | C/G/J |
| ADR-11 | Context owns driver configuration, connection lifecycle and write-admission fencing; independent GENERIC DSS | Keep privileged network access out of worker/UI. Preserve intent/receipt no-replay behavior. Vendor GCS routes remain disabled unless validated. | G/H |
| ADR-12 | Separate v0.8 authority/state/ports; explicit offline migration and rollback to v0.7 | No in-place schema mutation or lost uncertainty holds. Release only after all gates and separate explicit publication approval. | J/L |

## Reviewable implementation boundary

The plugin gains a server package and a worker-provider adapter. Its Context
owns atomic reservation, supervisor state, owner/claim state, event journal,
blackboard and driver binding. Worker code owns only procedure runtime/debugger
and its private native subprocesses. The Listener authenticates and routes;
it cannot grant an execution owner token itself.

Compose's fixed worker pool is a concrete choice of addendum option A:
supervised OS subprocesses in constrained worker services. Worker service code
does not schedule across executions or own claims. Context capacity admission
reserves a worker slot and logical procedure in one transaction; launch follows
that durable intent. A lost or uncertain worker retains both reservations.
Worker reuse requires proven descendant quiescence and cleared temporary state;
failure fences the slot pending operator reconciliation. A heartbeat timeout
alone never proves termination. Trusted approved procedure code remains the
operational scope; untrusted Python sandboxing is not established by `-I`.

Kubernetes launch is part of the Context's existing supervision function,
not a new manager service. Context's ServiceAccount can create/read/delete
only labeled execution Jobs and read corresponding Pods in its namespace;
an admission policy or separate namespace per Context is needed to prevent
plain RBAC verbs from allowing arbitrary images, mounts or service accounts.
No workload receives cluster-admin or a Docker daemon socket.

## Consequences requiring validation

Static Compose workers limit concurrent capacity but avoid privileged dynamic
launch. Modern Context authorization must remain the single public authority
even though the native runtime internally still has its existing Listener and
Context helpers. Those private helpers cannot expose alternate browser/driver
control. Both worker transports must preserve fencing, cancellation and safe
pause. Kubernetes support cannot be accepted from YAML validation alone.
