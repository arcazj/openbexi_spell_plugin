# Native host integration (v0.3 accepted)

The optional `openbexi-spell-host` wheel exposes the neutral OpenBEXI backend API
and a shared DAP relay. Its private Docker container installs the separate
original-source native SPELL wheel and connects through the original listener,
context and executor IPC. Project procedures use explicit `spell` imports.
The host interpreter does not receive a replacement SPELL language runtime.

The next host candidate fixes early console answers: the original runtime can
print a question before its input event arrives. The runner now retains those
lines and sends one answer per native prompt, preserving its prompt ID when
provided. It retains a final piped line without a newline, reports malformed
UTF-8 through normal cleanup, and bounds input to 64 KiB per line and 128 queued
lines / 256 KiB. Rejected or uncertain answers are never replayed.
The [console qualification record](../conformance/evidence/console_input_review.json)
binds the failing prior wheel, pipe regressions and actual IDE Run/Debug checks.
This candidate keeps the accepted 0.3.0 artifacts and final v0.6 gate separate.

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

Source package 0.3.0 in `.qualification/v0.3/native-package-05` passes the full
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

## Accepted host evidence

[The release manifest](HOST_QUALIFICATION.json) binds the final native image,
host wheel, JetBrains ZIP, source files and individual evidence reports. The
native image is `openbexi-spell-host:0.3.0`; its exact ID is in that manifest.
The neutral IDE extension passes 46 regression tests. Its installed Qt workflow
passes discovery, Run and artifact export, breakpoint/stack display, variable
editing, Step, Continue, prompt input, Stop, removal and ordinary Python Run.

Both actual PyCharm 2026.1.2 (261.24374.152) and IntelliJ IDEA 2026.2.3
(262.10968.63) pass the installed plugin workflow and separate removal restart.
Plugin Verifier accepts the ZIP on both builds; experimental APIs are exercised
and recorded. See [JetBrains installation and exact scope](JETBRAINS_HOST.md).

Ten native adapter cases qualify explicit imports and arguments, breakpoints,
stack/local edits (including nested folder paths), Step, exceptions, prompts,
pause/Stop, 1,200-message output order, EOF cleanup, launch rejection/retry and
malformed protocol rejection. Burst output and nested stack cases additionally
pass three repetitions each. Two independent pipe/status race tests and three
artifact-boundary tests cover bounded event pressure, stale status replies,
path traversal, links, duplicate archive members and unchanged source files.
The installed neutral CLI passes Run/export; managed EOF and process-tree loss
leave no owned native container behind.

Native IPC notifications retain receive order in the host bridge. While a
synchronous reply is pending, the adapter drains its bounded event queue, so
notification pressure cannot block that reply. Status revisions prevent an old
PAUSED query reply from overriding a newer RUNNING notification. Original
Display buffers flush before terminal status; output is complete before normal
artifact export and shutdown.

Fifteen obsolete host image references and three never-started mount probes were
removed during this phase, after checking ownership and container use. The
current host image, DSS image, unrelated Docker resources and active user
services were retained. Shared build-cache layers may still occupy disk; image
removal alone does not measure reclaimed physical space.

Execution and Monitoring, operational DSS integration and durable shared-session
admission remain v0.4 gates. Full inventory conformance remains v0.5;
independent native rebuilds, upgrades and distribution remain v0.6.
