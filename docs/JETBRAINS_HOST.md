# JetBrains SPELL host

The `0.3.1-workspace.1` development candidate adds the procedure workspace
described below. It is separate from the paused v0.6 release qualification.

The installable ZIP adds **Tools → SPELL**, project runtime settings, a SPELL
tool window and a native XDebugger implementation. It requires a CPython 3.13
interpreter with `openbexi-spell-host` installed and a running Docker Desktop
Linux engine with the qualified `openbexi-spell-host:0.3.0` image.

Install the ZIP through **Settings → Plugins → gear → Install Plugin from Disk**
and restart. In **Settings → SPELL Runtime**, select the host interpreter and
image. Open a project procedure with explicit `spell` imports. Use **Run File
with SPELL** or **Debug File with SPELL**. Choose the SPELL breakpoint type in
the IDE's breakpoint settings for native line breakpoints.

## Python editor and package installation

The native SPELL runtime runs inside Docker. Installing the JetBrains ZIP does
not install a `spell` package in the project's ordinary Python interpreter.
The project Python SDK must point to an existing executable for package
installation and ordinary Python execution. If an old project environment was
removed, select the current project `.venv/Scripts/python.exe` in Python
Interpreter settings.

The workspace candidate adds **Tools → SPELL → Sync SPELL Editor Definitions**
(also available in **SPELL Runtime Settings**). It reads the configured native
image and generates editor-only `.pyi` definitions under
`.openbexi/editor/current`, with an immutable image ID and source hashes. The
plugin registers them as an indexing library, without adding an executable
replacement runtime or disabling Python inspections. Sync again after changing
the runtime image. Docker and the configured host interpreter must be available
for synchronization; already-generated definitions remain usable offline.

Mixed native/browser examples should import the bounded SDK by its own
`openbexi_spell` name in their fallback branch. Native `spell.lang` is a different
package and does not re-export that SDK's API.

## Procedure workspace candidate

The candidate follows the original GUI manual's procedure view and embedded
prompt workflow (sections 3.2.1, 3.2.6 and 5.4), using IntelliJ's light/dark theme,
clear spacing and native controls. **Tools → SPELL → Procedures** contains Run
and Debug; **Execution** contains the supported controls. **Procedure Workspace**
opens the bottom tool window. Run and Debug can use the selected editor even
when a tool window has focus.

The workspace shows session history with procedure, start date/time, mode and
result. **Code & results** pairs the captured procedure source with line number,
native timestamp, item, value and status. Results come from native notifications;
an unreported result stays blank. Double-click a row to navigate to its source.
The **Output** tab retains the session's console text. History is limited to the
current IDE session; exported native run files remain under `.openbexi/runs`.

Prompts appear within the selected procedure: choice buttons for Yes/No and
lists, text/number/date fields, and masked password input when requested by the
native prompt. **Commit** submits once to that exact prompt, **Reset** clears the
entry, and **Abort procedure** stops the owning run. Native validation, defaults,
timeouts and reminders remain authoritative. The ordinary console input path is
also available. This local Development interface does not add the manual's
remote operational authority, mission monitoring or unsupported debugger actions.

Native per-line results and prompt-expiry updates require the matching workspace
runtime image. The locally tested candidate tag is
`openbexi-spell-host:workspace-candidate-20261017`; use the recorded immutable
image ID from its qualification report for repeatable execution. The installed
0.3.0 runtime is retained separately.

The [workspace candidate evidence](JETBRAINS_WORKSPACE_QUALIFICATION.json)
records the tested artifact, native image and scope. Local installation steps
and previews accompany the ZIP under `dist/workspace-candidate`.

On 2026-10-17 the installed user JAR was verified byte-for-byte against that
candidate, and the running IntelliJ startup log confirmed it was loaded. A
further private IntelliJ run passed all nine host checks on the final ZIP and
native image `sha256:0518192b4748bd4f5fa2cef5daa4ebe5b884735f559636bce5ba0b4119355c79`.
That development image also supplies source snapshots to the standalone IDE
through the host wheel `0.3.1.dev3` and its optional `openbexi/procedure`
presentation protocol. Its default Docker tag is `openbexi-spell-host:0.3.1-dev3`.
The user's explicit older workspace-image setting remains compatible and retained.
This delivery does not resume v0.6 or replace published conformance source hashes.

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
