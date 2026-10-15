# StartProc return value

LRM p89 specifies True after successful execution in blocking mode, or successful
loading in nonblocking mode. The return outcome and section 4.16.1.6 are the only
two requirements mapped by this proof. Other StartProc clauses remain separate.

The normalizer requires all nine native mode controls and eight failed-start
controls on the same installed runtime. Positive evidence covers both successful
return paths. Boundaries include immediate completion, manual children held
paused until RUN, and a later nonblocking child error that cannot revoke the
parent's earlier successful return. Failure evidence includes blocking child
ERROR/ABORTED and failed loads in all automatic/blocking combinations. Recovery
loads and finishes a valid child after a failed attempt in the same parent.

Failures use HandleError=False to observe the native exception directly. This
does not qualify interactive failure-policy choices, hidden GUI behavior,
library priorities, full StartProc, general modifiers or checkpoint recovery.
The preserved explicit-import profile applies. Sources, context inventory,
native events, actual parent-result files and terminal states must agree.
