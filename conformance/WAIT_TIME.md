# Positional time waits

LRM page 56 accepts seconds, relative strings and relative TIME objects as
positional WaitFor arguments. Absolute strings and TIME objects wait until their
UTC target; a target already in the past completes without another countdown.

The native procedures execute all three literal two-second calls in Example 78.
They also exercise fractions, zero, future absolute strings and TIME objects,
and Example 79's original past timestamp. Monotonic clocks bound relative elapsed
time; independent UTC calculations bound absolute completion. The controller
observes native WAITING and FINISHED states and retains the executed source,
events, result files and logs.

Malformed values must raise a declared language exception, followed by a valid
wait in the same procedure. The report covers Examples 78–79 and sections 4.6.1
and 4.6.2 when all eight cases pass. Interrupt controls, telemetry waits and
interval progression remain separate requirements.
