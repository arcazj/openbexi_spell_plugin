# Installed original-source native runtime

The qualified v0.2 foundation `openbexi-spell-source 0.2.0` packages the original
Python/RPC framework, the shared native executor/DTA library and five native
programs. It is qualified on Linux x86_64, Debian 13, GIL-enabled CPython 3.13.15.
It is an ASan/UBSan build and is separate from the bounded v0.1 plugin alias.
Install it in its own environment; both distributions provide the `spell` namespace.

The native launcher selects its own Python environment through isolated PyConfig.
The DTA import loader loads the executor's exact shared object, preserving one
native singleton graph. It supplies the actual native types. Procedures retain
explicit imports such as `from spell.runtime import ARGS, IVARS` and
`from spell.lang.functions import Display`.

## Qualification

[NATIVE_PACKAGE_QUALIFICATION.json](NATIVE_PACKAGE_QUALIFICATION.json) binds the
wheel to every recipe/source input, native binary and preceding qualification.
The original 143 library units, standalone/recovery gates, ownership probes and
25 context/server/service lifecycle runs all pass with the environment-selection
change. A fresh Docker build stage containing no source or native build tree then
installs the wheel and dependencies into a new virtual environment. Seven checks
verify:

- The installed executor uses that environment and original framework, reads
  native ARGS, writes native IVARS, returns 42 and leaves builtins unchanged.
- The Python diagnostic launcher imports the real shared-library DTA types.
- A plain Python import reports the required diagnostic launcher before loading
  sanitizer-dependent native code.
- Example initialization preserves an existing directory and its contents.
- Installed native files and the corresponding source archive match their hashes.
- The installed listener starts its context, runs a visible Python 3 procedure
  through the original IPC controller, obtains its native result and closes both
  procedure and context normally.
- The installed service command rejects unsupported checkpoint recovery explicitly
  and preserves the requested checkpoint file.

The package is then removed; both console commands and the `spell` namespace are
absent, while plain Python still runs. Two package builds in different output
directories produced identical 50,499,428-byte wheels:

`2998b1a105b8e7c7b8a8bdd05e3a63a5725e8ae13922a1abd2f0103a960acf23`.

Acceptance evidence is `.qualification/v0.2/native-package-05`; its native build
reuses the complete Build 52 gate. The initializer supplies both original
executor names so Python 3 procedure metadata cannot append `_v3` twice. The
disposable installed test records link targets after uninstall and removes those
test links before exporting evidence, avoiding Windows symlink privileges.

This proves reproducible packaging of one qualified native build. Independent
native rebuild reproducibility and production platform/toolchain qualification
remain distribution gates.

## Build and use

From the project root, build and verify the isolated package:

```powershell
docker build -f source_port/distribution-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-package-new .
python scripts/record_native_package.py --evidence .qualification/v0.2/native-package-new
```

Use a new output directory. The build exports diagnostics even when installed
behavior fails; the recorder must pass before accepting the artifact. Wheels are
under `distribution/a` and `distribution/b`. The wheel contains the unchanged
source archive, complete recipes, patches, original notices, GPL/LGPL texts and
qualification identity. The archive and recipes can be extracted to the same
repository-relative paths for a corresponding-source rebuild.

On the qualified Linux platform, create a separate CPython 3.13.15 virtual
environment, install the hash-pinned `source_port/distribution/runtime.lock`, then
install the wheel with `pip install --no-deps`. The commands are:

```text
spell-native doctor
spell-native init-example /absolute/new/example-directory
spell-native run -f /absolute/procedure.py -c /absolute/new/example-directory/config/server/server.xml -n example
spell-native-python -I /absolute/python-script.py
```

Apply the four SPELL environment variables emitted by `init-example` (also saved
in its `environment.json`) before executing the example. The initializer uses
the original local example driver with its qualified import adaptations, empty
local databases and no site-specific external data-source configuration. Native
`server`, `listener`, `context` and `service` subcommands forward original options.
These are foundation commands; host UI integration follows in v0.3.

## Release boundary

The acceptance recorder marks `v02_foundation_qualified: true` for this artifact.
This closes the original-source native foundation on the platform above. Native
service checkpoint resumption is explicitly unsupported; cold restart, live
reconnection and ordinary procedure ON_LINE/ON_STEP recovery are qualified.

The operational DSS driver, JetBrains/OpenBEXI host plugins, full inventory
conformance, production packaging and broader supported-platform matrix remain
later release gates. The report's full-release and independent-native-rebuild
flags remain false for those later requirements. Leak sanitizer is disabled;
no Windows or macOS native compatibility is claimed here. The bounded
`openbexi-spell-plugin 0.1.0` adapter remains a separate testing baseline until
host integration replaces it; it must not share an environment with this wheel.
