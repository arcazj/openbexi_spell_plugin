# JetBrains SPELL host

The installable ZIP adds **Tools → SPELL**, project runtime settings, a SPELL
tool window and a native XDebugger implementation. It requires a CPython 3.13
interpreter with `openbexi-spell-host` installed and a running Docker Desktop
Linux engine with the qualified `openbexi-spell-host:0.3.0` image.

Install the ZIP through **Settings → Plugins → gear → Install Plugin from Disk**
and restart. In **Settings → SPELL Runtime**, select the host interpreter and
image. Open a project procedure with explicit `spell` imports. Use **Run File
with SPELL** or **Debug File with SPELL**. Choose the SPELL breakpoint type in
the IDE's breakpoint settings for native line breakpoints.

The debugger supports current-frame variables and edits, Step Into, Step Over,
pause, resume and Stop. Answer a native prompt in the debug console using the
option index shown there. Step Out, arbitrary expression evaluation and
conditional breakpoints are unavailable. Original runtime limitations remain
visible; this host does not translate a procedure to a replacement language.

Project files run in a private snapshot. New/changed files are retained under
`.openbexi/runs`; a procedure does not overwrite the editor's sources. See
[host runtime](HOST_RUNTIME.md) for limits, input/output and cleanup semantics.

Remove the plugin in **Settings → Plugins** and restart. The host wheel can be
removed separately with `python -m pip uninstall openbexi-spell-host`. Neither
installation changes the ordinary Python debugger. The optional extension
depends on the platform and XDebugger modules, so a separate JetBrains Python
plugin is not required to launch SPELL. Python language editing and ordinary
Python run configurations depend on the host's own Python support.

## Qualification

The local SDK folder names are older than their installed products. Read the
actual `product-info.json`: the final runtime tests use PyCharm 2026.1.2 build
261.24374.152 and IntelliJ IDEA 2026.2.3 build 262.10968.63 on Windows x64.
Earlier candidate tests also passed on PyCharm 2026.1.1 build 261.23567.174;
the locally installed SDK updated during qualification, and the final evidence
records the new build separately.
The native runtime inside Docker is Linux x86_64 / CPython 3.13.15.

`jetbrains/build.py --sdk SDK --output DIRECTORY` uses the installed SDK and its
compiler, targets Java 21 and produces a ZIP with deterministic archive metadata.
`jetbrains/qualify.py` builds a separate private test plugin; that test plugin is
never included in the shipped ZIP. Private configuration avoids importing the
user's settings. Only first-run UI tours are disabled. The test uses the actual
IDE process handlers, console input and XDebugger variables/modifiers and sessions.

The removal test retains the exact product/test JARs as evidence outside the
private plugin search path, then restarts the same project and checks that its
actions/tool window are absent. It opens a Python file and runs CPython through
the standard IDE execution console. This baseline does not claim to qualify
JetBrains' separate Python run-configuration implementation.

Plugin Verifier reports experimental session-builder APIs on the tested 261 SDK
and the expression-field capability API on 262. Their runtime paths are exercised
in both hosts. No deprecated API remains. Wider host versions and distribution
upgrade/reproducibility remain v0.6 gates. v0.3 acceptance is recorded in
[the release artifact manifest](HOST_QUALIFICATION.json). The hidden private
frames provide screenshots of source positions and plugin layout; debugger
variables and edits are verified through the actual XDebugger API. Those
screenshots do not establish complete rendered debugger-panel visual coverage.
