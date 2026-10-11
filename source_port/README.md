# Original-source SPELL foundation 0.2.0a1

This separate GPL/LGPL distribution uses the exact supplied SPELL 2.6.10 archive.
It retains the original Python implementations and notices, generates the three
original RPC schemas and records exact preimage/output hashes. Five small patches
defer native-type imports, reject the old dictionary fallback and use the standard
thread-pool implementation instead of copying CPython's private worker function,
explicitly import the Python 3 URL-encoding module, and correct driver-cache
cleanup for namespace modules and paths appended by the manager.

The foundation wheel requires an **isolated CPython 3.13 environment**. Both it and
the existing Apache bounded adapter provide `spell`; installing them together is
unsupported. The working IDE/DSS adapter stays on its separately qualified wheel.

```powershell
python -m venv .qualification/v0.2/source-env
.qualification/v0.2/source-env/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r source_port/build.lock
.qualification/v0.2/source-env/Scripts/python.exe source_port/build.py --output .qualification/v0.2/source-a
python -m venv .qualification/v0.2/source-runtime-env
.qualification/v0.2/source-runtime-env/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r source_port/runtime.lock
.qualification/v0.2/source-runtime-env/Scripts/python.exe -m pip install --no-deps .qualification/v0.2/source-a/wheels/openbexi_spell_source-0.2.0a1-py3-none-any.whl
.qualification/v0.2/source-runtime-env/Scripts/python.exe -I source_port/qualify.py --output .qualification/v0.2
```

Use a new output directory for every build. Install the resulting wheel in a
different clean environment, together with the hash-pinned `runtime.lock`, and
run `python -I source_port/qualify.py --output .qualification/v0.2` there. No
builtins injection or fake native container is provided. Procedures use explicit
module imports. A native type request raises a clear error until the real DTA
library is built and qualified. Driver-framework import success is not full
language or operational acceptance.

The native executor, DTA/UTIL/EXC/WS, Step/Goto/warm-start, complete driver service
coverage and real IntelliJ/PyCharm host installation remain required v0.2/v0.3
gates. This is an alpha source/RPC milestone; it is not a completed v0.2 runtime.
The wheel includes the unchanged corresponding source archive, recipe, patches,
provenance manifest and original GPL/LGPL notices.

The embedded `spell_source_provenance/build.py` can rebuild from the included
archive in a build environment with `build.lock`. The original source contains
site-specific GCS/data-source defaults; the lifecycle fixture supplies explicit
local configuration. Those defaults require a separate migration decision before
any operational activation.

For the original native compile diagnostics, run from the repository root:

```powershell
docker build -f source_port/native-probe.Dockerfile --output type=local,dest=.qualification/v0.2/native-probe .
```

This build exports compiler logs; it does not install a native runtime or require
starting a container. The probe tests unchanged DTA/UTIL/EXC/WS units against the
pinned Linux CPython 3.13 base. Package/compiler versions are recorded in its
output. Apt toolchain resolution is captured, not locked for native reproducibility.
