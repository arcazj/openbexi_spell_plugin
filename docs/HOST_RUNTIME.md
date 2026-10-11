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

Source package 0.3.0a3 in `.qualification/v0.3/native-package-04` passes the full
native gate and seven installed-package checks. The independent recorder binds
the wheel to its sources and recipes in
[native host foundation qualification](NATIVE_HOST_FOUNDATION_QUALIFICATION.json).

- Native Step reports RUNNING until it reaches its next parked trace boundary.
- Generated native child commands quote executable and argument paths, including
  filenames containing spaces and apostrophes. The original leading environment
  variable in configured executable paths is resolved before quoting.
- Existing context, service, child, recovery and reconnection gates still pass.
- The original display buffer flushes before terminal status is sent. Its
  regression checks that the final Display arrives before FINISHED, so hosts
  can close a completed executor without losing its last output.

The earlier package-02 attempt was rejected by the gate because quoting prevented
the shipped `$SPELL_HOME` executable setting from expanding. Its exported failure
evidence is retained; it is not a qualified artifact.

## Open host acceptance work

The neutral IDE extension contract is committed as `541e906` in openbexi_ide and
passes 46 regression tests. Real Qt tests now pass installed discovery, Run,
artifact export, breakpoint/stack display, variable editing, Step, Continue,
native prompt input, Stop, removal and subsequent ordinary Python Run. Evidence
is `.qualification/v0.3/openbexi/6ce3aaa931bd485f80ce0de6e1db2add/result.json`,
with an inspected debugger screenshot and exact wheel/image identities.
Adapter boundary tests and the complete JetBrains workflow still gate v0.3.

The JetBrains project contains a candidate settings page, actions, tool window
and XDebugger integration. Its first ZIP passed binary compatibility verification
against PyCharm 261.23567.174 and IntelliJ IDEA 262.10968.63. A rebuilt candidate
removes the deprecated content-manager access; experimental debugger API use is
tracked against these exact hosts. Actual private install/Run/Debug/remove tests
remain separate gates. No v0.3 host
release is accepted until all three hosts pass.

Ten obsolete host image references and three never-started mount probes were
removed during this milestone. The current host image, DSS image, unrelated
Docker resources and active user services were retained. Shared build-cache
layers may still occupy disk; image removal alone does not measure reclaimed
physical space.
