# v0.6 distribution prerequisites

## Replacement candidate 2026-10-20

The GIL-based trace correction was rejected. The 1,200-message burst stalled
even with a 600-second diagnostic deadline. Native debugger
[stacks](evidence/v06-trace-read/deadlock-stacks.txt) show a display worker holding
the display mutex while waiting for the GIL, and the interpreter holding the GIL
while waiting for that display mutex. The full sequence also stalled during
child argument recovery. These failed reports remain retained.

The replacement publishes execution counts into an atomic scalar after
evaluator-owned trace changes. Background CIF workers load that scalar without
borrowing trace objects or acquiring the GIL. The burst test's original 30-second
deadline is restored. Both independent native builds passed at
`.qualification/v06/snapshot-native-pair/31bb22dba4a7497182f9259dc2b0bdb3`,
including all byte identity and installation/removal gates. The resulting
host runtime passed all 14 adapter tests, including the original burst deadline.
The replacement DSS image is
`sha256:ef97426030ab9db06f573710ebbec56ff2486ed558697c058ce9d724c9036100`;
its host companion is
`sha256:65aa34c7c98a544d86f43e993928b1bf18e88258bdea319752b9574bab7d1d70`.

Installed DSS integration also exposed a huge-integer timeout conversion error.
The checked command recipe now validates bounds before converting to a C double.
The installed integration oracle explicitly follows the qualified 3,600-second
TC/TM budgets, numeric native ranging statuses and two-baseband catalog. All
original invalid-input, recovery, exact effect and binary receipt assertions
remain. [The incident](evidence/v06-timeout-bounds/incident.json) retains the
failed original and initial adapted oracles. The corrected source composition
and boundary suite passes 68 tests.

Fresh native/driver artifacts, images, installed workflows and the complete
language sequence must pass before acceptance. The earlier image-specific
results below are historical, not acceptance of this replacement.

The replacement passes all focused controls: 14 host-adapter cases, 10 child
argument cases, two nine-case child-mode runs, 24 duplicate answers, 12 prompt
aborts and 49 installed DSS integration tests. The final documented wheels also
pass all 49 installed DSS tests, Linux native/driver upgrade and removal, host
lifecycle, installed OpenBEXI workflows and actual plugin-manager upgrade/removal.

The first complete sequence attempt passed all 40 startup behavior cases but its
provenance verifier still expected the checkpoint patch to be the final
frame-manager modification. The corrected verifier requires both exact patch
stages and the final source hash; 28 tests plus 34 rejection subtests pass.
[The failed gate remains retained](evidence/v06-trace-read/checkpoint-provenance.json).
The per-source trace stages are selected explicitly; the verifier also passes
against the actual installed manifest and independent compiled artifacts.
The full sequence restarts at
`.qualification/v06/snapshot-language/6d28bc97c53f4c53b0787bfc96e64bc0`.
IntelliJ and PyCharm installed upgrade/removal workflows now pass too. Both final
runtime images export with all descriptor and blob hashes verified. An independent
audit verifies 743 final host evidence file bindings with no missing sources.

## Earlier candidate verification 2026-10-20

The corrected native pair at
`.qualification/v06/trace-read-native-pair/fd3fba2eb0c14024869be32d2a0c41f2`
passes all six independent build, byte identity and installation/removal gates.
The final candidate DSS image is
`sha256:7dfbca0d2e0d5859cc13f8dda5ad721594e9cf09cb04dba3e238797e1ce203f4`.
Its host-only companion is
`sha256:e1eca1f10e5dbc265bb8924d93e064eb766d53b39176771d4b20c4965d05da63`.
Both exported image descriptor graphs and content blobs verify.

Host, shared and driver wheel pairs and the two JetBrains ZIP builds are
byte-identical. Windows and Linux Python-package upgrade/removal and Linux
native/driver upgrade/removal pass. OpenBEXI IDE 1.1.0 runs the installed host
wheel, including Debug, variables, Step/Continue, prompts, Abort and artifact
export. Its actual plugin manager also upgrades the published 0.3.1.dev3 host
to 0.6.0 and removes it while preserving project files and preferences.

Installed IntelliJ IDEA 2026.2.3 and PyCharm 2026.1.2 workflows pass, including
upgrade from the published 0.3.1-workspace.2 ZIP and removal in the same private
project/profile. Both compatibility verifiers pass. Harness corrections preserve
the original preference sentinel, save preferences synchronously and use the
IDE application exit API after removal; earlier failed captures remain retained.

Repeated child modes (twice), duplicate prompt answers and prompt aborts pass on
the corrected DSS image. The complete 61-suite native sequence is still running
at `.qualification/v06/trace-read-language/3985fb23a3b34bec8a7eb09edb6f321a`.
It adopts only the validated prefix on this identical image after a retained
Docker provenance timeout. It does not reuse the earlier faulty image's prefix.
All 763 requirements still need their final fresh evidence review. Installed DSS
integration, the complete repository regression and portable release evidence
remain gates. **v0.6 is not yet accepted or published.**

## Native startup race found 2026-10-20

The workspace-enabled image `sha256:f4b35c563abc4c184b1ce7267c11216284653dd2797bd58e1c99c9eb14920ba7`
passed 57 native suites, then failed `child-modes/nonblocking-late-error`.
The retained [incident](evidence/v06-trace-read/incident.json) and ASan log show
an IPC worker reading a freed execution trace while the interpreter clears its
trace map during startup. This is a release-blocking native memory error.

`trace_read_patches.py` is a candidate correction: the CIF count reader holds
the existing CPython GIL until the borrowed trace's count has been copied.
The central port remains unchanged; composition records the additional patch,
checks exact original/ported preimages and updates the continuation identity.
Six patch/composition/provenance checks pass. These are not runtime acceptance evidence.

An independent offline native build pair is running under
`.qualification/v06/trace-read-native-pair/fd3fba2eb0c14024869be32d2a0c41f2`.
The first attempt omitted the new recipe from the Docker COPY list; its failed
log is retained at `eec8779500dc4d88a9c3b73b3b4c7cd9`. Both recipe-copy stages
are now corrected. Next: finish build/install verification, build new runtime
images, stress startup and child modes under ASan, then repeat the full native
sequence. Do not reuse the passing prefix from a different image or treat this
candidate patch as a qualified fix.

## Resumed 2026-10-19

The user explicitly resumed v0.6. Work continues in
`C:/obspell_v06_resume` on `release/v06-resumed`, integrating the committed
shared procedure workspace (`6a00c5c`) with the distribution branch (`baad5f4`).
Package versions and default runtime references use 0.6.0; the workspace UI,
editor exporter, presentation protocol and descriptor-derived ZIP name remain.
The original checkouts and their uncommitted edits are preserved.

The integrated source passes 67 focused host, notification, prompt, status,
child and editor-export tests plus 33 subtests. The JetBrains ZIP compiles against
IntelliJ IDEA 2026.2.3. Local evidence is `.qualification/resume-integration.xml`
and `.qualification/resume-jetbrains/build.json`. These checks do not qualify
installation or the final release.

The earlier distribution checkout retains passing native reproducibility,
native/driver and Python upgrade/removal, shared-wheel and verifier evidence
under `C:/obspell_v06/.qualification/v06`. A fresh pre-workspace host/DSS image
build passes installed integrity checks at
`images/06ca583417074f278e30b801f5144bb2/result.json`. Its full native sequence
was started at `language-regressions/94855f8f73f44edcac84ed5ad9dc665d`; it is
not final workspace-enabled release evidence.

Remaining work includes porting and validating the retained uncommitted upgrade
harnesses, rebuilding host artifacts with the workspace changes, the full native
sequence on final images, installed OpenBEXI/IntelliJ/PyCharm upgrade workflows,
and the supported-platform/release dossier. The earlier repository run has
60 failures and 8 errors, including stale source bindings after version changes;
retain and resolve these without weakening evidence validation. No v0.6 release
is accepted or published by this checkpoint.

The [v0.5 acceptance record](V05_CONFORMANCE_QUALIFICATION.json) qualifies all
763 original requirements with none open. All 61 native suites (2,157 raw
checks), focused prompt/child controls, identical offline builds and fresh
installation/removal checks pass. Final installed-host workflows, versioned
upgrades, production packaging and the supported-platform matrix remain v0.6
work. The historical narratives below retain their original artifacts and limits.

## Historical 470-requirement checkpoint

v0.6 is not accepted. The earlier checkpoint has **470 qualified / 293 open**
original requirements. It retains the preceding 422 qualified rows and adds 48
bounded clauses after actual integrated native runs. Artifact versions and
accepted Docker tags remain unchanged. Both release flags remain false in the
[historical conformance manifest](../distribution/evidence/pre-v05-qualification.json) and
[distribution manifest](V06_QUALIFICATION.json).

The checked composition now includes DATA, UI, FLOW, DTA, TIME, OBS, CMD,
dictionary IPC, scheduler, resource, LIMIT, database import/save, Notify and
ValueType corrections. Native, original SPELL Python and driver proxy changes
are applied before wheel creation. Their complete RECORDs cover corrected
sources, original-source evidence, recipe chains and native artifacts.
The central CPython port recipes remain unchanged.

Two independent builds from source freeze `5cbbba3` passed the unchanged native
recorder suite with `--no-cache --network=none`. All six shipped native binaries,
Python sources, composition manifests and complete wheel bytes are identical.
Both builds passed eight fresh-install/removal checks without a build tree.
The Linux x86_64 CPython 3.13 wheel remains version 0.3.0; its SHA-256 is
`ac1c259cd85f9e4993264061f6a4372af2f08bfbedc31a5b929941cdc1b637db`.
The independently built driver wheel remains version 0.4.0, SHA-256
`6e491863da48d86daa7160a47f9b43870b7a272e90fda56d42f57262dc3069f5`.

Fresh host and DSS images pass installed native/Python/driver RECORD, source
composition and compiled bridge audits. The host image is
`sha256:95209eb11db106163c1a2e90b8a5cb63c60e5c613f0b93c9dfb8ad4d17a13853`.
All selected native conformance reports and ten host debugger workflows pass on
`sha256:1fef3e691d8590079898a01cb7bddad9dbce8d9b4c4c29046a790e16af2a3342`,
available as `openbexi-spell-dss:v06-integrated-97bb64016332`.
[Build evidence](../distribution/evidence/next-integrated-rebuild.json) and
[the native checkpoint](../distribution/evidence/next-integrated-conformance.json)
bind exact source, artifact, raw-report and normalized-report hashes.

The first TIME attempt ended during native IPC startup; one initial ValueType
case timed out during read-only ground-state lookup. Unchanged complete reruns
passed. Both failures remain retained, and their underlying causes are unresolved.
The race fixture's startup import collision was fixed by renaming its generated
`inspect.py`. The scheduler recorder now distinguishes native observation links
from recursive check dependencies; the strict cycle gate remains intact.

A separate [recorder incident](../distribution/evidence/recorder-lambda-incident.json)
reproduces a procedure-owned lambda exception-handler failure during ON_LINE
warmstart on the prior 49667 image without the SCDB patch. Current PY evidence
explicitly qualifies imported evaluation and sets `checkpoint_claim:false`;
FLOW callback tests qualify live effects and callback replacement. Neither
qualifies generic restored exception-handler behavior. The current composition
has no recorder correction, so the incident remains an unresolved release limit.

The 293 open requirements, generic recorder correction, final installed desktop
workflows, versioned upgrades and supported-platform matrix still block release.
Later SCDB read-only, Send/WaitFor timing and child-procedure host changes are
separate increments. The compiler-bearing Linux x86_64 CPython 3.13.15 ASan/UBSan
image is diagnostic; leak sanitizer is disabled. The exact toolchain can be
reused offline, while apt reconstruction remains unlocked. Historical host and
platform results below retain their own artifact/image scope.

## Historical host artifact and workflow evidence

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

## Historical COMMON snapshot rebuild

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

At that earlier snapshot, remaining gates included complete v0.5 acceptance, final integrated native
rebuilds, versioned upgrade paths, final installed artifacts and all three host
reruns, shipped DSS image runtime qualification, and reproducible toolchain
reconstruction. Partial evidence must not promote either v0.5 or v0.6.

## Historical DATA/FLOW/UI development integration

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

That combined development image passed 168 TIME checks, 44 COMMON
checks, four direct-IPC silence checks and all ten native host regressions.
Its separately integrated DSS development image is
`sha256:fd350eeaec46d7408384c04d0888e89776a7544c59f88c026e4c70efa1562117`;
all nine actual native driver acceptance tests passed. The package/release-gate
regressions passed 214 tests. Those reports remain in Git checkpoint `e365053`;
the [current conformance checkpoint](V05_CONFORMANCE_QUALIFICATION.json) records
the fresh wheel and image above. The accepted
DSS v0.4 image is unchanged. This integration closes the current native patch
regression checks while preserving full release/distribution gates above.
