# Child mode diagnostics

LRM pp86 and 88-89 require blocking StartProc to wait for the child and fail
when that child ends in ERROR or ABORTED. A nonblocking call returns after a
successful launch; a later child error does not invalidate that return. Manual
mode leaves the child paused until the client explicitly sends RUN.

Nine native cases observe those distinctions using actual parent/child status,
context inventory, open modes, IPC prompts and procedure-written files. Held
children prevent a fast successful child from hiding an ordering defect. Manual
cases inspect the paused child repeatedly before sending RUN. A recovery case
rejects an invalid identifier before starting a valid child in the same parent.

Run `run_child_modes.py --image <immutable-id>` after the current integration
sequence. The probe retains installed provenance, exact procedure sources,
observations, native logs and cleanup failures. It replaces no native function,
registry entry or driver result. These are diagnostics only: no inventory row,
whole StartProc contract, hidden GUI behavior or release is qualified by them.
