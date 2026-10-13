# Follow-up qualification runbook

This is a prepared sequence, **not an executed qualification or build freeze**.
The accepted source checkpoint is still 470 qualified / 293 open at `6f82c2c`.
Main's subsequent host-only fixes do not qualify the changed native composition.
Do not start this sequence until the parent reviews the final source-identity and
context-recovery donor, its checked composition and the final Git freeze.
Ranging and further child close/kill work remain separate.

## Bind the inputs before execution

Run from the frozen follow-up worktree. Record its full commit, clean source
status, raw and LF-normalized source hashes, donor report hashes and archive
hash. Finish all harness changes before collecting raw reports. Preserve every
failed attempt under its unique evidence directory; reruns use unchanged
oracles and deadlines unless a separately reviewed correction explains why.

Use these fixed bindings:

```powershell
$Python = 'C:/projects/openbexi_spell_plugin/.venv/Scripts/python.exe'
$Toolchain = 'openbexi-spell-toolchain:v06-a1f60eb52594'
$ToolchainId = 'sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2'
$HostDonor = Get-Content distribution/evidence/host-console-upgrade.json -Raw | ConvertFrom-Json
$HostWheel = $HostDonor.wheel.path
$HostWheelSha = 'd2b7cc41711d8ec7014e83babc6f2890f2bdf3c5668c6cffdf180d5ceeb1648d'
$PipeTests = (Resolve-Path host_plugin/tests/test_runner_input.py).Path
$PipeTestsSha = 'bd40a9225c41e384aab46c2696cb8c356d5dd045e6eb19a5562076aa88e0cc5a'
```

Verify the selected host wheel and retained test hashes before use. The host
donor already records two identical offline wheels and a complete installed
RECORD audit. It remains reusable only while all five package modules, metadata,
LICENSE and README match the donor. This is a CPython 3.13 profile; a
`py3-none-any` filename does not extend the tested interpreter/platform scope.

## Independent builds and installed image audits

Run each command only after the previous command and its JSON result pass.
Retain the printed unique evidence directory for each invocation; never select
an artifact by an unreviewed "latest" glob.

```powershell
& $Python -X utf8 distribution/qualify_driver_package.py --toolchain-image $Toolchain --toolchain-id $ToolchainId
& $Python -X utf8 distribution/rebuild.py --toolchain-image $Toolchain --toolchain-id $ToolchainId
```

Set `$Pair` to the second command's actual evidence directory and `$NativeWheel`
to the single wheel in `$Pair/a/distribution/wheels`. Require `result.json`
`passed=true`, both complete wheel bytes equal, all native/Python/composition
outputs equal, and the unchanged executor, context and installed-package gates.
The current gates are 23 executor tests, 10 context tests/25 lifecycles and eight
installed-package tests per build. A future reviewed donor may add tests; do not
silently remove or weaken existing gates. Both native builds use `--no-cache`
and `--network=none` against the exact pinned toolchain.

```powershell
& $Python -X utf8 distribution/build_images.py --native-wheel $NativeWheel --toolchain-image $Toolchain --toolchain-id $ToolchainId
```

Set `$Images` to this command's actual evidence directory. Bind the runtime
identities from its successful result, not from a historical tag:

```powershell
$Built = Get-Content "$Images/result.json" -Raw | ConvertFrom-Json
if (-not $Built.passed) { throw 'Fresh image qualification failed' }
$DssImage = $Built.driver_plugin.image
$HostImage = $Built.host_runtime.image
```

Require the new driver wheel SHA to equal both preflight wheel SHAs. The image
builder audits the selected native wheel, complete installed wheel RECORDs,
native artifacts, compiled IPC bridge, every native/Python/driver recipe stage
and the complete installed host Python source set. It must create fresh wheel
payloads without historical `/opt/*-patch` overlays. Archive these artifacts and
source snapshots before qualification. The old DSS image
`sha256:1fef3e691d8590079898a01cb7bddad9dbce8d9b4c4c29046a790e16af2a3342`
is a retained baseline only; no future candidate ID exists at preparation time.

## Native language regressions

After compilation ends, run the following unfiltered commands against the same
exact `$DssImage`. Record each returned raw result path. Coordinate one heavy
suite at a time: earlier fixture/feed stalls and HTTP timeouts remain retained,
and concurrent compilation would make timing observations harder to interpret.
Every command explicitly supplies `--image`; runner defaults are historical
development tags. Each runner verifies its installed provenance capture.

| Suggested owner | Command after `& $Python -X utf8` | Existing raw checks/scenarios |
| --- | --- | ---: |
| Composition | `conformance/run_data_files.py data --image $DssImage` | 24 |
| Composition | `conformance/run_data_files.py files --image $DssImage` | 36 |
| Composition | `conformance/run_data_race.py --image $DssImage` | 4 CAS competitions |
| Composition | `conformance/run_flow.py --image $DssImage` | 36 checks |
| Composition | `conformance/run_silence.py --image $DssImage` | 4 |
| Root | `conformance/run_resource.py --image $DssImage` | 12 |
| Root | `conformance/run_database_import.py --image $DssImage` | 16 |
| Root | `conformance/run_user_database.py --image $DssImage` | 20 + 2 real prompt scenarios |
| Root | `conformance/run_dta.py --image $DssImage` | 68 |
| Root | `conformance/run_ui.py --image $DssImage` | 62 |
| Root | `conformance/run_dta_edit.py --image $DssImage` | 64 dictionary IPC |
| Distribution | `conformance/run_native.py --image $DssImage` | 168 TIME |
| Distribution | `conformance/limit_run.py --image $DssImage` | 79 |
| Distribution | `conformance/notification_run.py --image $DssImage` | 16 |
| Python | `conformance/run_obs.py --image $DssImage` | 189 |
| Python | `conformance/run_cmd.py --image $DssImage` | 54 |
| Python | `conformance/run_python.py --image $DssImage` | 488 |
| Python | `conformance/run_common.py --image $DssImage` | 44 |
| Python | `conformance/run_events.py --image $DssImage` | 8 |
| Python | `conformance/run_scheduler.py --image $DssImage` | 9 |
| Python | `conformance/run_value_units.py --image $DssImage` | 38 |
| Distribution | `conformance/scdb_run.py --image $DssImage` | 26 |
| Python | `conformance/run_timing.py --image $DssImage` | 36 |
| Python | `conformance/run_send_verify.py --image $DssImage` | 18 |

Do not substitute imported-Python assertions for traced main-procedure checks,
or sequential compare-and-set checks for the competing-executor race. PY's
`checkpoint_claim:false` and the unsupported legacy cases remain explicit.

## Recorder and recovery

Run the existing standalone controls and native IPC error controls:

```powershell
& $Python -X utf8 conformance/checkpoint_error_run.py --image $DssImage
& $Python -X utf8 conformance/checkpoint_error_run.py --image $DssImage --case nested-unwind --case finally-unwind --case replace-error --case recursive-unwind --case repeated-catch
& $Python -X utf8 conformance/checkpoint_error_run.py --image $DssImage --ipc --mode DISABLED
```

These yield 24 ordinary, 20 expanded and four IPC error controls. Keep the
original synchronous frame-ownership and exceptional RETURN guards. The report
uses `$Pair/a/native/executor-runtime.json` and `executor-build.json` through
`--integrated-gate-dir`; do not run the overlay-only `checkpoint_error_gate.py`
on a fresh installed image or fabricate its `/out` and patch directories.

**Pending:** the independently demonstrated `main#1` checkpoint source identity
and obsolete WSS/WSD recovery lookup need their qualified donor, composition
preimages and actual kill/reopen controls. Append the donor's exact unfiltered
runner commands here before freeze. The four DISABLED IPC controls do not prove
warmstart. Existing retained blocker reports remain historical counterexamples;
do not turn their absence from a new suite into an acceptance claim.

## Installed host client, real native adapter and IDE workflows

Use a private CPython 3.13 environment with the exact `$HostWheel` installed and
the separately selected neutral IDE/runtime wheel. Record every wheel SHA,
installed member audit, interpreter identity and IDE commit/artifact identity.
`$InstalledPython` names that environment; `$Ide` names the reviewed IDE source
checkout; `$PreviousHostWheel` is the retained accepted 0.3.0 artifact. All
outputs below must be new, explicitly selected directories.

```powershell
& $Python -X utf8 -m unittest discover -s host_runtime/tests -v
& $Python -X utf8 scripts/qualify_host_adapter.py --image $DssImage --output $NativeHostOutput
& $Python -X utf8 scripts/qualify_child_prompts.py --image $DssImage --output $ChildPromptOutput
& $InstalledPython -I scripts/qualify_host_lifecycle.py --interpreter $InstalledPython --image $DssImage --wheel $HostWheel --wheel-sha256 $HostWheelSha
& $Python -X utf8 scripts/qualify_host_upgrade.py --ide $Ide --wheel $HostWheel --previous-wheel $PreviousHostWheel --image $DssImage
```

The local host tests currently have 21 checks. Native adapter qualification has
14 tests, with two additional actual successive/overlapping child prompt tests.
The lifecycle runner now checks its CLI export image and live container image
for EOF/process-tree loss, plus the exact installed host bytes before and after.
Run it without sibling owned-container creation; ambiguous ownership fails.
The actual Qt upgrade checks PluginManager replacement, native Run/Debug child
answers, removal, ordinary Python and project/preferences preservation. Its
current harness imports the selected IDE source; record that scope honestly.
Repeat adapter/lifecycle tests with `$HostImage` if claiming the standalone host
image as a separately qualified delivery profile.

Installed IDE and JetBrains delivery remain separate actual artifact workflows:

```powershell
& $Python -X utf8 distribution/openbexi_workflows.py --ide $Ide --ide-wheel $IdeWheel --host-wheel $HostWheel --image $DssImage
& $Python -X utf8 distribution/host_workflows.py --sdk $JetBrainsSdk --plugin $JetBrainsZip --interpreter $InstalledPython --image $DssImage --output $JetBrainsOutput
```

The first verifies installed IDE origin and actual manifest images; it currently
installs pinned desktop dependencies from the index, so it is not an offline
installation claim. The second injects the exact image only into the private
test settings and checks actual installed/removal workflows. Supply retained
artifact hashes and supported host/platform profiles; do not infer macOS or a
fresh-Windows-machine test from source IDE automation. The browser/VNC window
close and console scroll checks remain separate: browser creation was attempted
but the available computer-use backend reported the browser unavailable.

For the installed shared driver acceptance, use a separate headless private
environment containing the selected IDE/runtime, shared, host and composed DSS
driver wheels plus the locked test dependencies (no PySide6). The existing
`scripts/qualify_driver_installed.py` checks origins under its interpreter prefix:

```powershell
$env:OPENBEXI_NATIVE_TEST_IMAGE = $DssImage
& $HeadlessPython -I scripts/qualify_driver_installed.py --output $DriverInstalledOutput --ide $Ide --plugin (Get-Location).Path
Remove-Item Env:OPENBEXI_NATIVE_TEST_IMAGE
```

The copied IDE `native_driver_acceptance.py` consumes this explicit image
variable. Bind the exact copied test sources and restore any pre-existing
environment value when orchestrating this command. Historical
`record_host_qualification.py` / `record_driver_qualification.py` hard-code old
release images; they are not valid final recorders for this candidate.

## Windows and Linux installed pipe qualification

The new `scripts/qualify_host_input.py` runs the retained 16 FIFO/EOF oracles with
an independently controlled DAP peer. It changes only their checked `HOST_SOURCE`
assignment in a retained copy, pointing child processes at the exact installed
site. The source oracles remain byte-identical otherwise. Before and after the
run it verifies the full wheel RECORD, every installed payload byte, the complete
package Python source set and private import origin. It records actual OS,
CPython, package version, original/adapted/harness hashes, JUnit and case journals.
This proves client transport, separate from the native adapter's 14+2 tests.

```powershell
& $InstalledPython -I scripts/qualify_host_input.py --wheel $HostWheel --wheel-sha256 $HostWheelSha --tests $PipeTests --tests-sha256 $PipeTestsSha --expected-platform Windows --output $WindowsPipeOutput
```

Run the same command using the private Linux CPython 3.13 interpreter, changing
only paths and `--expected-platform Linux`. The helper performs no installation,
network or Docker operation. Create that private environment inside a separately
retained Linux qualification container after the build hold is released; copy
the wheel, exact test source and helper, without checkout package imports. Use
the pinned runtime and a hash-locked offline test wheelhouse:

```sh
python -m venv /qualification/interpreter
/qualification/interpreter/bin/python -I -m pip install --no-index --no-deps /inputs/openbexi_spell_host-0.3.1.dev1-py3-none-any.whl
/qualification/interpreter/bin/python -I -m pip install --no-index --find-links /test-wheelhouse --require-hashes -r /inputs/pipe-test-requirements.lock
/qualification/interpreter/bin/python -I /inputs/qualify_host_input.py --wheel /inputs/openbexi_spell_host-0.3.1.dev1-py3-none-any.whl --wheel-sha256 d2b7cc41711d8ec7014e83babc6f2890f2bdf3c5668c6cffdf180d5ceeb1648d --tests /inputs/test_runner_input.py --tests-sha256 bd40a9225c41e384aab46c2696cb8c356d5dd045e6eb19a5562076aa88e0cc5a --expected-platform Linux --output /qualification/linux-pipes
```

The dependency lock/wheelhouse must be prepared and hashed before this command;
it must install pytest 8.4.2 and its complete dependencies. Its availability has
not yet been established. Windows and Linux installed runs of this new helper
are **not executed** at preparation time. Fifteen fixture-based validator tests
pass; those tests do not qualify either runtime platform.

## Reports, coverage and final review

Retain raw bytes, SHA256, byte length, native transcripts, source snapshots and
LF-normalized input hashes. Do not rewrite raw reports to satisfy a recorder.
Resolve historical baseline paths from the committed donor reports and verify
their recorded hashes before reuse. `$Raw` below is a map of actual new raw
report paths, not a historical path or guessed UUID.

Run the strict standard qualifiers after all contributing raw suites pass:

- `obs_report.py`, `cmd_report.py`, `events_report.py`, `scheduler_report.py`,
  `value_units_report.py`, `timing_report.py` and `send_verify_report.py` each take
  their matching raw path as a positional argument under `conformance/`.
- `limit_report.py $Raw.limit $Raw.obs --baseline $OldLimitBaseline --numeric_failure $OldLimitNumeric --range_failure $OldLimitRange`
  requires same-image OBS; use `--retained_failure` for preserved later failures.
- `notification_report.py --result $Raw.notification --baseline $OldNotifyBaseline`.
- `resource_report.py $Raw.resource`.
- `database_import_report.py $Raw.database --baseline $OldDatabaseBaseline --files $Raw.files --data $Raw.data`.
- `user_database_report.py $Raw.user_database --baseline $OldUserDatabaseBaseline --files $Raw.files --data $Raw.data`.
- `scdb_report.py $Raw.scdb --baseline $OldScdbBaseline --database-import $Raw.database --checkpoint-gap $OldScdbGap --policy-oracle-correction $OldScdbOracle`.
- `checkpoint_error_report.py --baseline $OldRecorderBaseline --audit $OldRecorderAudit --candidate $Raw.recorder --expanded $Raw.recorder_expanded --ipc-baseline $OldIpcErrors --ipc-candidate $Raw.recorder_ipc --ipc-blocker $OldIpcBlocker --integrated-gate-dir "$Pair/a/native" --output conformance/evidence/checkpoint_error.json`.

The last recorder's blocker description must be reconciled with any separately
qualified source/context recovery donor before final recording. Similarly,
`database_import_report.py` still describes the historical SCDB write gap; its
read-only scope text must defer to the separately qualified SCDB report after
fresh composition, without broadening its own read/import claims. These are
identified recorder text assumptions, not permission to bypass their assertions.

DATA/FILES/race/FLOW/silence/DTA/UI/IPC/TIME/PY/COMMON raw results are already in
the canonical report shape; promote only after full input verification, retaining
raw hashes and declared scope. Keep PY `checkpoint_claim:false`. Scheduler's
recorder performs checked observation-reference conversion; keep the strict
generic dependency-cycle gate unchanged. Only OBS and selected other qualifiers
accept a custom output; most write canonical evidence directly, so allocate one
owner per report and avoid simultaneous staging.

Refresh coverage only for independently supported positive/boundary/failure/
recovery dimensions on the exact installed sources. Do not import donor counts.
Then run `conformance/check.py --output $GateOutput` and the source-bound report
checks against a fresh Git-index checkout. Exit 1 with a complete valid report
means clauses remain open; an exception, stale hash or unsupported dependency
is a failed checkpoint, not the expected open-row result. The 763-clause inventory
and release flags remain unchanged until their real gates pass. At most the two
SCDB rows and Wait row are currently proposed by these added language tranches;
hundreds of clauses still block complete v0.5/v0.6 release acceptance.

Commit the reviewed checkpoint in the isolated branch. Main now contains
equivalent host-only commits, so integration is an ordinary reviewed merge;
compare final host/package/recipe bytes and rerun source binding checks after
merge. Do not rebuild or relabel the accepted historical artifacts.
