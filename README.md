# openbexi_spell_plugin v0.1

An independently installable development plugin for
[openbexi_ide](../openbexi_ide/README.md), with the retained bounded SPELL SDK and
a deterministic Dynamic Satellite Simulator (DSS) fixture. Procedures import
SPELL symbols explicitly. The complete source-derived SPELL runtime and actual
JetBrains host plugins remain roadmap gates.

The isolated original-source alpha foundation is available under
[source_port](source_port/README.md), with its own GPL/LGPL wheel and
[qualification](docs/SOURCE_PORT.md). It does not replace this working bounded
adapter or complete the native SPELL executor port.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install .
.venv/Scripts/openbexi-dss.exe --port 8085 --database var/dss.sqlite
```

Or start the packaged test fixture with `docker compose up --build -d`.

The local fixture uses the existing SQLite-backed engine, satellite catalogue,
binary TC/TM packets, command journal, epoch/revision checks and staged TCP command
server. HTTP is at `http://127.0.0.1:8085`; state is `/api/v1/state`, telemetry is
`/api/v1/telemetry`, and health is `/healthz`. The manual clock keeps tests
repeatable; PAUSE and STEP work, while automatic RESUME is rejected in this profile.
It does not pretend that a Kafka publisher is running. The original
Kafka-capable server remains available as an optional `kafka` extra/profile.

Install this plugin into the IDE's selected interpreter and run:

```powershell
../openbexi_ide/.venv/Scripts/python.exe -m pip install .
../openbexi_ide/.venv/Scripts/openbexi.exe run dss_demo.py --project examples --language spell --dss-url http://127.0.0.1:8085
```

Shared sessions can set `serve --dss-url http://127.0.0.1:8085` and then
`submit dss_demo.py --language spell` from a connected controller. Python and
SPELL procedures share the same controller fencing and configured execution slots.

For native desktop Run/Debug, open `examples/desktop_dss_demo.py` in openbexi_ide
and select the interpreter containing this plugin. In Run > Arguments, set
`--dss-url http://127.0.0.1:8086` to use the currently running native fixture.
This procedure explicitly activates its adapter and imports `spell.lang`; the
ordinary Python desktop remains independent of SPELL.

The first adapter supports Display, current-sample GetTM/Verify, catalogue BuildTC,
staged Send and relative numeric WaitFor. Unsupported interactive prompts,
operational graphics and other language families fail explicitly. This profile
does not implement native DataContainer/Step/Goto/warm-start or full legacy driver
compatibility. The retained SDK common policy/TIME code is separately tested;
its presence does not imply every service backend is available.

Original manuals and `SPELL2.6.10-src.zip` are preserved in `docs/reference/`.
They are essential source authority, with their original licenses, and are not
copied into the Apache-licensed runtime wheel. Read the
[source review](docs/SOURCE_REVIEW.md), [roadmap](ROADMAP.md),
[master prompt](openbexi_spell_plugin_master_prompt.md) and
[migration](docs/MIGRATION.md).

```powershell
python -m pip install '.[test]'
python -m pytest tests -q
```

The v0.1 fixture binds only to loopback and uses synthetic satellite data. Paused
epochs, uncertain command effects and backpressure remain explicit; failed sends
are never automatically replayed by this adapter. Operational work requires the
full server's separate migration and acceptance gate. See
[v0.1 qualification](docs/QUALIFICATION.md) for the tested scope.
