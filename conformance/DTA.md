# Native data-container qualification

The DTA suite executes the original `DataContainer`, `Var` and `TIME` implementations
inside the original native executor. Its independent controller answers actual CIF
IPC prompts and checks the resulting ITEM messages. No container or client service
is replaced with a test double.

The frozen native-only development candidate is
`sha256:90f76095d9eed8117d5dd4657a7c338e4e17521278c6f3e0516bbe746e46e55a`
(`openbexi-spell-host:v05-dta-time-context-development`). All 64 DTA checks pass in
`.qualification/v0.5/dta/1fc53eb4da8346adb2ffc8ef0f0e05b1/`.

The final combined DTA/TIME/OBS development image is
`sha256:3434d53d2963c25ca43fba94c87bc106829eb6203c12aaa9ae51e757496830e0`
(`openbexi-spell-dss:v05-dta-time-obs-development`). Its 64 DTA checks pass in
`.qualification/v0.5/dta/9d18adef536646f1828c169016d80a90/`; the promotable report is
`conformance/evidence/dta.json`. It attaches 12 inventory rows to four independent
dimensions each. Additional checks deliberately have no inventory allocation.
This is a conformance increment, not acceptance of the full v0.5 or v0.6 gate.

## Behavior covered

- All six native variable types: explicit type, exact returned Python type,
  empty/zero/numeric/Unicode boundaries, invalid assignment, real user correction
  and subsequent use of the same container.
- Native mapping construction, methods, ordered keys, iteration and invalid calls.
- Declaration consistency, inclusive ranges, Expected selection, uninitialized and
  missing variables, type inference and confirmation before each read.
- Decimal/hexadecimal/binary/octal ITEM values, including zero and positive/negative
  integers beyond 32 bits; deferred format/type inference rejects invalid values
  before mutating the variable.
- Exact ITEM progress/success/failure sequences and values for read/write/correction.
- Literal prompt values, apostrophes and colons in strings, and rejection of
  expression-shaped input followed by a valid answer. Expected choices return the
  existing typed value by index instead of evaluating its display representation.
- Absolute epoch zero, a pre-epoch fractional value, leap dates, microseconds,
  negative fractional relative values, ranges spanning zero and TIME Expected lists.

The TIME notification oracle parses native wire text independently into Python
datetime or integer microseconds. It compares meaning rather than requiring the
Python class's default pretty-print format.

## Checked source corrections

`source_port/dta_native_patches.py` checks both the complete original archive member
and the complete established CPython port before patching `SPELLdtaVariable.C`.
It enforces the manual's Range/Expected and STRING-range constraints, obtains Type
before converting TIME constraints, validates formats, preserves large integer
formatting, and uses owned Python references and direct literal/constructor calls.

`source_port/dta_time_patches.py` similarly checks `SPELLtime.C` and
`SPELLpythonHelper.C`. The original native unsigned-seconds ABI is retained. Signed
interpretation at comparison/formatting, normalized negative fractional conversion,
and an absolute-epoch guard correct the values exercised here. Absolute output
uses UTC. This does not claim a complete rewrite or qualification of every native
TIME arithmetic operator.

`conformance/dta_native_build.py` applies these recipes together with the retained
DATA-context, UI and FLOW recipes, then uses the recorded original build graph to
compile changed units and relink the executor library, Context and Listener.
All three artifacts are installed and their hashes are checked by the controller.
For every changed unit, the complete original/ported/patched source, recipes, compile/link commands, object
hashes, binaries and manifest are retained at `/opt/dta-native-patch` in the image,
and locally in
`.qualification/v0.5/dta-native/35ad737e209f4af09d85e0bd3d45dfee/native-patch/`.
Reports retain both raw input hashes and LF-normalized Python recipe hashes.

The source/object base used for this retained rebuild is
`openbexi-spell-native:v06-diagnostic-6a340659e519`, exact image
`7c3eb7b7b33bb49690a35c51cb0a096c8c30bc770f9994eb54563d4aea4725cb`.
The runtime parent is the prior integrated DATA/UI/FLOW image
`0eadf2e3b1e961a5e403b79b665e70b22c649179ccde40e86ffceae2ee7559ec`.

## Retained failures and regressions

The same current declaration/format oracles on the prior accepted native image
`0eadf2e3b1e961a5e403b79b665e70b22c649179ccde40e86ffceae2ee7559ec`
fail five of twelve checks in
`.qualification/v0.5/dta/60c391dfb36544eeb215965fedcf72b7/`:
invalid combined constraints, large-number formatting, and invalid initial values
with a deferred format. Additional raw baseline failures preserve the apostrophe
prompt loop (`7749ebdad16041a991dc1c2baea0c6f9`), epoch conversion
(`3989183aefdc414b937e46c6544bef39`) and Expected-string prompt loop
(`c9be281b0e9848599e1f1451914d0943`) under the same DTA evidence directory.

Earlier unsuccessful development runs remain intact: an artifact-installation
attestation rejection (`c700c1ddde5a4e2fbcc21004068f2eca`), an overly strict TIME
text oracle (`85ff7fc64374485c8a7d414e30f70962`), and a concurrent unrelated recipe
change detected by the input guard (`7f0ad2a8fd0840e897ae4cf8958e95a9`). None is
promoted as passing evidence.

Regression results on the frozen native-only candidate:

| Suite | Passing checks | Evidence directory under `.qualification/v0.5/` |
| --- | ---: | --- |
| TIME | 168 | `time/1bb513b11d8548db98276a59267238b0` |
| UI | 62 | `ui/df66ac79e684475ca1515027c2ddeeee` |
| DATA | 24 | `data/03e4400129ef49838d69b02a4490f930` |
| FLOW | 36 | `flow/7c008564cbee4a238aaa82a04663fb18` |

Combined-image regression results:

| Suite | Passing checks | Evidence directory under `.qualification/v0.5/` |
| --- | ---: | --- |
| TIME | 168 | `time/a53f8b254a4f449180b39793009e7ea1` |
| UI | 62 | `ui/d2f50322346045068b460da43eddb961` |
| DATA | 24 | `data/596cbe1051154293b99dd1b4c2c9bca2` |
| FILES | 36 | `files/45ce85cd4ccd421b876bbe7b9034f526` |
| DATA race | 4 | `data-race/6ffb973df3cd40189169685cf3f7d752` |
| FLOW | 36 | `flow/72889e6aa8fd482a8e3e1e1adfb90c80` |

## Scope still open

The suite does not qualify predefined ARGS/IVARS client editing, all Var behavior
as a whole, the full data-container section, SCDB/GDB/MMD or user-database
persistence, PROC metadata, shared-data Scope semantics across every function,
or external ranging/resource/display services. These need their own actual native
and, where applicable, DSS evidence. The singular `ClearSharedDataScope` spelling
conflict remains explicit; no speculative compatibility alias was introduced.

The follow-up `run_dta_edit.py` diagnostic retains a concrete ARGS/IVARS blocker
at `.qualification/v0.5/dta-edit/05a9511ad6af4d929a4795397f1e88dc/`. Both objects
are actual `libSPELL_DTA_v3.DataContainer` instances, accessed through the explicit
`spell.runtime` imports required by this port. The original native
`SPELLrequestProcessor::isDataContainer` still compares `tp_name` with
`spell.lib.adapter.data.DataContainer`. Consequently `REQ_GET_DICTIONARY` returns
plain representation text, and `REQ_UPD_DICTIONARY` acknowledges both valid and
invalid edits without applying them. Both containers retain their original values,
and the resumed procedure correctly fails its edited-value assertion. All eight
diagnostic checks are failed and have no inventory allocation. The retained
`7de11329c4e1406391da401fa0fc8dc7` probe first isolated the typed-field mismatch;
`b12672d4155345009a93707d9b6978d0` was an earlier fixture error lacking explicit
runtime imports, not evidence of a native regression.

Repairing that IPC branch also requires qualification of malformed field counts,
conversion errors, Python reference ownership and notification restoration; it is
kept separate from this frozen candidate rather than declaring ARGS/IVARS complete.

Run the suite with:

```powershell
.venv/Scripts/python.exe -X utf8 conformance/run_dta.py --image sha256:3434d53d2963c25ca43fba94c87bc106829eb6203c12aaa9ae51e757496830e0
```
