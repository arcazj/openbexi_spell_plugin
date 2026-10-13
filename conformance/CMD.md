# Native command checkpoint

This is a bounded development checkpoint on original SPELL 2.6.10 ported to
CPython 3.13 and the original-schema driver, with real binary DSS command effects.
It does not establish full v0.5 or v0.6 acceptance.

The harness observes the original native executor, TC items, BuildTC and Send.
Independent assertions check exact expected command names and values, simulator
state, five ordered binary stages per successful command, one ingress delivery
per stage, failure receipts, prompts and absence of effects. It never replaces
a language function, registry, driver response or simulator command outcome.
Each check records its source, dimension, expected prompts and retained RPC bytes.

## Demonstrated corrections

The frozen3434 baseline exposed a discarded name-to-item list in Send, lowercase
`group` leaking into modifier configuration, and IndexError on malformed TC
arguments. A subsequent native probe established that empty groups returned
success and a known failed RELEASE receipt bypassed OnFailure while reporting
execution success. Checked `cmd_patches.py` changes only original tchelper.py and
tc_item.py, retaining exact preimages, upstream notices and patched files.
The explicit lowercase structural keyword is removed from helper configuration;
the capitalized Group modifier remains distinct. Malformed shapes reject before
sending. A known false driver result enters the original failure-action path.

The driver previously implemented `_sendBlock` by sequential ordinary commands.
It now rejects that unsupported atomic operation before any effect, including
when a TC item carries Block=True. That rejection does not qualify block support.

## Supported slice and limits

LRM pp47?55 supplies the independent expected behavior. The selected rows cover
simple TC construction, Send by name or item, the demonstrated two/three-element
argument syntax, real decimal/hex/octal/binary argument encoding, ordinary
sequential lists and explicit confirmation. The example catalog replaces only
placeholder spacecraft definitions. Numeric/RAW values are compared with exact
catalog boundaries and encoded TC evidence. ValueType casting remains open;
these syntax checks do not claim every argument type or calibration profile.

The sequential failure test puts the real DSS in SAFE mode through a real
SET_MODE command. CMD2 succeeds, CMD1 receives RELEASE/FAILED, and CMD3 is never
sent. Native OnFailure offers ABORT/RESEND/SKIP/CANCEL. Explicit cancellation
retains the first effect and failure receipts; returning to NOMINAL and a new
send establishes recovery without replay. Confirmation OK sends once; CANCEL
sends nothing. PromptFailure=False selects automatic failure handling, consistent
with the source and existing COMMON policy distinction from PromptUser.

Full BuildTC/Send, cross-family args, unrestricted TIME-valued arguments,
ValueType casts, critical confirmation, GCS sequences, Time/ReleaseTime/SendDelay,
LoadOnly, arbitrary addInfo, Group critical sections, Block single-frame sends,
combined telemetry/limit adjustment and the one-minute timeout example remain
open. Short bounded timeouts are not evidence for that literal one-minute row.
Unknown-effect fencing is tested separately through the existing real native
DSS integration suite; command receipts never imply mission-driver acceptance.

## Reproduction and provenance

`cmd.Dockerfile` derives only from the preserved3434 development image and
retains recipe, originals and patched hashes at `/opt/cmd-conformance-patch`.
The controller validates those against the actually installed files, as well as
the inherited DTA and OBS manifests. The runner binds exact image, all fixture
sources, manual/inventory, oracles, recipes and proxy input hashes. Outputs are
LF JSON and all baseline failures remain in the ignored qualification directory.

```powershell
docker build --network none -f conformance/cmd.Dockerfile -t openbexi-spell-dss:v05-cmd-02 .
python conformance/run_cmd.py --image openbexi-spell-dss:v05-cmd-02
```
