# Original WS frame and data controllers

The original `SPELLwsFrame`, `SPELLwsStaticData` and `SPELLwsDynamicData` now link
and run on GIL-enabled CPython 3.13.14. Static data retains code storage. Dynamic
data uses an owned modern snapshot instead of removed try-block, fast-local and
operand-stack fields. A frame controller owns its frame and its data controllers;
destruction releases them, and cleanup removes its associated files.

Recovery creates an inspection view with the saved locals, cells, line and cursor.
Execution uses the shared continuation engine, which lets CPython allocate a live
frame before restoring its slots. The existing trace callback receives CALL and
LINE only after restoration, followed by real nested events. Rebinding replaces
the inspection view with that live frame. The existing callback is restored on
success or failure, and can inspect or edit live locals and take another snapshot.

The original recovery experiments and this WS integration now compile the same
`native/continuation.cpp`; there is no second recovery implementation. Its private
ABI is restricted to CPython 3.13.14 with the GIL. These are logical continuations;
the original physical caller chain is not reconstructed.

Single-frame persistence uses the qualified cloudpickle 3.1.2 graph codec through
the original WS storage. It checks source/runtime/codec identity and record/payload
integrity before deserializing. A temporary file is fully written, closed and
flushed before atomic replacement, followed by directory sync. A failed encode
leaves the previous checkpoint intact. These are application-owned checkpoint
files, not an untrusted import format. Arbitrary external dependencies and native
DTA serialization remain open integration requirements.

[Evidence](NATIVE_WS_FRAMES_QUALIFICATION.json) records 12 WS frame/data checks:
namespace sharing, inspection, live rebinding/edits, saved iterators, exception
handlers/finally, failed writes, invalid state, source mismatch, corruption,
200 ownership cycles, cleanup and fresh-process recovery. All earlier native
suites pass. The shared engine passes 14 in-memory, 13 persistent and 11 logical
caller checks. ASan/UBSan are enabled; LeakSanitizer remains disabled.

The original library inventory is 142/143 passing compilation/syntax checks.
`SPELLwsWarmStartImpl` still needs its whole-stack controller port and original
frame-manager recovery integration. Per-frame persistence does not establish
shared object identity across independently serialized caller frames. The full
executor, context and CIF also remain v0.2 release gates.

```powershell
docker build --progress=plain -f source_port/experiments/persistent-probe.Dockerfile --output type=local,dest=.qualification/v0.2/native-ws-frames-01 .
python source_port/record_native.py --evidence .qualification/v0.2/native-ws-frames-01 --ws-frames
```
