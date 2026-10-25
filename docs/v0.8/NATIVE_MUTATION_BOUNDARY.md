# Dev37 private Executor mutation boundary

This increment closes unsupported operations at the native Executor CIF before
their first side effect. It does not implement the corresponding owner actions.
The supported private owner commands remain RUN, STEP and main-Executor PAUSE;
public runtime control remains disabled.

`mutation_policy.H` defines the closed command/request inventory.
`mutation_gate.H` supplies a denial-only diagnostic. The reproduced
`SPELLserverCif::processMessage` rejects prompt answer/cancel and unsupported or
redirected commands before prompt wakeup or child redirection.
`processMessageCommand` independently rejects unsupported commands before
ABORT's `cancelPrompt`, CLOSE/BLOCK's `setClosing`, or mailbox insertion.
`processRequest` rejects every request outside the existing diagnostic-read
inventory before calling a setter/evaluator. It returns
`V08_NATIVE_MUTATION_DENIED` as a native error response.

The private Unix helper accepts denial diagnostics only from an authenticated,
original registered Executor and for that exact member. Field names, operation
labels and retained diagnostic cardinality are bounded. The helper always
replies DENY; neither ALLOW nor helper unavailability can enable the unsupported
operation. A diagnostic is never a grant, completion, barrier or authority
transfer. Original Context/Executor process identity checks remain required.

Candidate cleanup uses host process control instead of sending an unfenced
native CLOSE or management logout request. Uncertain reservations remain held;
whole-container termination must still be independently confirmed. The default
session path retains its existing cleanup behavior.

## Required proof

Local checks compile the production policy with C++17 and exercise closed
commands, prompt replies, direct setters, unknown operations and redirection.
They also cover diagnostic scope, extra fields, capacity, duplicate DENY replies
and candidate/default cleanup. Frozen native source reproduction checks that
the guards precede the actual side-effect call sites. This is not a full native
compilation or runtime result.

The hosted native Context C probe sends 13 one-way operations and six direct
setter requests through the original bridge after the first authorized STEP.
Each must produce a denial from the exact original native Executor; direct
requests must return the native denial error. FIRST must remain 1, SECOND must
remain absent, the SCRIPT/variable-expression marker must not exist, and the
Executor must remain PAUSED. The existing first/second STEP ownership-fencing
oracle then continues. All original family, stale RUN and same-owner
RUN/PAUSE/RUN tests remain mandatory.

Hosted dev37 compilation and execution are pending. In particular, this paused
fixture does not complete pending-prompt compatibility or positive owner ABORT,
CLOSE, answer, setter, or debugger feature qualification. Native Context GUI
management, controller-client roster messages, remaining queue dispositions,
full-family barriers, new-owner runtime identity and observer read scope remain
in `NATIVE_MUTATION_MATRIX.md`. Full v0.8 acceptance remains unqualified.
