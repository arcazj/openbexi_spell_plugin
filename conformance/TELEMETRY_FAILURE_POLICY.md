# Native GetTM failure actions

Language Reference 2.4.4 page 38 defines REPEAT, SKIP and ABORT after an acquisition
failure. Four native cases start with actual invalid-quality DSS packets and use
the original GetTM wrapper and native prompt/answer protocol.

The positive case repairs the DSS source before choosing REPEAT. The boundary
case repeats twice, with a repair only before the second answer. The failure
case chooses ABORT and must never write a return value. The recovery case chooses
SKIP, verifies the returned `None`, then resets the source and acquires 28.0.
The controller retains the actual choices, three held PROMPT samples per answer,
source packets, epochs, original RPC bytes, database state and emitted messages.

These are diagnostic cases. Their results require independent review and a
fresh composed regression before any whole-function requirement is promoted.
