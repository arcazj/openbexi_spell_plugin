# Prompt control regression

The combined ranging candidate returned the second of two conflicting prompt
answers in `duplicate:boundary`. The original IPC client and context server
dispatch one worker thread per message, so the prompt mutex alone does not
preserve channel arrival order. The retained failure is in
`evidence/prompt_order_baseline.json`.

The proposed native correction dispatches only one-way prompt answers directly
on each receiving channel, through the context's existing routing and the
executor's existing pending-answer guard. Those callbacks forward or signal;
they do not wait for an IPC response. Other messages and requests retain their
existing worker processing. No artificial response delay is introduced.

A separate child diagnostic found that CMD_ABORT left an unanswered prompt
waiting. The proposed correction cancels a pending prompt before forwarding the
explicit abort command. The existing cancellation path owns prompt cleanup and
scheduler notification; cancellation is a no-op once an answer has won.
`evidence/child_modes_baseline.json` retains that failure and eight passing cases.

The recipes check exact original and composed preimages. Required validation is
repeated conflicting answers in independent executors, all timed-prompt and
child-mode controls, fresh reproducible native builds, and the complete combined
regression sequence. These repairs qualify no additional inventory rows by
themselves; candidate build and runtime acceptance remain pending.
