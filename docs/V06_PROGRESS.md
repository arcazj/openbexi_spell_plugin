# v0.6 distribution prerequisites

v0.6 is not accepted. It remains dependent on full v0.5 conformance, final native
patch integration, versioned upgrades, and distribution/runtime qualification.
Accepted earlier artifact versions and Docker tags are preserved.

The [distribution tools](../distribution/README.md) now retain immutable source
snapshots and compare two fresh native compilations, instead of creating two
wheels from one compilation. The original complete native recorder still gates
packaging. Volatile qualification logs stay in external per-build evidence;
original sources, licenses, recipes and native identities remain in the wheel.
Two packaging integrity checks pass, including RECORD validation and rejection
of changed native contents.

## Host artifact and workflow evidence

Two independent Java compilations produced the identical current 0.3.0 ZIP,
SHA-256 `da56fdc2fec31483d49c75ee4bf207fe75199418562ce331c02bcdcc6c571ef8`.
Two Python host wheel builds with fixed SOURCE_DATE_EPOCH produced SHA-256
`0976a0c49bba647aa1a0b99a7feccd0cbd5921068f97006fae8c9b7b2cea0192`.
Versions are unchanged; this is not an earlier-version-to-v0.6 upgrade test.

| Host | Exact tested platform | Current evidence |
| --- | --- | --- |
| OpenBEXI IDE 0.3.0 | Windows x64, CPython 3.13.15, PySide6 Essentials 6.10.3 | Fresh installed IDE/host wheels, actual Qt widgets offscreen: Run, debugger breakpoint/stack/edit/Step/Continue, prompt, Stop, removal and ordinary Python afterward |
| PyCharm 2026.1.2 | Windows x64, build 261.24374.152 | Private real IDE installation: Run, XDebugger/edit/Step/Continue, prompt, Stop and restart after removal |
| IntelliJ IDEA 2026.2.3 | Windows x64, build 262.10968.63 | The same actual installed plugin and removal workflows |

All three workflow results bind the actual per-run image identity to the current
COMMON/TIME image. They do not qualify later DATA/FLOW/UI overlays or a final
v0.6 image. Plugin Verifier 1.410 accepts both JetBrains builds, reporting seven
experimental API usages for PyCharm and one for IntelliJ. No broader host,
native Windows, macOS, ARM or free-threaded CPython support is inferred.

Evidence roots:

- `.qualification/v0.6/jetbrains-a`, `jetbrains-b`, `host-wheels-a`, `host-wheels-b`
- `.qualification/v0.6/verifier`
- `.qualification/v0.6/hosts/f44a5d0a5baa4ee1b4209d6fa801f45f` (PyCharm)
- `.qualification/v0.6/hosts/241b73b122c745208d3a7a07cebbe5f9` (IntelliJ)
- `.qualification/v0.6/openbexi/86d977c8f0de46dea373dfcd19923431`
- `.qualification/v0.6/packaging-tests.xml`

These host tests use private profiles and ordinary application test APIs. They
do not establish visual noVNC X-button closure or mouse-wheel scrolling.

## Native rebuild status

The first independent attempt,
`.qualification/v0.6/rebuild/6a340659e519410f8d418e5a769c7268`, was rejected by
the recorder because the new toolchain recipe omitted the separately locked
cloudpickle continuation dependency. The failed logs, snapshot and diagnostic
build image are retained. The toolchain recipe now includes the existing
continuation and persistent-checkpoint lock files. Its separate successful
context suite does not override the earlier WS failure.

The corrected independent pair uses snapshot
`.qualification/v0.6/rebuild/a1f60eb525944f47bd2cfbfc649cc30a`.
Both complete native gates and seven fresh installation/removal tests pass.
All six shipped native binaries, Python sources, and complete wheels are
byte-identical across the two independent compilations. The wheel SHA-256 is
`8771ee36c55ab4c95d14638275d67637d2d6dcc96b555305e485bd1385d44174`.
The [prerequisite manifest](V06_QUALIFICATION.json) binds the evidence, actual
wheel/native contents, host workflows and verifier reports. It explicitly leaves
both release acceptance flags false.
This snapshot predates the new native DATA/FLOW/UI conformance fixes, which must
be integrated before final distribution acceptance.

The toolchain is frozen by exact Docker image identity and records installed
Debian and Python package versions. Apt reconstruction is still not tied to a
repository snapshot. The corrected toolchain image is
`sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2`.
Its retained 641,929,216-byte `toolchain-image.tar` has SHA-256
`68735a13c6e54c4649dac5f72c27655ed817aef4ba5595d14b28fc764cf115e9`;
`toolchain-export.json` binds the archive and image. Loading this archive and
using `rebuild.py --toolchain-image` supports offline reuse of the exact compiler
environment. The current native profile remains the Linux x86_64,
CPython 3.13.15 ASan/UBSan diagnostic build; leak sanitizer is disabled.

Remaining release gates include complete v0.5 acceptance, final integrated native
rebuilds, versioned upgrade paths, final installed artifacts and all three host
reruns, shipped DSS image runtime qualification, and reproducible toolchain
reconstruction. Partial evidence must not promote either v0.5 or v0.6.

## Subsequent DATA/FLOW/UI development integration

The combined conformance candidate is
`openbexi-spell-host:v05-ui-flow-data-final`, exact image
`sha256:0eadf2e3b1e961a5e403b79b665e70b22c649179ccde40e86ffceae2ee7559ec`.
It derives from the separate DATA context runtime and incrementally recompiles
the explicit UI/FLOW units with `distribution/incremental_native.py`.
The actual installed shared executor SHA-256 is
`fd0d69a80c4d9a83a05c483a5f025f02afd45806420934a66a866288616b0ac7`;
the retained DATA `SPELL-Context` SHA-256 is
`50559be847e262594df8f21aaaccac59bea610e67c70f97c4a57c962b1cf6cdb`.
The checked FLOW Python overlay `exechelper.py` is
`fae4c58ab9222e54e08f7372dea0520e8a7f699939e565ed596c664a195d2d6b`.

`/opt/combined-native-patch` retains original, ported and patched native sources,
exact recipes, compile/link commands and hashes. Its `python/` directory retains
the checked original/patched Python helper and a manifest bound to the native
manifest. This image is the shared target of the separately recorded
`conformance/evidence/ui.json` and `flow.json` conformance work. It does not replace
the immutable baseline's independent rebuild evidence. Final release packaging
must rebuild the integrated source recipes independently and rerun the installed
host gates with those final bytes.

The complete combined development image now passes 168 TIME checks, 44 COMMON
checks, four direct-IPC silence checks and all ten native host regressions.
Its separately integrated DSS development image is
`sha256:fd350eeaec46d7408384c04d0888e89776a7544c59f88c026e4c70efa1562117`;
all nine actual native driver acceptance tests pass. The package/release-gate
regressions pass 214 tests. These results are bound in
[the conformance checkpoint](V05_CONFORMANCE_QUALIFICATION.json). The accepted
DSS v0.4 image is unchanged. This integration closes the current native patch
regression checks while preserving full release/distribution gates above.
