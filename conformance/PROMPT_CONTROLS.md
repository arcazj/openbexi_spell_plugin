# Prompt control regression

The combined ranging candidate returned the second of two conflicting prompt
answers in `duplicate:boundary`. The original IPC client and context server
dispatch one worker thread per message, so the prompt mutex alone does not
preserve channel arrival order. The retained failure is in
`evidence/prompt_order_baseline.json`.

The native correction dispatches only one-way prompt answers directly
on each receiving channel, through the context's existing routing and the
executor's existing pending-answer guard. Those callbacks forward or signal;
they do not wait for an IPC response. Other messages and requests retain their
existing worker processing. No artificial response delay is introduced.

A separate child diagnostic found that CMD_ABORT left an unanswered prompt
waiting. The first candidate woke the prompt but deadlocked: the Python thread
held the GIL while waiting for the command mutex; the cancellation worker held
that mutex while notifying Python. The native debugger captured both stacks in
`evidence/prompt_abort_deadlock.json`. Its 24 answer-order and ten timed-prompt
checks passed, while child abort still failed; the complete attempted candidate
is retained in `evidence/prompt_controls_first_candidate.json`.

Cancellation now completes the scheduler abort and driver notification before
releasing the answer mutex and waking the procedure. It reports ownership so
the explicit command and resumed prompt do not dispatch duplicate aborts.
Cancellation is a no-op once an answer has won; an explicit abort then follows
the ordinary command path.
`evidence/child_modes_baseline.json` retains that failure and eight passing cases.

The recipes check exact original and composed preimages. Required validation is
24 conflicting-answer and 12 abort-at-prompt trials in independent executors,
all timed-prompt and child-mode controls, fresh reproducible native builds, and the complete combined
regression sequence. These repairs qualify no additional inventory rows by
themselves. Passing controls are recorded separately in `evidence/prompt_controls.json`;
the full combined checkpoint and release gates remain additional requirements.
