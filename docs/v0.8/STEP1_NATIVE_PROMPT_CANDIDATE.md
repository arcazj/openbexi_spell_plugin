# Step 1: original native prompt selection candidate

This change continues Step 1 only, based on the complete source tree of
`9ff010dcec3169b62ff0fd4ef69c0444d923a11f`. The companion IDE remains pinned
to `dd06fe91d9da9cad828ff659adced0e3be80816d`. No ownership transfer, stable
release, worker reuse, reservation reclamation or production migration is enabled.

## Implemented private chain

The Context's explicit `owner-reply-candidate` profile registers original prompts
and admits exactly one owner-authorized reply per prompt. The original worker
grant and pinned member registration remain mandatory. A distinct prompt grant
binds prompt definition, native member, execution, owner connection/epoch,
action, answer digest and expiration. Raw answers remain in bounded transient
memory, never in audit or SQLite response records. Uncertain delivery is never
replayed.

The source-derived native CIF is changed only after all frozen source-port
recipes have run. It retains the original condition variable, prompt transition
lock, cancellation scheduler and default-conversion behavior. Prompt registration
sends the actual native definition to the PID-authenticated agent outside the
answer mutex, before publishing the prompt. The agent computes its canonical
digest rather than trusting a caller-proposed digest.

For `MSG_ANSWER`/`MSG_CANCEL`, the default native mutation denial remains in force.
Only an explicitly selected `native_prompt_protocol` worker may enable the
private `OPENBEXI_V08_PROMPTS=owner-bound/1` native profile. The inherited flag is
removed otherwise. Such messages still require exact one-way type, ProcId,
prompt and reply UUIDs, action-specific fields and no child redirection.

Final Context authorization runs under the original native answer lock before
selection or wakeup. No native IPC round trip is made by the authorization
handler: it contacts only the original Context authority. The original steady
clock deadline is checked both before and after that bounded RPC. Thus an answer
whose authorization completes after the deadline cannot replace the native
timed default. A consumed-but-late or lost acknowledgment is retained as
uncertain, never replay permission. Internal scheduler cancellation is reported
as UNKNOWN, not forged owner cancellation.

The original native scheduler performs answer/cancel/timeout selection. One
safety-only close report records that selection without claiming procedure or
external-effect completion.

## Executable verification scopes

`test_native_prompt_boundary.py` composes the checked original SPELL archive,
applies the production candidate patches, extracts the original CIF start,
answer, cancellation and wait methods, and compiles those methods together with
the actual prompt gate/state headers using ASan/UBSan. Only the transport, GIL,
message substrate and scheduler are controlled doubles. It calls the real worker
relay and Context/SQLite over actual mTLS. Positive/negative cases include
answer, cancellation, timeout, duplicate and opposite replies, scope/argument/type
substitution, disconnect, registration failure, response loss and deadline
expiry while authorization is in flight. This is not the complete interpreter.

The existing `--native-child-gate` hosted qualification also builds the actual
source-derived native programs and launches three additional isolated Context
cohorts: owner answer, owner cancellation, and native timed default. Each requires
an actual prompt registration, native selection callback, durable matching
receipt, expected terminal state and whole-container termination. Original
family/owner/denial regressions remain in the same job. All fixture outcomes keep
execution holds and spent slots; this is not production safe-reuse acceptance.

## Remaining mandatory Step 1 work

Hosted native qualification of this exact source must pass before treating the
prompt integration as qualified. Positive owner-bound ABORT/CLOSE, complete
normal/error termination and safe descendant/driver cleanup remain subsequent
Step 1 tasks. The historical LOADED startup failure's root cause is not claimed
fixed. All eleven full release gates remain unchanged. Steps 2–5 remain blocked
until their prerequisites are actually satisfied.
