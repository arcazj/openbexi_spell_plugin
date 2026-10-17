# openbexi_spell_plugin

SPELL is an optional runtime for [openbexi_ide](https://github.com/arcazj/openbexi_ide),
PyCharm and IntelliJ IDEA. Procedures use explicit imports from the original
SPELL library. The neutral IDE stays independent of SPELL.

The v0.3 host release is accepted for local Development workflows; see
[the exact host qualification](docs/HOST_QUALIFICATION.json). It supplies a host wheel, an
IntelliJ Platform plugin ZIP and a private native Docker runtime. The native
foundation builds the supplied SPELL 2.6.10 code for CPython 3.13.15, preserving
source provenance and applicable GPL/LGPL notices. See the exact
[execution status](docs/EXECUTION_TO_V06.md).

The [v0.4 original DSS driver and shared provider](docs/DRIVER_RUNTIME.md) connect
that runtime to durable Development and approved immutable Execution, with
read-only Monitoring, fenced binary effects, optional Kafka telemetry,
whole-container pause and recovery without replay. See
[the v0.4 evidence](docs/DRIVER_QUALIFICATION.json) for the qualified GENERIC
simulator scope.

The [v0.5 language qualification](docs/V05_CONFORMANCE_QUALIFICATION.json)
passes **all 763 requirements with none open**. All 61 native suites pass
(2,157 raw checks) on freshly installed, reproducibly built packages. See the
[release notes](docs/V05_RELEASE_NOTES.md) and
[v0.5 release](https://github.com/arcazj/openbexi_spell_plugin/releases/tag/v0.5).
Final distribution and installed host workflows remain v0.6 work; the
[release plan](docs/STABLE_RELEASE_PLAN.md) records the remaining gates.

## Native desktop and CLI

Install `openbexi_spell_host-0.3.0-py3-none-any.whl` in the CPython 3.13 environment
selected by your IDE. The runtime image is `openbexi-spell-host:0.3.0` and needs
Docker Desktop's Linux engine. No host-folder sharing or published IPC port is
required. The host wheel supplies the OpenBEXI extension and shared DAP bridge;
the original SPELL library runs inside the image.

```python
from spell.lang.functions import Display
from pathlib import Path
answer = 6 * 7
Display('Answer: ' + str(answer))
Path('answer.txt').write_text(str(answer))
```

In OpenBEXI, choose **Run ? Reload Runtime Plugins**, select **SPELL**, and use
Run or Debug. Native line breakpoints, stack inspection, current-frame variable
edits, Step, pause, prompts and Stop are supported. The ordinary Python backend
continues to use its own runtime/debugger.

```powershell
openbexi run procedure.py --project C:/path/to/project --language spell
```

For JetBrains, install `openbexi-spell-0.3.0.zip` through **Plugins ? Install
Plugin from Disk**, restart, configure **SPELL Runtime**, and use **Tools ? SPELL**.
See [JetBrains installation and compatibility](docs/JETBRAINS_HOST.md).

Each run uses a bounded project snapshot. Changed/new files are saved under
`.openbexi/runs/RUN_ID/artifacts` with a hash manifest; source files in the editor
are not overwritten. The host supports local Development. Step Out, arbitrary
expression evaluation, conditional breakpoints and operational DSS integration
are later capabilities. See [host runtime and qualification](docs/HOST_RUNTIME.md).

## DSS testing baseline

The repository's root Python package remains the separate bounded v0.1 DSS/SDK
baseline. Installing it does not install the native host wheel or JetBrains ZIP.
Its `spell` alias must stay in a different environment from the native source
runtime. The native Docker image already provides that separation.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install .
.venv/Scripts/openbexi-dss.exe --port 8085 --database var/dss.sqlite
```

The deterministic Dynamic Satellite Simulator exposes health at
`http://127.0.0.1:8085/healthz`, state at `/api/v1/state`, and telemetry at
`/api/v1/telemetry`. It uses the existing binary TC/TM packets and transactional
command journal. Its manual clock supports PAUSE/STEP; automatic RESUME is
explicitly unavailable in this profile. Kafka transport is a separate optional
profile. [DSS container evidence](docs/DSS_CONTAINER_RUNTIME.md) covers the
internal container workflow; published container access is a later gate.

`examples/dss_demo.py` and `examples/desktop_dss_demo.py` belong to the bounded
DSS adapter. Full original driver integration belongs to v0.4, followed by all
763 conformance requirements in v0.5 and distribution/compatibility in v0.6.
Preserve exactly Development, read-only Monitoring and approved Execution.

## Source and development

The seven original manuals and exact source archive remain in `docs/reference`.
See the [source review](docs/SOURCE_REVIEW.md), [roadmap](ROADMAP.md),
[master prompt](openbexi_spell_plugin_master_prompt.md), and
[migration](docs/MIGRATION.md). Historical milestone reports retain their original
source/artifact identities and do not automatically qualify later releases.

Build and test commands for native hosts are in [HOST_RUNTIME.md](docs/HOST_RUNTIME.md).
The retained DSS baseline has its own tests:

```powershell
python -m pip install '.[test]'
python -m pytest tests -q
```
