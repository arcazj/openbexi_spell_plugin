# Follow-up composition preparation

This isolated worktree starts at `6f82c2c01bc5dde1fb18500e1367e3d257df1d9f`.
The last qualified checkpoint remains **470 qualified / 293 open**, on exact
DSS image `1fef3e691d8590079898a01cb7bddad9dbce8d9b4c4c29046a790e16af2a3342`.
The first frozen pair at `120ed73` failed its second context gate on a real
forced-pause/shutdown race; its first build passed. Both builds produced identical
native binaries. The retained pair remains failed. Qualified shutdown donor
`a97118e` is now composed for a fresh pair; no combined runtime is accepted.
The historical coverage and donor reports have not been promoted or regenerated.
Their source hashes describe the earlier commits, not this changed working tree.

The eight production tranches cherry-pick without conflicts:

| Tranche | Original commit | Composition boundary |
| --- | --- | --- |
| Named SCDB read-only view | `e85a2e9b77465ba6865949f3884f41d655840196` | Original `database.py` and `dbmgr.py`; ordered after database import and user-database corrections |
| Send/WaitFor telemetry handoff | `bfac147f03ac539114465f5d63b81e40237a3d4a` | `tchelper.py` after CMD; proxy `tm.py` after LIMIT |
| Send verification modifiers | `231700dbeabe46ad3f488dc0db33fdc460860889` | `tchelper.py` after timing; no driver or native-unit changes |
| Child-procedure host and prompt routing | `166caff449f208d41859d41257517fc8fec6f509` | Four host Python modules; independent of original SPELL and driver source recipes |
| Queued console input | `15c7dd105a8c3502daf20a38afc73171ce76cb71` | Local host client runner; after the child-host commit, separately bound host wheel and actual Qt evidence |
| Distinct host upgrade candidate | `4a4c8c915ca7379af3a868269a40559f933e4fed` | Host 0.3.1.dev1 module/package version after console fix; real IDE upgrade and removal, preserving accepted defaults |
| Caught-exception recorder cleanup | `9c674bd51115e016dd135d3ed76c1ebf8a4ed207` | `SPELLframeManager.C` after the central port; production `fix=True`, without audit instrumentation |
| Checkpoint source identity and context recovery | `53afd40d46fa1e1c0e116de877a48f2f43ca9060` | `SPELLinterpreter.C` after the central port; `SPELLcontext.C` after the qualified DATA correction |

The current dispatcher binds 27 recipes, 14 native units, 21 original SPELL
Python modules and two corrected driver modules. SCDB adds two Python units;
timing modifies units already present. The recorder adds one native unit and
has no SCDB dependency. The source-identity correction adds the interpreter unit;
context recovery composes against the exact DATA-corrected context preimage.
Every recipe enters the continuation identity, so
these changes require a fresh native build. The central port recipes are unchanged.

`evidence/followup-qualified-sources.json` reads exact committed donor reports,
retains their commit/report hashes, and verifies the timing preimages against
the preceding CMD/LIMIT outputs, then Send's preimage against timing's output.
The prior source fixture remains unchanged.
The context chain is checked against the separately committed DATA and recovery
donors, and the identity donor's recorder bytes must equal the earlier recorder
donor. Native manifests now retain every intermediate stage, including the
continuation header; installed provenance validates each stage through to the
final source hashes. The original archive and central port bytes remain fixed.
Source composition checks compare the final native, Python, driver, child-host
and local host-client bytes against those independent donors. The recorder's
complete original/ported/patched hashes and production mode are checked. No
original source is executed by that comparison.

SCDB provenance now accepts a real installed composition and validates its SCDB
stage; the historical overlay branch remains explicit. Timing's runner and
recorder use the verified composed driver outputs when available. Native cases,
oracles and retained donor evidence are unchanged. The image auditor also
checks the complete installed host Python source set against the build snapshot,
including `children.py` and `prompts.py`; missing, changed or extra modules are
rejected. The focused composition, preimage-failure/recovery, identity patch and
host-source-set suite passes 28 tests plus two subtests, including rejection of
Send before timing and recovery before DATA without modifying the source tree.
Eleven shared provenance tests cover native stage ordering and rejection of
missing or altered stages; five recorder provenance parser tests
also pass. The
recorder qualifier replays its retained historical 24+20+4 controls and 23-test
gate successfully; this is recorder compatibility, not a fresh runtime run.
The console donor retains its independent host wheel RECORD audit, 16 pipe
checks and actual Qt Run/Debug evidence. The distinct 0.3.1.dev1 donor adds two
identical offline wheel builds, full RECORD and installed-payload verification,
real Qt upgrade from 0.3.0, Run/Debug, removal and ordinary Python afterward.
The exact client wheel SHA is
`d2b7cc41711d8ec7014e83babc6f2890f2bdf3c5668c6cffdf180d5ceeb1648d`.
These results do not establish behavior of the future combined image.

## Before a build freeze

1. Review the completed fresh installed-provenance branches and source/preimage
   composition checks. The recorder's 24 original and 20
   additional standalone controls, four IPC error controls and existing 23-test
   executor gate must rerun against the exact installed sources. Preserve the
   synchronous frame-ownership and exceptional RETURN guards.
2. Rerun the qualified identity donor's eight native IPC error controls and 22
   actual recovery controls on the fresh installed composition. The donor proves
   source resolution and kill/reopen; its diagnostic overlay is not acceptance of
   this new wheel. Fatal invalid warm-start rejection followed by `UNINIT` remains
   the observed policy; stable terminal error/recovery UI behavior stays open.
3. Recheck the final source changes, then freeze one exact Git identity.
   All recipes and full source
   chains must enter the wheels and their RECORDs before installation.
4. Finish the fresh identity/provenance recorder handoff and final review before
   the expensive pair. Ranging and additional child close/kill corrections remain
   outside this composition. Preparation of dependencies and workflow recorders
   does not authorize a build or promote coverage.

After freeze, the pinned toolchain is
`sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2`.
The next runtime requires the unchanged full native gate, two independent
no-cache/network-none builds, complete wheel-byte comparison, fresh installed
native/Python/driver/host audits, and actual conformance regressions on the exact
new image. The host wheel and final installed Qt/JetBrains workflows retain
their own artifact and platform gates. No build is authorized by this document.

## Remaining requirements

The committed checkpoint's 293 open rows are: LIMIT 52, CMD 45, SPECIAL 43,
DATA 36, OBS 32, UI 32, FLOW 28, COMMON 20 and PY 5. FILES and TIME have no open
inventory rows within their recorded profiles. Neither v0.5 nor v0.6 is accepted.

The new donors propose only `DATABASE-SCDB`, `SECTION-4-15-1-096` and
`MODIFIER-WAIT`. Those three rows remain open until actual fresh composed
evidence passes all dimensions and strict source/dependency validation. Child
host, Send modifier and recorder workflows add no inventory row by themselves.
Even successful integration
would leave at least 290 original rows open, plus the remaining distribution,
upgrade, host/platform and unresolved recorder/IPC requirements.

## Shutdown cancellation follow-up

The checked `shutdown_pause_patches.py` changes only context executor
`forcePause`: active waits observe close/process termination while preserving
the five-second deadline and ordinary `waitStatus`. Its independent donor has
10 passing controls (baseline failed five) and the unchanged 25-lifecycle context
gate. Composition tests compare the complete source bytes to that committed
donor. Child close/kill and ranging changes remain excluded from this freeze.

Local preparation: 99 distribution tests and four shutdown recipe tests pass.
A new driver preflight and full independent native pair remain required.
