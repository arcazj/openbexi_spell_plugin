# Native incoming-message clear lifecycle

The first combined metadata/stream candidate completed its non-profiled handoff
soak but failed memory growth: 119,943,168 bytes against 67,108,864, with peak
1,540,661,248 bytes. Its 45.416-second soak preserved eight original processes
and every progress interval. Evidence: run `40419970647`, artifact `12697573366`,
ZIP SHA256 `50c2ab2f3f53fb2c6e5c06d4af2ba22ceaf60626d596b12465593a2d1fd0b7f4`.

The matching diagnostic run `40419970674`, artifact `12697732994`, ZIP SHA256
`f80c7e6d540ccb2acf9f7c29e8c6811d8a93fb17fd22d8049a987a30c30f92b1`, still
showed repeated native map-node copies in incoming dispatch. Context RSS rose
96.0 MiB during the soak; the two Executors rose 17.4/18.5 MiB. Sampled stacks
identify allocation sites, not a live-object leak. Both archives were SHA256 and
ZIP-integrity verified before inspection.

## Reproduced defect and correction

The real `SPELLipcIncomingBase::finish()` invokes `m_message.clear()` before
its message destructor. The earlier cache recycled at destruction only, so the
normal incoming-worker path had already freed its field nodes before recycling.
A compiled regression using the original message class reproduces this lifecycle:
400,000 allocations remain after 10,000 two-message copy/clear iterations in the
pre-fix candidate. The earlier destructor-only benchmark did not exercise it.

This correction recycles owned fields/metadata at the original `clear()` boundary,
then retains the original empty-properties, empty-ID/sender/receiver behavior.
Sequence, key, type and compression state remain exactly as before. The same
32-slot, 64-field, 64 KiB entry bounds and nonblocking ordinary-allocation fallback
apply. Repeated clear/destruction cannot recycle the same storage twice because
successful recycling transfers ownership out of the source message.

The regression fails before this patch and passes after it, with zero allocations
after warm-up. All 97 focused component checks pass locally under ASan/UBSan;
the separately collected regression also passes with the pinned lint/formatter.
The isolated memory-comparison builder fingerprint is updated to the exact
reviewed source; no other source guard or acceptance policy is changed.

The first combined terminal cohort also failed before its case matrix with late
BrokenPipe admission replies beyond the unchanged four-second deadline. That
failed archive (`12697867351`, SHA256
`1002916a6210ea4db5f5bf4ad46fe54a4b180b1f5111bb8841a2b5e9d4749d1f`)
is retained separately; this memory correction does not claim to fix its cause.

## Required hosted acceptance

Both non-profiled handoff and installed-IDE profiles must still pass 45 seconds,
eight original processes, advancing counters, 1,792 MiB peak and 64 MiB median
window growth inside 2 GiB/no-swap with zero pressure/OOM events. Sanitizers,
workload, authority decisions and all runtime deadlines remain unchanged.
No full-release gate or stable release is promoted by component measurements.
