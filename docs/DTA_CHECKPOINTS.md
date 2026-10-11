# Native DTA checkpoint graphs

The original `Var` and `DataContainer` types now support the checkpoint codec's
pickle protocol. Their native implementations remain responsible for values,
validation, constraints and ownership. Restoration does not replace these types
with Python substitutes.

A Var records its value, inferred/explicit type, range, expected values, format,
confirmation flag, name and borrowed parent. Rebuilding uses the original
constructor with notifications suppressed for that operation; the previous
global notification setting is restored even if validation fails. The original
constructor infers internal LIST/DICT types from the default value instead of
accepting those internal names as explicit Type modifiers.

A container records its name, notification setting and ordered key/Var mapping.
Pickle memoization preserves Vars shared by multiple containers and procedure
frames. Parent bindings and names are restored independently from dictionary
insertion, so restore order does not change the original last-parent association.
The Python wrapper owns the native container; the native owner/parent pointers
remain borrowed and are detached during destruction. The reduction exposes a
dictionary copy, preserving the private native mapping's type invariant.

Native allocation avoids replaying subclass constructors. Standard instance
attributes and slots, including cycles, are restored with the native state.
The checkpoint identity now binds all production native port inputs and the
patch recipe, including these DTA hooks.

[Evidence](NATIVE_DTA_CHECKPOINT_QUALIFICATION.json) records twelve isolated
serialization cases and three integrated SIGKILL/fresh-process recoveries through
the original WS controller and frame manager. Cases cover native values and
constraints, shared identity, parent detachment, notification suppression/failure
restoration, subclass slots/cycles, 200 graph cleanup cycles, invalid state and
private mapping isolation. Procedures verify DTA aliases across callers and a
second checkpoint, active constraints after recovery, and no repeated subclass
constructor effects.

All earlier native suites and 38 continuation probes pass. All 143 original
library units still pass compilation/syntax checks. ASan/UBSan are enabled;
LeakSanitizer is disabled. Real executor/CIF notification and prompt handling,
Step-stage dispatch, external resource/dependency recovery and operational DSS
effects remain v0.2/integration gates. This milestone does not promote a release.

```powershell
docker build --progress=plain -f source_port/experiments/persistent-probe.Dockerfile --output type=local,dest=.qualification/v0.2/native-dta-checkpoint-02 .
python source_port/record_native.py --evidence .qualification/v0.2/native-dta-checkpoint-02 --dta-checkpoints
```
