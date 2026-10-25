# Step 1: original-native prompt selection candidate

This candidate connects the private owner-bound prompt protocol to the exact
source-derived `SPELLserverCif` prompt lifecycle. It does not complete Step 1,
make public execution available, approve ownership transfer, prove procedure or
driver-effect settlement, or promote any full v0.8 release gate.

## Original synchronization retained

`prompt_patch.py` checks the exact header/translation-unit preimages after the
existing native admission composition. It preserves the original answer mutex,
condition variable, cancellation transition mutex, GIL-release behavior,
scheduler timeout/default conversion and cancellation-before-wakeup ordering.

An explicitly enabled private native profile registers a fresh kernel-generated
prompt UUID and the actual bounded definition before publishing the prompt.
The agent derives its digest and binds the original root/child admission and
worker identity. The owner reply remains bound to that definition, member,
connection, epoch, capability, action and answer digest. Plaintext answer values
are not copied into SQLite audit or idempotency rows.

Immediately before native answer selection, the original receive path checks
pending identity, performs the final certificate-authenticated Context check
without holding the answer mutex, then reacquires the mutex and rechecks the
same generation. Timeout, cancellation or a newer prompt can win during that
RPC; a late reply cannot overwrite their selection. Cancellation similarly
rechecks the generation inside the original transition/answer-lock ordering.
Replies cannot redirect through ParentId. Missing or mismatched identity,
malformed answers, stale ownership and uncertain responses never authorize a
retry or wake a pending prompt.

Selected answer, cancellation, default and unknown outcomes are reported once
through the original native PID-bound Unix channel. These observations never
release reservations or spent workers. A close acknowledgment is not procedure
termination, background/child closure or proof of external-effect settlement.
The default profile continues to reject native answer/cancel messages.

## Qualification boundaries

The local C++ fixture compiles actual patched method bodies under address and
undefined-behavior sanitizers; its surrounding class, transport and Python
interfaces are controlled fixtures. It covers early answers, duplicate/foreign
replies, default winning during authorization, old cancellation versus a new
prompt, registration failure and cancellation completing before wakeup. It is
not the complete native program.

The original native child-gate hosted qualification additionally builds the full
candidate and runs three isolated contexts:

* Root ALPHA answer, independently admitted child NUM answer, a second root
  prompt, original numeric default, exact results and normal completion.
* Owner-bound cancellation with actual ABORTED status and no following effect.
* Owner disconnection after forwarding but before the actual native selection
  check; the final authority must reject, the following effect must remain
  absent, and original participants and uncertain holds must be retained.

Each prompt cohort first exercises an actual identity-less native reply denial.
Context-scope, copied owner, changed definition, wrong member and closed prompt
checks remain mandatory. Success requires matching native callbacks and durable
rows, not merely a worker-supplied success flag.

Host/container cleanup in these fixtures remains independent qualification
cleanup, NOT the operational cleanup proof required by Step 1. Positive
ABORT/CLOSE, complete normal/error terminal-effect outcomes, comprehensive
startup reliability, and safe cleanup remain unfinished. The historical LOADED
timeout is not claimed fixed. Steps 2–5 remain gated in the approved order.
