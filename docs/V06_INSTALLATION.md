# v0.6 installation and supported platforms

Release acceptance and exact artifact identities are recorded in
`V06_QUALIFICATION.json`; acceptance requires `v06_accepted: true`.

| Component | Qualified platform |
| --- | --- |
| Original native executor and DSS runtime | Linux x86_64, Debian 13, GIL-enabled CPython 3.13.15; Docker Linux containers |
| OpenBEXI host | Windows x86_64, CPython 3.13.15, installed OpenBEXI IDE 1.1.0 |
| IntelliJ plugin | Windows x86_64, IntelliJ IDEA 2026.2.3, build 262.10968.63 |
| PyCharm plugin | Windows x86_64, PyCharm 2026.1.2, build 261.24374.152 |
| Host/shared Python package upgrade and removal | Windows x86_64 and Linux x86_64, CPython 3.13.15 |

The ZIP's compatibility range is broader than the two IDE builds exercised here.
No native Windows, native macOS, ARM, free-threaded CPython or Linux desktop IDE
qualification is claimed. The simulator is GENERIC; site-specific mission
drivers and operational security/capacity acceptance remain separate work.

## Load the runtime

Verify downloaded files against `SHA256SUMS.txt`. Load the runtime archive, then
assign the package defaults to the exact included images:

```text
docker load --input openbexi-spell-v0.6-runtime.tar.gz
docker tag sha256:65aa34c7c98a544d86f43e993928b1bf18e88258bdea319752b9574bab7d1d70 openbexi-spell-host:0.6.0
docker tag sha256:ef97426030ab9db06f573710ebbec56ff2486ed558697c058ce9d724c9036100 openbexi-spell-dss:0.6.0
```

The host image supports local procedure execution. The DSS image adds the
composed original-driver bridge used by shared procedure sessions.
Both images are compiler-free and run the diagnostic ASan/UBSan native build.
Leak sanitizer remains disabled.

## OpenBEXI and shared sessions

Use a CPython 3.13 interpreter. Install the `openbexi_spell_host-0.6.0` wheel
through OpenBEXI's plugin manager or with that interpreter's pip. Select the same
interpreter in the IDE; SPELL becomes available as a language backend.
Run/Debug, workspace prompts and controls, variables, child procedures and
isolated artifact export use the loaded runtime.

For shared procedure sessions, install `openbexi_spell_shared-0.6.0` in the
interpreter hosting the shared service. Its host dependency is version 0.6.0.
Install `openbexi_spell_dss-0.6.0` where the DSS bridge runs; its pinned dependencies
are grpcio 1.84.0 and protobuf 7.36.2. The bounded simulator service remains the
separate `openbexi-spell-plugin 0.1.0` package.

## JetBrains IDEs

Install `openbexi-spell-0.6.0.zip` using **Settings → Plugins → Install Plugin
from Disk**, then restart the IDE. Configure the plugin with the CPython 3.13
interpreter containing `openbexi-ide` and `openbexi-spell-host 0.6.0` and the loaded
runtime image. The installed qualification uses private project/configuration
directories; it never changes the user's existing IDE profile.

## Upgrade and removal

The tested OpenBEXI plugin-manager path is host 0.3.1.dev3 → 0.6.0. The Python
package path is host 0.3.0 plus shared 0.4.0.post1 → both 0.6.0 on Windows and
Linux. Native source 0.3.0 plus DSS driver 0.4.0 → both 0.6.0 is tested on Linux.
The JetBrains path is ZIP 0.3.1-workspace.2 → 0.6.0 on both listed IDE builds.
Complete running procedures before replacing packages.

Use the plugin manager to replace/remove the OpenBEXI host wheel, or install
the selected new wheels with the interpreter's pip. Upgrade host and shared
together when both are present. For JetBrains, install the new ZIP and restart;
to remove it, uninstall the plugin and restart. Qualification verifies that
project files and preferences survive and ordinary Python execution remains
available after removal.

Standalone native wheels require Linux x86_64 CPython 3.13 and the pinned runtime
dependencies in `source_port/distribution/runtime.lock`; the supplied images
already contain them. See `NATIVE_PACKAGE.md` for launcher commands. Native
service checkpoint resumption remains unsupported; cold restart and live
reconnection retain their documented scope.

## Rebuild

The build-environment archive contains the exact base, compiler and compiler-free
runtime images. The retained offline inputs contain the original Debian package
bytes and hash-pinned Python wheels. `distribution/reconstruct_toolchain.py`
rebuilds from those local inputs with networking and Docker build cache disabled.
This reproduces the package inventories; Docker image identifiers can differ
because image metadata contains build timestamps.

`distribution/rebuild.py` builds the native wheel twice independently using the
locked compiler image. `distribution/build_images.py` composes the host and DSS
images from the selected wheel. Native binaries, Python sources, composition
manifests and the complete native wheel must match across independent builds.
Host, shared, driver wheels and the JetBrains ZIP have separate paired builds.
The release evidence records exact commands, input hashes and results.
