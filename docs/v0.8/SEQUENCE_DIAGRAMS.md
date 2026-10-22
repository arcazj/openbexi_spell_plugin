# Proposed authority and lifecycle sequences

All sequences are `TARGET-v0.8`, pending Gate B review. They describe required
ordering and failure behavior; no v0.8 endpoint is implemented yet.

## Per-execution consent; A and C unchanged

```mermaid
sequenceDiagram
    participant U1 as U1 (owns A, B, C)
    participant U2 as U2 (observes B)
    participant L as Listener
    participant X as Context authority
    participant DB as Context SQLite
    U2->>L: Request control of B (session + idempotency key)
    L->>X: Authenticated scoped identity; claim B
    X->>DB: Validate requester; persist pending claim at B epoch 7
    DB-->>X: Commit claim; owner remains U1
    X-->>L: CONTROL_CLAIM_REQUESTED (no capability)
    L-->>U1: Nonblocking Accept / Reject notification
    L-->>U2: Pending; still read-only
    U1->>L: Accept claim B, epoch 7, current capability
    L->>X: Authenticated owner acceptance
    X->>DB: CAS (B, U1, 7) to (B, U2, 8); close claim; append events
    DB-->>X: Atomic commit; A and C unchanged
    X-->>L: Claim accepted and owner changed
    L-->>U2: Fresh B capability on authenticated connection
    L-->>U1: B observer; retains A and C
    U1->>L: Delayed PAUSE B using epoch 7
    L->>X: Forward authenticated command
    X-->>L: Reject stale ownership/capability
    L-->>U1: Conflict; no worker mutation
```

Reject/expiry/cancel closes only the pending claim, leaving owner and epoch
unchanged. Concurrent claim/accept requests serialize under the same Context
authority; repeated idempotent acceptance cannot increment the epoch twice.

## Duplicate-start race and worker launch

```mermaid
sequenceDiagram
    participant A as Start request A
    participant B as Concurrent start B
    participant X as Context
    participant DB as Durable reservations
    participant W as Bound worker
    A->>X: Start (ContextID, ProcedureID, Git SHA)
    B->>X: Same logical procedure, different request
    X->>DB: BEGIN IMMEDIATE; reserve logical ID + worker slot
    DB-->>X: Commit launch intent, ExecutionID, owner, fence, generation
    X->>DB: Check competing logical reservation
    DB-->>X: Existing active/uncertain reservation
    X-->>B: Conflict; no second worker
    X->>W: Idempotent launch with immutable inventory and generation
    W-->>X: Confirm same generation / paused runtime and PID
    X->>DB: Persist launch acknowledgement
    X-->>A: Execution identity and state
```

An ambiguous launch reply keeps the original reservation and worker slot.
Health loss does not permit a replacement. Different ProcedureIDs and different
Contexts can be admitted concurrently within configured capacity.

## Driver write vs transfer

```mermaid
sequenceDiagram
    participant W as Worker driver relay
    participant X as Context authority
    participant J as Intent/receipt journal
    participant D as Independent DSS
    participant U as Current owner accepting transfer
    W->>X: Effect request (execution + generation + correlation)
    X->>X: Serialize admission; validate live owner epoch and procedure fence
    alt admission linearizes before transfer
        X->>J: Durably reserve/write intent under admitted authority
        X->>D: Send command once after final live-authority check
        U->>X: Accept transfer with valid old owner proof
        X->>X: Commit new owner/epoch; invalidate old capability
        D-->>X: Actual receipt or uncertain timeout
        X->>J: Retain actual outcome linked to admitted request/epoch
        X-->>W: Recorded response or uncertainty hold; never replay
    else transfer linearizes first
        U->>X: Accept transfer
        X->>X: Commit new owner/epoch
        X-->>W: Reject old-epoch effect before intent or external write
    end
```

The Context attaches authority; worker payloads cannot select their own owner
epoch. Every subsequent external write revalidates current authority. A transfer
does not reverse a command already sent under valid prior authority. An unknown
outcome remains an uncertainty hold and is never converted into a successful
receipt or a retry.

## Listener vs Context failure

```mermaid
sequenceDiagram
    participant UI as Browser / client
    participant L as Listener
    participant X as Independent Context
    participant W as Worker
    participant DB as Durable authority
    L-xL: Listener process stops
    W->>X: Existing runtime events / checked driver requests
    X->>DB: Continue durable event/effect accounting
    Note over X,W: Context and worker lifetimes do not depend on Listener process
    UI->>L: Reconnect after Listener restart
    L->>X: Authenticated snapshot + cursor replay
    X-->>UI: State / owner / explicit replay gap if needed
    X-xX: Context process crashes
    Note over W,DB: No heartbeat-based replacement or uncertain-effect replay
    X->>DB: Restart; obtain exclusive lock; advance epochs; revoke capabilities
    X->>DB: Close pending claims; retain active/uncertain reservations
    X-->>UI: RECOVERY_REQUIRED; explicit shutdown/effect reconciliation needed
```

Listener outage does not waive controller grace/identity rules. Context restart
cannot grant old browser capabilities authority or treat a partitioned worker
as terminated. Final recovery tests must prove these properties with real
process/Pod failures and retained audit ordering.
