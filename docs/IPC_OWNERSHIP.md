# Native IPC and process ownership

The original SPELL IPC classes now retain socket ownership across failed bind,
connect and accept setup; workers are started only after admission to their
owner's collector. Closing admission rejects unstarted work while shutdown joins
and destroys admitted workers. Client disconnect serializes owner calls, detaches
the channel before cancellation and fences sends against channel destruction.
Server channel publication and pending-request snapshots use the existing lock.

Process listeners use shared subscription records. Unregistering disables future
callbacks and drains callbacks already admitted before returning. A callback can
unregister itself without joining its own call. The listener object still belongs
to its caller: self-unregistration does not authorize deleting it during a callback.

## Independent evidence

[NATIVE_IPC_OWNERSHIP_QUALIFICATION.json](NATIVE_IPC_OWNERSHIP_QUALIFICATION.json)
records Build 36 and every source, patch, recipe and artifact hash. The independent
native probes require:

- Forty failed listener operations and 100 failed connections leave the Linux
  descriptor count unchanged.
- Shutdown waits for a blocked admitted worker and destroys it exactly once;
  a late worker remains unstarted and owned by its caller.
- Eight requests admitted by a real native IPC server return while its handlers
  remain blocked and two callers disconnect the client concurrently.
- External listener removal waits for an admitted callback; neither it nor a
  listener that removes itself receives a later callback.

All earlier native component, standalone/recovery and service-binding gates pass,
along with all 18 original listener/context/server/service lifecycle runs. These
checks ran under ASan/UBSan on the pinned Linux x86_64 CPython 3.13.15 environment.
Leak sanitizer and thread sanitizer were not enabled. The descriptor accounting
is a targeted leak check, not a claim of complete leak or race coverage.

## Remaining release work

This is a v0.2 milestone. An installable native runtime and its clean-environment
qualification, service reconnect/checkpoint semantics and remaining ownership
review still gate v0.2. The concurrent test covers established connections;
cancellation of an in-progress network connect is not established by this report.
