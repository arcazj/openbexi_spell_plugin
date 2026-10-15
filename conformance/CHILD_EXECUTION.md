# Child execution modes

The original LRM p88 supports three bounded requirements here: Example 156
(nonblocking), Example 158 (manual), and section 4.16.1.4 (automatic/manual).
The shared native verifier requires all nine execution controls and eight
failed-load/recovery controls on the same installed runtime.

Manual children remain PAUSED through three observations before explicit RUN.
Parent progress is checked while the child waits at a prompt. A later child error
preserves the nonblocking parent's successful return. Missing loads fail in all
four automatic/blocking combinations; a subsequent valid child succeeds in the
same parent. Each requirement maps its own positive, boundary, failure and
recovery observations.

The whole Blocking section remains open because it also specifies interactive
error handling. Hidden GUI behavior, library priorities, global modifiers and
checkpoint recovery require separate evidence.
