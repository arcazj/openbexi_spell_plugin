# Interrupted waits

LRM 2.4.4 pp57-58 requires INTERRUPT to hold a time or telemetry wait. STEP
resumes the existing condition, while SKIP cancels it. Either path ends in the
manual's PAUSE state, represented as PAUSED on the native IPC wire. Resuming a
time wait retains its original target, including a deadline reached while the
wait was interrupted.

The controller drives actual CMD_INTERRUPT, CMD_STEP and CMD_SKIP messages.
It observes the native WAITING, INTERRUPTED and PAUSED states and checks that
the statement after WaitFor remains unexecuted until a subsequent CMD_RUN.
Relative and absolute boundary cases hold the interrupt beyond the original
deadline. Telemetry cases use the installed driver, original protobuf messages
and the real local DSS; a controlled simulator tick satisfies the condition.
Neither telemetry acquisition nor countdown notifications may advance while
the interrupted state is held. Every case includes a subsequent successful wait.
Failure cases catch an invalid duration and also issue a duplicate interrupt.

The suite has 24 cases: three condition types, two control actions and four
dimensions. Its strict report requires all leaves and the exact committed
scheduler correction in the freshly installed package. See the
[current checkpoint](../docs/LANGUAGE_CHECKPOINT.json) for acceptance status.
The full WaitFor function, interval progression and other modifiers require
separate qualification.

The native Executor_Wait binding returns True for SCH_ABORTED (the UI SKIP
path); only SCH_TIMEOUT returns False. This is distinct from choosing CANCEL
in a failure-policy prompt. The tests preserve that existing return behavior;
the manual control requirement concerns cancellation and the final paused state.
