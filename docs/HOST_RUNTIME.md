# Native host integration (v0.3 in progress)

The optional `openbexi-spell-host` wheel exposes the neutral OpenBEXI backend API
and a shared DAP relay. Its private Docker container installs the separate
original-source native SPELL wheel and connects through the original listener,
context and executor IPC. Project procedures use explicit `spell` imports.
The host interpreter does not receive a replacement SPELL language runtime.

The local adapter currently owns one Development session. Run, breakpoints,
current-frame variable inspection/editing, Step, pause, prompt input and normal
shutdown have independent native adapter checks. Step Out and arbitrary
expression evaluation are unavailable. Execution and Monitoring, operational
DSS drivers and shared controller admission remain later gates.

Windows projects are copied into a private container snapshot. No host folder
bind mount or native IPC port is required. Regular files are bounded to 32 MiB
each and 256 MiB total; dependency directories, Git metadata, `.env` files and
prior run artifacts are excluded. On normal completion, changed/new files are
exported under `.openbexi/runs/RUN_ID/artifacts`, with a hash manifest. The
original project files are never replaced. At this milestone, forced stops do
not guarantee result export; cleanup is qualified separately.

The original procedure path and auto-imported UserLib path are distinct. Pointing
both at a project executes procedure bodies during startup; the host keeps the
original empty UserLib and uses the project only as its procedure path.

## Qualified native foundation changes

Source package 0.3.0a2 in `.qualification/v0.3/native-package-03` passes the full
native gate and seven installed-package checks. The independent recorder binds
the wheel to its sources and recipes in
[native host foundation qualification](NATIVE_HOST_FOUNDATION_QUALIFICATION.json).

- Native Step reports RUNNING until it reaches its next parked trace boundary.
- Generated native child commands quote executable and argument paths, including
  filenames containing spaces and apostrophes. The original leading environment
  variable in configured executable paths is resolved before quoting.
- Existing context, service, child, recovery and reconnection gates still pass.

The earlier package-02 attempt was rejected by the gate because quoting prevented
the shipped `$SPELL_HOME` executable setting from expanding. Its exported failure
evidence is retained; it is not a qualified artifact.

## Open host acceptance work

The neutral IDE extension contract is committed as `541e906` in openbexi_ide and
passes 46 regression tests. Real Qt tests have exercised installed discovery,
Run, artifact export, breakpoint/stack display, variable editing and Step. Their
full workflow is not yet accepted: the original timer-based display buffer can
lose final output when a completed executor is closed immediately. A native
flush-before-terminal-notification fix and regression are next.

The JetBrains project contains a candidate settings page, actions, tool window
and XDebugger integration. Compilation, plugin verification and actual private
IntelliJ/PyCharm install/Run/Debug/remove tests are separate gates. No v0.3 host
release is accepted until all three hosts pass.

Ten obsolete host image references and three never-started mount probes were
removed during this milestone. The current host image, DSS image, unrelated
Docker resources and active user services were retained. Shared build-cache
layers may still occupy disk; image removal alone does not measure reclaimed
physical space.
