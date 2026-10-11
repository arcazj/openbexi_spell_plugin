# Context login, status and pending-service ownership

The context now routes reconnect completion through the executor model's virtual
owner callback. Service models notify the service manager; ordinary procedure
models notify the executor manager. The logged-in flag is published after login
metadata and process attachment, and the shared login/process flags are atomic.

Pending services have one owning map. Successful login transfers ownership to
the active map; failed login retires the model for cleanup by its owner, outside
the manager lock. Cleanup cancels and joins outstanding login monitors. The
watchdog checks active and pending models under the manager lock, so it cannot
start another instance while a reconnect is pending. The start path repeats that
check under its own admission lock.

Status waits arm their event before reading the model and use one monotonic
deadline. Unrelated notifications cannot extend the timeout. Process-finish waits
also arm before checking state. A disconnected IPC client rejects subsequent
one-way messages and requests before accessing its detached channel.

## Evidence

[NATIVE_CONTEXT_OWNERSHIP_QUALIFICATION.json](NATIVE_CONTEXT_OWNERSHIP_QUALIFICATION.json)
records Build 39 and its exact inputs and artifacts. All earlier native,
standalone/recovery, binding and ownership gates pass. Eight context tests cover
19 complete listener/context/server/service lifecycle runs.

The added scenario registers a real service definition while its persisted
process ID points to a test-owned live process that never logs in. Across multiple
watchdog intervals, the original context retains that pending reconnect without
executing the service definition. Context shutdown cancels the monitor and exits
normally, without a double deletion or signalling the unattached test process.
The test then terminates its own process.

An independent context-side component probe delivers original status notifications
and checks an already-reached state, a new transition and a timeout amid unrelated
notifications. It also exercises login-worker success, timeout and cancellation
through the virtual callback. Its short timeout is a test constructor argument;
the production login-monitor default remains 120 seconds. The IPC probe also
checks sends after concurrent shutdown. ASan/UBSan report no failure in these
checks; leak/thread sanitizer qualification remains separate.

## Remaining work

This milestone establishes pending-model ownership and login/status behavior.
It does not qualify an existing native service reconnecting after a live context
crash. The CIF retry path, socket inheritance and service checkpoint semantics
remain under review before final native foundation acceptance. The installed
0.2.0a2 diagnostic wheel is the preceding package snapshot; these changes will
enter the next qualified native artifact.
