The first combined wait/PROC build stopped at the context gate with three
qualification failures. Its complete native build archive and logs are retained
by `distribution/evidence/context-harness-review.json`.

The first client connected before the listener opened its socket. The qualifier
now observes both listening socket inodes owned by that process, with a bounded
deadline, before launching the original protocol client. It does not open probe
connections or assume that a fixed sleep means readiness.

The next procedure completed normally. Its listener reused the previous case's
second-resolution log filename, so the old comparison of newly created filenames
excluded its successful shutdown. Each case now owns a separate log directory.
The shutdown, forced-kill and sanitizer assertions remain in place.

The final-output assertion observed concurrent IPC callback workers. These can
run in a different order from their messages' socket arrival. A controlled
200 ms callback delay produced three false failures with the asynchronous
observer and three passes with the ordered observer, on the exact same native
binaries. The retained final-repeat socket traces in both variants show Display
before completion. The qualifier now observes messages on its receive thread
and retains the original protocol acknowledgements. Production IPC dispatch is
unchanged.

The corrected observers also passed all eight focused shared-data, child,
scheduler and controller scenarios without the injected delay. Two fresh builds
and the complete composed regression sequence remain necessary for acceptance.
