# Prompt transition acknowledgement deadlock

The listener candidate built reproducibly, but its child lifecycle run failed
in `close-none`: the procedure remained at its parent prompt and native status
requests timed out. A separate debugger run reproduced the hang on the eleventh
independent executor. The child close call had not been reached.

The retained native stacks show the procedure thread in
`startPrompt -> scheduler.startPrompt -> notifyStatus -> waitAcknowledge` while
holding the prompt answer mutex. The channel receive thread is in the ordered
answer handler, waiting for that mutex. It cannot receive the acknowledgement
that would let prompt startup release the mutex.

`prompt_startup_patches.py` keeps answer locking limited to mailbox state. A
separate process-local transition mutex serializes startup and cancellation
without changing the native class layout. Cancellation claims its result before
calling the scheduler; the Python waiter resumes only after that transition
finishes. A timed default cannot replace an in-progress cancellation. Answer
arrival order remains the channel's arrival order.

The exact-method differential probe forces an early answer ahead of the startup
acknowledgement and a duplicate answer ahead of a cancellation acknowledgement.
The previous methods block acknowledgement processing in both cases; the
corrected methods allow it and preserve the selected answer or cancellation.
These controlled probes complement the retained native debugger evidence.

The diagnostic runner requires 40 early-answer trials, 14 child lifecycle
controls, nine mode controls, 12 abort-at-prompt trials, ten timed-prompt cases
and 24 conflicting-answer trials. It retains generated controllers, procedure
effects, logs, events, installed source identities and the exact library overlay.
The strict report verifies those 109 controls before source composition.

No inventory row is promoted by this infrastructure correction. A fresh pair
of native packages and the complete language regression sequence are required
before publishing a new coverage checkpoint or accepting a release.
