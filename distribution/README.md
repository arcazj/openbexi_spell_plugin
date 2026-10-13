# Distribution qualification prerequisites

These tools prepare v0.6 evidence. They do not accept or tag v0.6, which depends
on the complete v0.5 conformance gate. Current artifact versions remain unchanged
until a coordinated release candidate is ready.

`python distribution/rebuild.py` copies the current native recipes, supplied
source archive and distribution recipes into a unique retained source snapshot.
It freezes a toolchain Docker image, then starts two independent builds with
`--no-cache --network=none`. Each build begins without `/source` or `/out`, compiles
the original native source, runs the existing full native gate, packages a wheel,
and exercises fresh installation and removal without a source/build tree.
The comparison checks every shipped native binary, Python source identity and
the complete wheel bytes. A second ZIP of one compilation is not counted as an
independent rebuild. Neither accepted image tags nor historical evidence changes.

The toolchain starts from the recorded offline CPython 3.13.15 base image. Python
dependencies use the existing hash locks, including the separate continuation
and persistent-checkpoint requirements. The toolchain image identity and exact
Debian/Python package versions are recorded. Apt repository reconstruction is
not snapshot-locked yet; reproducing a build requires retaining that exact
toolchain image. This remains an explicit distribution requirement.

Use `--export-toolchain` to retain a hash-bound Docker image archive alongside the
run. On another machine, load that archive and pass its recorded tag through
`--toolchain-image`; the native builds then need no apt or package-index access.
The report checks and records the exact image identity before both compilations.

`stable_wheel.py` keeps volatile test output beside the wheel. The unchanged
native recorder must accept the full native gate first. Native binary contents,
original source archive, source recipes, GPL/LGPL notices and source hashes remain
in the wheel. A deterministic gate-policy manifest identifies the recorder and
native artifacts; the full per-build report is exported as
`native-qualification.json`. The rebuilt wheel's RECORD covers every file.
The integrity tests ensure source/native payloads and executable permissions are
preserved, all RECORD hashes match, and changed native contents reject packaging.

`host_workflows.py` uses a retained copy of the existing private JetBrains test
harness to set the actual plugin's runtime-image setting explicitly. It exercises
Run, XDebugger stack/variables/edit/Step/Continue, prompts, Stop, and removal in
the same private project. It checks images from real run manifests. The normal
user IDE profiles remain untouched. `openbexi_workflows.py` similarly uses a fresh
environment with installed IDE and host wheels and the actual Qt widget test
harness. Its offscreen results are separate from noVNC X-button/scroll testing.

For incremental conformance development, `incremental_native.py` accepts explicit
changed source units inside a prepared compiler image. Checked-preimage patch
recipes must run first. It compiles into a new directory, reads the original
native dependency manifests, and relinks only affected shared/independent graphs.
It preserves `/out` and records source/object/command/binary hashes. A successful
compile is not behavior qualification. Derived host images must copy the actual
linked artifacts into the installed native `bin` directory and retain the patch
recipe, originals, patched sources and report. These overlays are not release
distributions; final native rebuilds must integrate every accepted patch.

Remaining v0.6 gates include a complete v0.5 snapshot, versioned upgrade paths,
the final DSS image/runtime and actual host workflows against final artifacts,
the supported platform matrix, and reproducible reconstruction of the toolchain.
