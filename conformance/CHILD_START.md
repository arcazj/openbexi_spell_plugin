# Failed child startup and recovery

LRM pp88–89 distinguish a failed launch from a child error after a successful
nonblocking launch. StartProc returns True only after successful execution in
blocking mode or successful loading in nonblocking mode.

Eight diagnostic cases attempt an absent procedure under each combination of
Automatic and Blocking. Four require DriverException and no remaining child;
four then load a real child in the same parent and require True and FINISHED.
Manual recovery observes the paused child three times before sending RUN. Its
nonblocking parent must already have returned; its blocking parent must wait.

Run `run_child_start.py --image <immutable-id>`. These diagnostics use
HandleError=False to observe native failure directly. They do not qualify the
interactive error policy, hidden GUI behavior, library priorities, arguments,
whole StartProc contract or any inventory row by themselves. Runtime evidence
is still pending.
