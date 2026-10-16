These eight diagnostic procedures observe the remaining command interfaces on
the existing installed native runtime. They collect missing modifier names,
time tagging, ground release times and delay, load-only calls, grouped/blocked
lists, catalog sequences, a one-minute execution timeout, critical-command
confirmation disabled, and platform information passed to Send.

They retain native results or exceptions, original protobuf bytes, initial and
final simulator state, and the simulator's actual command-stage receipts. A True
return is only a baseline observation: it does not by itself prove scheduling,
frame grouping, metadata handling or any language requirement. There are no
coverage promotions in this baseline.

LRM 2.4.4 pages 49-55 distinguish on-board execution time (Time), ground release
time (ReleaseTime), and a GCS-held per-command delay (SendDelay). LoadOnly is
successful at loading, without execution. Group prevents uplink interleaving;
Block additionally uplinks all members in the same encoded frame. These must be
separate behavioral checks in a later candidate, including failure and recovery.

The current GENERIC catalog already defines SEQNAME and SEQ.DUPLICATE, and marks
TC.SIMULATOR.RESET critical. All commands here run only against fresh private
simulator instances created by the qualification controller.
