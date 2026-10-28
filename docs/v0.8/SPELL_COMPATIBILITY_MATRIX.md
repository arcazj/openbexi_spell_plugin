Current executable `c9ec5c5ec8338fe1530bc57ebb30fbb6ba410034`; paired IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. [Fresh input reconciliation](evidence/compatibility-inputs-c9ec5c5e-20261028.json) verifies555top-level bindings (546match/9drift) and47unchanged historical reports. All763 current native requirements remain NOT_FRESHLY_QUALIFIED;57 historical capture hashes remain unresolved. The following snapshots are historical.

Dev77 changes measured private bridge ownership and requires fresh exact-source acceptance. The reconciliation below is the preserved dev76 input checkpoint; all 763 current native requirements and 57 unresolved historical captures remain open.

Current executable `3b18313899ebe07d84b8e98b86c8f9b5020c3263`; paired IDE `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. [Fresh immutable input reconciliation](evidence/compatibility-inputs-3b183138-20261028.json) checks all 555 top-level bindings and 47 unchanged historical reports. All 763 current native requirements remain NOT_FRESHLY_QUALIFIED; 57 historical capture hashes remain unresolved. Bounded dev76 lifecycle/driver/memory tests do not replace these requirements. The following snapshots are historical.

Dev76 adds a measured native request-identity ownership change and requires fresh qualification. The exact input reconciliation below remains bound to the last hosted dev75 executable; all 763 current requirements and 57 unresolved historical capture hashes remain open.

# SPELL compatibility matrix — v0.8 qualification record

All 763 original requirement IDs and their four historical evidence dimensions are preserved. This matrix does not promote those historical results to the current v0.8 native candidate. Every row still requires fresh applicable native acceptance at the exact SPELL and IDE identities.

Candidate under qualification: `3c1951ef0365ed4c1dc4dc56f39ffce0bca2e5a0`; companion IDE: `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`. Historical coverage remains unchanged. The 241 portable tests and lifecycle/memory/storage components are separate scopes.

The [machine-readable matrix](evidence/compatibility-matrix-20261027.json) contains every positive, boundary, failure and recovery reference, report hashes and current top-level input comparisons. Nested raw-capture recovery is tracked separately in [the recovery record](COMPATIBILITY_ARCHIVE_RECOVERY.md); matching top-level inputs alone cannot qualify a report or missing raw capture.

| Kind | Requirements | Fresh v0.8 native status |
|---|---:|---|
| Constant | 66 | Not freshly qualified |
| Control | 3 | Not freshly qualified |
| DataContainer | 2 | Not freshly qualified |
| Database | 3 | Not freshly qualified |
| Example | 195 | Not freshly qualified |
| Function | 70 | Not freshly qualified |
| FunctionAliasCandidate | 2 | Not freshly qualified |
| KeywordArgument | 6 | Not freshly qualified |
| Method | 67 | Not freshly qualified |
| Modifier | 72 | Not freshly qualified |
| Operator | 31 | Not freshly qualified |
| Outcome | 9 | Not freshly qualified |
| SourceErratum | 7 | Not freshly qualified |
| SourceSection | 140 | Not freshly qualified |
| State | 3 | Not freshly qualified |
| Syntax | 60 | Not freshly qualified |
| Type | 27 | Not freshly qualified |

| Historical report | Top-level inputs | Missing or changed inputs |
|---|---:|---:|
| [child_arguments.json](../../conformance/evidence/child_arguments.json) | 131 | 7 |
| [child_execution.json](../../conformance/evidence/child_execution.json) | 138 | 7 |
| [child_policy.json](../../conformance/evidence/child_policy.json) | 141 | 7 |
| [child_returns.json](../../conformance/evidence/child_returns.json) | 135 | 7 |
| [cmd.json](../../conformance/evidence/cmd.json) | 136 | 4 |
| [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | 172 | 7 |
| [common-silence.json](../../conformance/evidence/common-silence.json) | 121 | 4 |
| [common.json](../../conformance/evidence/common.json) | 122 | 4 |
| [data-race.json](../../conformance/evidence/data-race.json) | 119 | 4 |
| [data.json](../../conformance/evidence/data.json) | 124 | 4 |
| [database_import.json](../../conformance/evidence/database_import.json) | 123 | 4 |
| [database_scope.json](../../conformance/evidence/database_scope.json) | 124 | 4 |
| [database_values_composed.json](../../conformance/evidence/database_values_composed.json) | 138 | 5 |
| [dta.json](../../conformance/evidence/dta.json) | 125 | 4 |
| [events.json](../../conformance/evidence/events.json) | 138 | 4 |
| [files.json](../../conformance/evidence/files.json) | 124 | 4 |
| [flow.json](../../conformance/evidence/flow.json) | 123 | 4 |
| [legacy_compare_composed.json](../../conformance/evidence/legacy_compare_composed.json) | 129 | 4 |
| [limit.json](../../conformance/evidence/limit.json) | 137 | 4 |
| [notification.json](../../conformance/evidence/notification.json) | 126 | 4 |
| [obs.json](../../conformance/evidence/obs.json) | 137 | 4 |
| [predefined_containers.json](../../conformance/evidence/predefined_containers.json) | 145 | 7 |
| [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | 134 | 7 |
| [prompt_timeout.json](../../conformance/evidence/prompt_timeout.json) | 122 | 4 |
| [python.json](../../conformance/evidence/python.json) | 121 | 4 |
| [python_sections.json](../../conformance/evidence/python_sections.json) | 162 | 5 |
| [resource.json](../../conformance/evidence/resource.json) | 139 | 5 |
| [rng.json](../../conformance/evidence/rng.json) | 144 | 5 |
| [scdb.json](../../conformance/evidence/scdb.json) | 126 | 4 |
| [scheduler.json](../../conformance/evidence/scheduler.json) | 126 | 4 |
| [time.json](../../conformance/evidence/time.json) | 118 | 4 |
| [timing.json](../../conformance/evidence/timing.json) | 139 | 4 |
| [ui.json](../../conformance/evidence/ui.json) | 133 | 4 |
| [user_database.json](../../conformance/evidence/user_database.json) | 125 | 5 |
| [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | 291 | 8 |
| [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | 476 | 9 |
| [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | 139 | 4 |
| [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | 205 | 7 |
| [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | 172 | 7 |
| [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | 145 | 8 |
| [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | 221 | 8 |
| [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | 183 | 8 |
| [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | 192 | 7 |
| [value_units.json](../../conformance/evidence/value_units.json) | 139 | 4 |
| [wait_control.json](../../conformance/evidence/wait_control.json) | 142 | 7 |
| [wait_interval.json](../../conformance/evidence/wait_interval.json) | 127 | 7 |
| [wait_time.json](../../conformance/evidence/wait_time.json) | 128 | 7 |

| Requirement | Kind / package | Historical status and report | Current v0.8 native status |
|---|---|---|---|
| CMP-LRM244-CONSTANT-ACTION-ABORT — ABORT | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-CANCEL — CANCEL (action) | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-HANDLE — HANDLE | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-NOACTION — NOACTION | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-RECHECK — RECHECK | Constant / COMMON | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-REPEAT — REPEAT | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-RESEND — RESEND | Constant / COMMON | QUALIFIED: [events.json](../../conformance/evidence/events.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-RESUME — RESUME | Constant / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ACTION-SKIP — SKIP | Constant / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-EXECUTION-STATE-ABORTED — ABORTED | Constant / FLOW | QUALIFIED: [child_policy.json](../../conformance/evidence/child_policy.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-EXECUTION-STATE-ERROR — ERROR (child-procedure state) | Constant / FLOW | QUALIFIED: [child_policy.json](../../conformance/evidence/child_policy.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-EXECUTION-STATE-FINISHED — FINISHED | Constant / FLOW | QUALIFIED: [child_policy.json](../../conformance/evidence/child_policy.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-FILE-MODE-APPEND — APPEND | Constant / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-FILE-MODE-READ — READ | Constant / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-FILE-MODE-READ-WRITE — READ_WRITE | Constant / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-FILE-MODE-WRITE — WRITE | Constant / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ITEM-STATUS-ITEM-FAILED — ITEM_FAILED | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ITEM-STATUS-ITEM-PROGRESS — ITEM_PROGRESS | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-ITEM-STATUS-ITEM-SUCCESS — ITEM_SUCCESS | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-SELECTION-ACTIVE — ACTIVE | Constant / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-SELECTION-ALL — ALL | Constant / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-TYPE-HARDSOFT — HARDSOFT | Constant / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-TYPE-SPIKE — SPIKE | Constant / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-TYPE-STATUS — STATUS | Constant / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-LIMIT-TYPE-STEP — STEP (limit type) | Constant / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PRINT-FORMAT-PS — PS | Constant / COMMON | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PRINT-FORMAT-VECTOR — VECTOR | Constant / COMMON | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-ARGS — PROC["ARGS"] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-INPUT-DATA — PROC[INPUT_DATA] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-NAME — PROC["NAME"] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-OUTPUT-DATA — PROC[OUTPUT_DATA] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-PARENT — PROC["PARENT"] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-PREV-STEP — PROC["PREV_STEP"] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROC-KEY-STEP — PROC["STEP"] | Constant / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-ALPHA — ALPHA | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-CANCEL — CANCEL (prompt type) | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-DATE — DATE | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-LIST — LIST | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-NO — NO | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-NUM — NUM | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-OK — OK | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-OK-CANCEL — OK_CANCEL | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-YES — YES | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PROMPT-TYPE-YES-NO — YES_NO | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-PYTHON-SENTINEL-NONE — None | Constant / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RADIX-BIN — BIN | Constant / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RADIX-DEC — DEC | Constant / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RADIX-HEX — HEX | Constant / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RADIX-OCT — OCT | Constant / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RANGING-STATE-CALIBRATING — CALIBRATING | Constant / DATA | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RANGING-STATE-ERROR — ERROR (ranging state) | Constant / UI | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RANGING-STATE-IDLE — IDLE | Constant / DATA | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-RANGING-STATE-RANGING — RANGING | Constant / DATA | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-SCOPE-GLOBAL — GLOBAL | Constant / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-SEVERITY-ERROR — ERROR (severity) | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-SEVERITY-INFORMATION — INFORMATION | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-SEVERITY-WARNING — WARNING | Constant / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-HOUR — HOUR | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-MINUTE — MINUTE | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-NOW — NOW | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-SECOND — SECOND | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-TODAY — TODAY | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-TOMORROW — TOMORROW | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-TIME-YESTERDAY — YESTERDAY | Constant / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-VALUE-FORMAT-ENG — ENG | Constant / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-CONSTANT-VALUE-FORMAT-RAW — RAW | Constant / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-CONTROL-WAITFOR-INTERRUPT — INTERRUPT | Control / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-CONTROL-WAITFOR-SKIP — SKIP (WaitFor command) | Control / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-CONTROL-WAITFOR-STEP — STEP (WaitFor command) | Control / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-DATA-CONTAINER-ARGS — ARGS | DataContainer / DATA | QUALIFIED: [predefined_containers.json](../../conformance/evidence/predefined_containers.json) | Not freshly qualified |
| CMP-LRM244-DATA-CONTAINER-IVARS — IVARS | DataContainer / DATA | QUALIFIED: [predefined_containers.json](../../conformance/evidence/predefined_containers.json) | Not freshly qualified |
| CMP-LRM244-DATABASE-GDB — GDB | Database / DATA | QUALIFIED: [database_import.json](../../conformance/evidence/database_import.json) | Not freshly qualified |
| CMP-LRM244-DATABASE-PROC — PROC | Database / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-DATABASE-SCDB — SCDB | Database / DATA | QUALIFIED: [scdb.json](../../conformance/evidence/scdb.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-ADJUSTLIMITS-NAME — Condition-based limit-adjustment callable conflict | SourceErratum / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-HANDLEERROR-DEFAULT — HandleError default conflict | SourceErratum / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-LIMIT-KEY-LOHIGH — LoHigh/LoYel limit-key conflict | SourceErratum / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-PROMPT-FAILURE-MODIFIERS — Operation-failure modifier conflict | SourceErratum / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-USER-ACTION-DISABLE — User-action disable callable conflict | SourceErratum / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-VERIFY-FALSE-ACTION-MODIFIER — Verify false-action modifier conflict | SourceErratum / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-ERRATUM-VERIFY-ONFALSE-DEFAULT — Verify OnFalse default conflict | SourceErratum / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-001 — Example 1: indentation | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-002 — Example 2: splitting character strings | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-003 — Example 3: splitting with comma | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-004 — Example 4: splitting code with backslash | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-005 — Example 5: single line comments in python | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-006 — Example 6: multi-line comments in python | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-007 — Example 7: variable types in Python | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-008 — Example 8: lists and dictionaries | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-009 — Example 9: arithmetic expressions | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-010 — Example 10: boolean expressions | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-011 — Example 11: string expressions | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-012 — Example 12: substrings | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-013 — Example 13: conditional statements | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-014 — Example 14: for loop statements | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-015 — Example 15: while loop statements | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-016 — Example 16: user defined function example | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-017 — Example 17: arguments by reference | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-018 — Example 18: module (procedure) import | Example / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-019 — Example 19: SPELL function with keyword parameters | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-020 — Example 20: changing defaults for a function in a procedure | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-021 — Example 21: failure action configuration | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-022 — Example 22: automatic failure processing | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-023 — Example 23: reacting on function result | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-024 — Example 24: special error handling | Example / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-025 — Example 25: silent execution | Example / COMMON | QUALIFIED: [common-silence.json](../../conformance/evidence/common-silence.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-026 — Example 26: using NOW in a loop | Example / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-027 — Example 27: using NOW in a loop (2) | Example / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-028 — Example 28: modifying the output time format | Example / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-029 — Example 29: time management | Example / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-030 — Example 30: obtain engineering TM values | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-031 — Example 31: waiting for updates | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-032 — Example 32: waiting for updates with timeout | Example / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-033 — Example 33: acquisition of raw value | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-034 — Example 34: acquisition extended information | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-035 — Example 35: verify a single TM value | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-036 — Example 36: verify a single TM value in raw format | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-037 — Example 37: verify using next update and timeout | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-038 — Example 38: verify with tolerance | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-039 — Example 39: using Verify in a test statement | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-040 — Example 40: getting failure information | Example / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-041 — Example 41: getting failure information (output) | Example / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-042 — Example 42: do nothing on False | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-043 — Example 43: do not prompt the user and take the SKIP action | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-044 — Example 44: repeat verification if it fails, 2 times | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-045 — Example 45: delay the verification | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-046 — Example 46: ignoring string value case | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-047 — Example 47: multiple verifications | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-048 — Example 48: multiple verifications and configurations | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-049 — Example 49: multiple verifications and configurations (2) | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-050 — Example 50: verifications with multiple values | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-051 — Example 51: comparing telemetry parameters | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-052 — Example 52: comparing telemetry parameters (wrong code) | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-053 — Example 53: comparing telemetry parameters with items | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-054 — Example 54: comparing telemetry parameters with lists of items | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-055 — Example 55: building a simple command | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-056 — Example 56: building a simple command | Example / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-057 — Example 57: building a simple command | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-058 — Example 58: command arguments | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-059 — Example 59: building a command with arguments | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-060 — Example 60: sending a simple command | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-061 — Example 61: time-tagged commands | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-062 — Example 62: commands with a release time | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-063 — Example 63: load only command | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-064 — Example 64: confirm command execution | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-065 — Example 65: confirm critical command execution | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-066 — Example 66: commands with arguments | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-067 — Example 67: sending sequence | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-068 — Example 68: sending a group of commands | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-069 — Example 69: sending a group of commands with arguments | Example / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-070 — Example 70: sending a list of commands grouped | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-071 — Example 71: sending a list of commands blocked | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-072 — Example 72: sending with timeout | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-073 — Example 73: additional information | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-074 — Example 74: sending with delayed release | Example / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-075 — Example 75: sending and verifying | Example / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-076 — Example 76: sending, verifying and adjusting limits | Example / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-077 — Example 77: complex send | Example / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-078 — Example 78: wait relative time condition | Example / OBS | QUALIFIED: [wait_time.json](../../conformance/evidence/wait_time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-079 — Example 79: wait absolute time condition | Example / OBS | QUALIFIED: [wait_time.json](../../conformance/evidence/wait_time.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-080 — Example 80: wait telemetry condition | Example / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-081 — Example 81: wait telemetry condition with maximum delay | Example / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-082 — Example 82: simple interval | Example / OBS | QUALIFIED: [wait_interval.json](../../conformance/evidence/wait_interval.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-083 — Example 83: complex interval | Example / OBS | QUALIFIED: [wait_interval.json](../../conformance/evidence/wait_interval.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-084 — Example 84: injecting parameters | Example / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-085 — Example 85: reading all limit definitions | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-086 — Example 86: complex limit definitions for HARDSOFT limit | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-087 — Example 87: complex limit definitions for STATUS limit | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-088 — Example 88: reading applicable limit definitions | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-089 — Example 89: reading limit definitions by identifier | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-090 — Example 90: reading limit definitions from status parameters | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-091 — Example 91: reading single data from limit definitions | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-092 — Example 92: reading single data from limit definitions (2) | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-093 — Example 93: reading single data from limit definitions (3) | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-094 — Example 94: modifying limit definitions | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-095 — Example 95: modifying limit definitions (2) | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-096 — Example 96: modifying limit definitions (3) | Example / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-097 — Example 97: modifying limit definitions (4) | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-098 — Example 98: modifying limit data for Status parameter | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-099 — Example 99: modifying limit definitions (5) | Example / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-100 — Example 100: modifying limit definitions for SPIKE limit | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-101 — Example 101: modifying limit definitions for STEP limit | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-102 — Example 102: enabling and disabling alarms | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-103 — Example 103: automatic limit adjustment for HARDSOFT parameter | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-104 — Example 104: automatic limit adjustment for STATUS parameter | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-105 — Example 105: loading limits from file | Example / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-106 — Example 106: restoring limits | Example / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-107 — Example 107: checking alarm status | Example / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-108 — Example 108: display messages | Example / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-109 — Example 109: sending notifications | Example / UI | QUALIFIED: [notification.json](../../conformance/evidence/notification.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-110 — Example 110: event messages | Example / UI | QUALIFIED: [events.json](../../conformance/evidence/events.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-111 — Example 111: change configuration value | Example / FILES | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-112 — Example 112: retrieve configuration value | Example / FILES | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-113 — Example 113: variable mappings with ground database | Example / FILES | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-114 — Example 114: types of prompt | Example / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-115 — Example 115: default prompt list | Example / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-116 — Example 116: custom list with index | Example / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-117 — Example 117: custom list with values | Example / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-118 — Example 118: default value for prompt | Example / UI | QUALIFIED: [prompt_timeout.json](../../conformance/evidence/prompt_timeout.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-119 — Example 119: opening displays | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-120 — Example 120: opening a workspace | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-121 — Example 121: specifying the host | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-122 — Example 122: specifying the monitor | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-123 — Example 123: specifying time span | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-124 — Example 124: printing displays | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-125 — Example 125: display format | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-126 — Example 126: closing displays | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-127 — Example 127: closing workspaces | Example / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-128 — Example 128: step definitions | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-129 — Example 129: step and go-to | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-130 — Example 130: displaying step information | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-131 — Example 131: pausing, aborting and finishing | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-132 — Example 132: setting user actions | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-133 — Example 133: enabling/disabling user actions | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-134 — Example 134: removing user actions | Example / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-135 — Example 135: spacecraft database | Example / DATA | QUALIFIED: [database_import.json](../../conformance/evidence/database_import.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-136 — Example 136: spacecraft database keys | Example / DATA | QUALIFIED: [database_import.json](../../conformance/evidence/database_import.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-137 — Example 137: checking spacecraft database keys | Example / DATA | QUALIFIED: [database_import.json](../../conformance/evidence/database_import.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-138 — Example 138: loading a manoeuvre file | Example / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-139 — Example 139: ground database mappings | Example / DATA | QUALIFIED: [database_import.json](../../conformance/evidence/database_import.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-140 — Example 140: using database mappings | Example / DATA | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-141 — Example 141: using database mappings (2) | Example / DATA | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-142 — Example 142: procedure database | Example / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-143 — Example 143: loading an user database file | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-144 — Example 144: creating an user database file | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-145 — Example 145: saving an user database file | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-146 — Example 146: modifying a database value | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-147 — Example 147: database data example | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-148 — Example 148: database data example manipulation | Example / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-149 — Example 149: creating a data container | Example / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-150 — Example 150: declare a variable in a data container | Example / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-151 — Example 151: starting a sub-procedure | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-152 — Example 152: procedure library example | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-153 — Example 153: folder priorities | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-154 — Example 154: starting procedure using priorities | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-155 — Example 155: starting procedure overriding priorities | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-156 — Example 156: starting a sub-procedure in non-blocking mode | Example / FLOW | QUALIFIED: [child_execution.json](../../conformance/evidence/child_execution.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-157 — Example 157: starting a sub-procedure in hidden mode | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-158 — Example 158: starting a sub-procedure in manual mode | Example / FLOW | QUALIFIED: [child_execution.json](../../conformance/evidence/child_execution.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-159 — Example 159: starting a sub-procedure (complex) | Example / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-160 — Example 160: starting a sub-procedure with arguments | Example / FLOW | QUALIFIED: [child_arguments.json](../../conformance/evidence/child_arguments.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-161 — Example 161: accessing procedure arguments | Example / FLOW | QUALIFIED: [child_arguments.json](../../conformance/evidence/child_arguments.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-162 — Example 162: opening a file | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-163 — Example 163: opening a file | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-164 — Example 164: writing to a file | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-165 — Example 165: reading file lines | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-166 — Example 166: reading directory contents | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-167 — Example 167: create a File instance | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-168 — Example 168: deleting files and directories | Example / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-169 — Example 169: enabling or disabling the ranging system | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-170 — Example 170: starting ranging activities | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-171 — Example 171: starting dual ranging activities | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-172 — Example 172: aborting ranging activities | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-173 — Example 173: setting and getting baseband configurations | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-174 — Example 174: getting BBE/Antennae information | Example / SPECIAL | QUALIFIED: [rng.json](../../conformance/evidence/rng.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-175 — Example 175: calibrate the ranging system | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-176 — Example 176: status of the ranging system | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-177 — Example 177: setting shared data values | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-178 — Example 178: setting shared data values (2) | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-179 — Example 179: setting shared data values (3) | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-180 — Example 180: setting shared data values in a scope | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-181 — Example 181: creating a scope | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-182 — Example 182: test and set shared data values | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-183 — Example 183: test and set shared data values (2) | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-184 — Example 184: getting shared data values | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-185 — Example 185: getting shared data values (2) | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-186 — Example 186: getting shared data values (3) | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-187 — Example 187: getting shared data information | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-188 — Example 188: clearing shared data values | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-189 — Example 189: clearing shared data scopes | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-190 — Example 190: clearing shared data scopes | Example / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-191 — Example 191: generate memory reports | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-192 — Example 192: compare memory images | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-193 — Example 193: compare memory images on limited data ranges | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-194 — Example 194: extract memory values | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-EXAMPLE-195 — Example 195: extract TM/TC database values | Example / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ABORT — Abort | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ABORTRANGING — AbortRanging | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ADDSHAREDDATASCOPE — AddSharedDataScope | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-BUILDTC — BuildTC | Function / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-ADJUSTLIMITS — AdjustLimits | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-AND — AND | Function / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-CLEARSHAREDDATASCOPE — ClearSharedDataScope | FunctionAliasCandidate / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-COMPAREMEMORYIMAGES — CompareMemoryImages | FunctionAliasCandidate / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-FILE — File | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-GOTO — Goto | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-OR — OR | Function / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CANDIDATE-STEP — Step | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CHANGELANGUAGECONFIG — ChangeLanguageConfig | Function / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CLEARSHAREDDATA — ClearSharedData | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CLEARSHAREDDATASCOPES — ClearSharedDataScopes | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CLOSEDISPLAY — CloseDisplay | Function / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CLOSEFILE — CloseFile | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CLOSEWORKSPACE — CloseWorkspace | Function / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-COMPAREMEMORYIMAGE — CompareMemoryImage | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-CREATEDICTIONARY — CreateDictionary | Function / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DELETEFILE — DeleteFile | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISABLEALARM — DisableAlarm | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISABLERANGING — DisableRanging | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISABLEUSERACTION — DisableUserAction | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISMISSUSERACTION — DismissUserAction | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISPLAY — Display | Function / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-DISPLAYSTEP — DisplayStep | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ENABLEALARM — EnableAlarm | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ENABLERANGING — EnableRanging | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ENABLEUSERACTION — EnableUserAction | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-EVENT — Event | Function / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-FINISH — Finish | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GENERATEMEMORYREPORT — GenerateMemoryReport | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETANTENNANAMES — GetAntennaNames | Function / SPECIAL | QUALIFIED: [rng.json](../../conformance/evidence/rng.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETBASEBANDCONFIG — GetBasebandConfig | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETBASEBANDNAMES — GetBasebandNames | Function / SPECIAL | QUALIFIED: [rng.json](../../conformance/evidence/rng.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETLIMITS — GetLimits | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETRANGINGSTATUS — GetRangingStatus | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETRESOURCE — GetResource | Function / FILES | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETSHAREDDATA — GetSharedData | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETSHAREDDATAKEYS — GetSharedDataKeys | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETSHAREDDATASCOPES — GetSharedDataScopes | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-GETTM — GetTM | Function / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-ISALARMED — IsAlarmed | Function / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-LOADDICTIONARY — LoadDictionary | Function / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-LOADLIMITS — LoadLimits | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-MEMORYLOOKUP — MemoryLookup | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-NOTIFY — Notify | Function / UI | QUALIFIED: [notification.json](../../conformance/evidence/notification.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-OPENDISPLAY — OpenDisplay | Function / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-OPENFILE — OpenFile | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-OPENWORKSPACE — OpenWorkspace | Function / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-PAUSE — Pause | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-PRINTDISPLAY — PrintDisplay | Function / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-PROMPT — Prompt | Function / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-READDIRECTORY — ReadDirectory | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-READFILE — ReadFile | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-RESTORENORMALLIMITS — RestoreNormalLimits | Function / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SAVEDICTIONARY — SaveDictionary | Function / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SEND — Send | Function / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETBASEBANDCONFIG — SetBasebandConfig | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETGROUNDPARAMETER — SetGroundParameter | Function / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETLIMITS — SetLimits | Function / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETRESOURCE — SetResource | Function / FILES | QUALIFIED: [resource.json](../../conformance/evidence/resource.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETSHAREDDATA — SetSharedData | Function / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-SETUSERACTION — SetUserAction | Function / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-STARTPROC — StartProc | Function / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-STARTRANGING — StartRanging | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-STARTRANGINGCALIBRATION — StartRangingCalibration | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-TMTCLOOKUP — TMTCLookup | Function / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-VERIFY — Verify | Function / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-WAITFOR — WaitFor | Function / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-FUNCTION-WRITEFILE — WriteFile | Function / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-ADDINFO — addInfo | KeywordArgument / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-ARGS — args | KeywordArgument / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-COMMAND — command | KeywordArgument / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-GROUP — group | KeywordArgument / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-SEQUENCE — sequence | KeywordArgument / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-KEYWORD-ARGUMENT-VERIFY — verify | KeywordArgument / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-BIN — bin | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-HEX — hex | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-OCT — oct | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-RANGE — range | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-REPR — repr | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-CONVERSION-STR — str | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-DICTIONARY-HAS-KEY — dict.has_key | Method / PY | QUALIFIED: [database_scope.json](../../conformance/evidence/database_scope.json) | Not freshly qualified |
| CMP-LRM244-METHOD-DICTIONARY-KEYS — dict.keys | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-BASENAME — File.basename | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-CANREAD — File.canRead | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-CANWRITE — File.canWrite | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-DIRNAME — File.dirname | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-EXISTS — File.exists | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-FILENAME — File.filename | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-ISDIR — File.isdir | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-ISFILE — File.isfile | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-FILE-ISOPEN — File.isOpen | Method / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-ABS — abs | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-ACOS — acos | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-ASIN — asin | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-ATAN — atan | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-CEIL — ceil | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-COS — cos | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-DEGREES — degrees | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-EXP — exp | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-FLOOR — floor | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-LOG — log | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-LOG10 — log10 | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-MAX — max | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-MIN — min | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-POW — pow | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-RADIANS — radians | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-ROUND — round | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-SIN — sin | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-SQRT — sqrt | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-MATH-TAN — tan | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-CAPITALIZE — str.capitalize | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-CENTER — str.center | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ENDSWITH — str.endswith | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-FIND — str.find | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ISALPHA — str.isalpha | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ISDIGIT — str.isdigit | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ISLOWER — str.islower | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ISSPACE — str.isspace | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-ISUPPER — str.isupper | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-LOWER — str.lower | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-REPLACE — str.replace | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-STARTSWITH — str.startswith | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-STRING-UPPER — str.upper | Method / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-DESCRIPTION — telemetry-item.description | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-ENG — telemetry-item.eng | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-FULLNAME — telemetry-item.fullName | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-NAME — telemetry-item.name | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-RAW — telemetry-item.raw | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-REFRESH — telemetry-item.refresh | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-STATUS — telemetry-item.status | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TELEMETRY-ITEM-TIME — telemetry-item.time | Method / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-ABS — TIME.abs | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-FMT — TIME.fmt | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-HOUR — TIME.hour | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-ISREL — TIME.isRel | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-JULIANDAY — TIME.julianDay | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-MINUTE — TIME.minute | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-MONTH — TIME.month | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-REL — TIME.rel | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-SECOND — TIME.second | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-METHOD-TIME-YEAR — TIME.year | Method / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ACTIVE — Active | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ADJLIMITS — AdjLimits | Modifier / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ALGORITHM — Algorithm | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-AUTOMATIC — Automatic | Modifier / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-BEGIN — Begin | Modifier / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-BLOCK — Block | Modifier / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-BLOCKING — Blocking | Modifier / FLOW | QUALIFIED: [child_policy.json](../../conformance/evidence/child_policy.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-CONFIRM — Confirm | Modifier / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-CONFIRMCRITICAL — ConfirmCritical | Modifier / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-DEFAULT — Default | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-DEFINITION — Definition | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-DELAY — Delay | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-DELTA — Delta | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-DESTINATION — Destination | Modifier / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-END — End | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ERROR — Error | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-EXPECTED — Expected | Modifier / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-EXTENDED — Extended | Modifier / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-FAILURECODE — FailureCode | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-FORMAT — Format | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-GROUP — Group | Modifier / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HANDLEERROR — HandleError | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HIBOTH — HiBoth | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HIRED — HiRed | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HIYEL — HiYel | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HOST — Host | Modifier / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-HYSTERESIS — Hysteresis | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-IGNORE — Ignore | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-IGNORECASE — IgnoreCase | Modifier / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-IMAGE — Image | Modifier / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-INTERVAL — Interval | Modifier / OBS | QUALIFIED: [wait_interval.json](../../conformance/evidence/wait_interval.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-LIMITS — Limits | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-LOADONLY — LoadOnly | Modifier / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-LOBOTH — LoBoth | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-LORED — LoRed | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-LOYEL — LoYel | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-MESSAGE — Message | Modifier / COMMON | QUALIFIED: [scheduler.json](../../conformance/evidence/scheduler.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-MIDPOINT — Midpoint | Modifier / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-MODE — Mode | Modifier / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-MONITOR — Monitor | Modifier / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-NAME — Name | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-NOMINAL — Nominal | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-NOTIFY — Notify | Modifier / COMMON | QUALIFIED: [common-silence.json](../../conformance/evidence/common-silence.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ONFAILURE — OnFailure | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ONFALSE — OnFalse | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-ONTRUE — OnTrue | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-PRINTER — Printer | Modifier / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-PROMPTFAILURE — PromptFailure | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-PROMPTUSER — PromptUser | Modifier / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-RADIX — Radix | Modifier / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-RANGE — Range | Modifier / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-RELEASETIME — ReleaseTime | Modifier / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-RETRIES — Retries | Modifier / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-REUSE — Reuse | Modifier / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-SCOPE — Scope | Modifier / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-SELECT — Select | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-SENDDELAY — SendDelay | Modifier / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-SEVERITY — Severity | Modifier / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-SOURCE — Source | Modifier / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-TIME — Time | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-TIMEOUT — Timeout | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-TOLERANCE — Tolerance | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-TYPE — Type | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-UNITS — Units | Modifier / COMMON | QUALIFIED: [value_units.json](../../conformance/evidence/value_units.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-UNTIL — Until | Modifier / COMMON | QUALIFIED: [scheduler.json](../../conformance/evidence/scheduler.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-VALUE — Value | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-VALUEFORMAT — ValueFormat | Modifier / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-VALUETYPE — ValueType | Modifier / COMMON | QUALIFIED: [value_units.json](../../conformance/evidence/value_units.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-VERBOSITY — Verbosity | Modifier / COMMON | QUALIFIED: [common-silence.json](../../conformance/evidence/common-silence.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-VISIBLE — Visible | Modifier / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-WAIT — Wait | Modifier / COMMON | QUALIFIED: [timing.json](../../conformance/evidence/timing.json) | Not freshly qualified |
| CMP-LRM244-MODIFIER-WARNING — Warning | Modifier / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-FILE-PATH-APPEND — File + path | Operator / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-ADD — + | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-AND — and | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-BITWISE-AND — & | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-BITWISE-OR — \| | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-DIVIDE — / | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-EQUAL — == | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-GREATER — > | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-GREATER-EQUAL — >= | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-LEGACY-NOT-EQUAL — <> | Operator / PY | QUALIFIED: [legacy_compare_composed.json](../../conformance/evidence/legacy_compare_composed.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-LESS — < | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-LESS-EQUAL — <= | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-MODULUS — % | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-MULTIPLY — * | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-NOT — not | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-NOT-EQUAL — != | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-OR — or | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-POWER — ** | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-PYTHON-SUBTRACT — - | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-STRING-CONCAT — string + string | Operator / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-TIME-ADD — TIME + TIME | Operator / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-TIME-MULTIPLY — TIME * integer | Operator / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-TIME-SUBTRACT — TIME - TIME | Operator / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-BW — bw | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-EQ — eq | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-GE — ge | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-GT — gt | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-LE — le | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-LT — lt | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-NBW — nbw | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OPERATOR-VERIFY-NEQ — neq | Operator / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-BOOLEAN-FALSE — False | Outcome / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-BOOLEAN-TRUE — True | Outcome / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-OPERATION-FAILURE — operation failure | Outcome / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-OPERATION-SUCCESS — operation success | Outcome / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-PROMPT-TIMEOUT — prompt timeout | Outcome / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-STARTPROC-TRUE — StartProc returns True | Outcome / FLOW | QUALIFIED: [child_returns.json](../../conformance/evidence/child_returns.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-VERIFY-FAIL — verification fail | Outcome / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-VERIFY-PASS — verification pass | Outcome / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-OUTCOME-WAIT-ABORT — WaitFor interrupted then skipped | Outcome / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-SECTION-1-2-106 — 1.2 Data containers | SourceSection / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-001 — 2.1 Python constructs | SourceSection / PY | QUALIFIED: [python_sections.json](../../conformance/evidence/python_sections.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-1-002 — 2.1.1 Indentation | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-10-011 — 2.1.10 Conditional statements | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-11-012 — 2.1.11 Loop statements | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-12-013 — 2.1.12 User defined functions | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-13-014 — 2.1.13 Modules | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-2-003 — 2.1.2 Multi-line code blocks | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-3-004 — 2.1.3 Comments | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-4-005 — 2.1.4 Variable types | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-5-006 — 2.1.5 Basic data types | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-6-007 — 2.1.6 Python is case-sensitive | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-7-008 — 2.1.7 Arithmetic expressions | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-8-009 — 2.1.8 Boolean expressions | SourceSection / PY | QUALIFIED: [python_sections.json](../../conformance/evidence/python_sections.json) | Not freshly qualified |
| CMP-LRM244-SECTION-2-1-9-010 — 2.1.9 String expressions | SourceSection / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-1-015 — 3.1 SPELL drivers | SourceSection / COMMON | QUALIFIED: [v05_common_complete.json](../../conformance/evidence/v05_common_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-2-016 — 3.2 Configuration and modifiers | SourceSection / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-2-1-017 — 3.2.1 Change configuration defaults from procedures | SourceSection / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-3-018 — 3.3 Operation error handling | SourceSection / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-4-019 — 3.4 Reacting on operation result | SourceSection / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-5-020 — 3.5 Special error handling | SourceSection / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SECTION-3-6-021 — 3.6 Silent execution | SourceSection / COMMON | QUALIFIED: [common-silence.json](../../conformance/evidence/common-silence.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-1-022 — 4.1 Time management | SourceSection / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-1-1-023 — 4.1.1 Output format | SourceSection / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-10-083 — 4.10 Injecting events | SourceSection / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-11-084 — 4.11 Ground control system configuration and variables | SourceSection / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-12-085 — 4.12 Requesting Information | SourceSection / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-13-086 — 4.13 Managing GCS system displays | SourceSection / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-13-1-087 — 4.13.1 Opening displays and workspaces | SourceSection / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-13-2-088 — 4.13.2 Printing displays | SourceSection / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-13-3-089 — 4.13.3 Closing displays and workspaces | SourceSection / UI | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-14-090 — 4.14 Procedure execution flow control | SourceSection / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-14-1-091 — 4.14.1 Steps | SourceSection / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-14-2-092 — 4.14.2 Go-to mechanism | SourceSection / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-14-3-093 — 4.14.3 Ending, pausing and aborting | SourceSection / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-14-4-094 — 4.14.4 User action function | SourceSection / FLOW | QUALIFIED: [flow.json](../../conformance/evidence/flow.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-095 — 4.15 Databases | SourceSection / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-1-096 — 4.15.1 Spacecraft database | SourceSection / DATA | QUALIFIED: [scdb.json](../../conformance/evidence/scdb.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-2-097 — 4.15.2 Manoeuvre message databases | SourceSection / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-3-098 — 4.15.3 Ground system databases | SourceSection / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-4-099 — 4.15.4 Procedure database | SourceSection / DATA | QUALIFIED: [proc_dictionary_composed.json](../../conformance/evidence/proc_dictionary_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-5-1-101 — 4.15.5.1 Loading user databases | SourceSection / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-5-100 — 4.15.5 User databases | SourceSection / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-5-2-102 — 4.15.5.2 Creating user databases | SourceSection / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-5-3-103 — 4.15.5.3 Saving user databases | SourceSection / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-5-4-104 — 4.15.5.4 Reverting changes to user databases | SourceSection / DATA | QUALIFIED: [user_database.json](../../conformance/evidence/user_database.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-15-6-105 — 4.15.6 Database formats | SourceSection / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-1-109 — 4.16.1.1 Procedure library and priorities | SourceSection / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-108 — 4.16.1 Starting procedures | SourceSection / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-2-110 — 4.16.1.2 Blocking / Non-blocking mode | SourceSection / FLOW | QUALIFIED: [child_policy.json](../../conformance/evidence/child_policy.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-3-111 — 4.16.1.3 Visible/Hidden mode | SourceSection / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-4-112 — 4.16.1.4 Automatic/Manual mode | SourceSection / FLOW | QUALIFIED: [child_execution.json](../../conformance/evidence/child_execution.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-5-113 — 4.16.1.5 Passing arguments | SourceSection / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-1-6-114 — 4.16.1.6 Return value | SourceSection / FLOW | QUALIFIED: [child_returns.json](../../conformance/evidence/child_returns.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-16-107 — 4.16 Sub-procedures | SourceSection / FLOW | QUALIFIED: [v05_flow_complete.json](../../conformance/evidence/v05_flow_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-1-116 — 4.17.1 Opening files | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-115 — 4.17 File manipulation | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-2-117 — 4.17.2 Closing files | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-3-118 — 4.17.3 Write data to files | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-4-119 — 4.17.4 Read data from files | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-5-120 — 4.17.5 Read directory contents | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-6-121 — 4.17.6 General file system operations | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-7-122 — 4.17.7 Deleting files and directories | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-17-8-123 — 4.17.8 Error handling with file operations | SourceSection / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-18-1-125 — 4.18.1 Enabling or disabling ranging activities | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-18-124 — 4.18 Ranging operations | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-18-2-126 — 4.18.2 Starting or stopping ranging activities | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-18-3-127 — 4.18.3 Ranging configuration | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-18-4-128 — 4.18.4 Ranging status | SourceSection / DATA | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-1-130 — 4.19.1 Setting shared data values | SourceSection / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-129 — 4.19 Sharing data between procedures | SourceSection / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-2-131 — 4.19.2 Test-and-set shared data values | SourceSection / DATA | QUALIFIED: [data-race.json](../../conformance/evidence/data-race.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-3-132 — 4.19.3 Getting shared data values | SourceSection / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-4-133 — 4.19.4 Clearing shared data values | SourceSection / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-19-5-134 — 4.19.5 The GLOBAL scope | SourceSection / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-024 — 4.2 Telemetry values acquisition | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-1-025 — 4.2.1 Acquiring engineering values | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-2-026 — 4.2.2 Acquiring raw values | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-3-027 — 4.2.3 Extended information | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-4-028 — 4.2.4 Possible failures | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-2-5-029 — 4.2.5 Failure actions | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-20-1-136 — 4.20.1 Generate memory reports | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-20-135 — 4.20 Memory management functions | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-20-2-137 — 4.20.2 Comparing memory images | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-20-3-138 — 4.20.3 Extract data from memory images | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-21-1-140 — 4.21.1 Extract data from TM/TC database tables | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-21-139 — 4.21 Ground control system TM/TC database | SourceSection / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-030 — 4.3 Verifying telemetry values | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-1-031 — 4.3.1 Verifying a single parameter value | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-10-040 — 4.3.10 Verifying multiple conditions | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-11-041 — 4.3.11 Verifying against multiple parameter values | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-12-042 — 4.3.12 Comparing parameters against other parameters | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-13-043 — 4.3.13 Boolean expressions | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-2-032 — 4.3.2 Last recorded values an timeouts | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-3-033 — 4.3.3 Tolerance | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-4-034 — 4.3.4 Failed comparisons | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-5-035 — 4.3.5 OnFalse for Verify function | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-6-036 — 4.3.6 Retrying verifications | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-7-037 — 4.3.7 Delaying the verification | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-8-038 — 4.3.8 Case-insensitive verification | SourceSection / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-3-9-039 — 4.3.9 Function result | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-4-044 — 4.4 Building commands | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-4-1-045 — 4.4.1 Command arguments | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-046 — 4.5 Sending commands | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-1-047 — 4.5.1 Sending a command without arguments | SourceSection / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-10-056 — 4.5.10 Grouping and blocking command groups | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-11-057 — 4.5.11 Timeouts for execution verification | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-12-058 — 4.5.12 Platform specific parameters | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-13-059 — 4.5.13 Delaying command release time | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-14-060 — 4.5.14 Sending And Verifying | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-15-061 — 4.5.15 Automatic limit adjustment | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-16-062 — 4.5.16 A complex example | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-17-063 — 4.5.17 Return value | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-2-048 — 4.5.2 Sending a time-tagged command | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-3-049 — 4.5.3 Release time for commands | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-4-050 — 4.5.4 Loading but not executing | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-5-051 — 4.5.5 Confirm execution of all commands | SourceSection / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-6-052 — 4.5.6 Confirm execution of critical commands | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-7-053 — 4.5.7 Sending a command with arguments | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-8-054 — 4.5.8 Sending sequences | SourceSection / CMD | QUALIFIED: [command_display_composed.json](../../conformance/evidence/command_display_composed.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-5-9-055 — 4.5.9 Sending command groups | SourceSection / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-064 — 4.6 Holding execution | SourceSection / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-1-065 — 4.6.1 Stop procedure execution for a given amount of time | SourceSection / OBS | QUALIFIED: [wait_time.json](../../conformance/evidence/wait_time.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-2-066 — 4.6.2 Stop procedure execution until a given absolute time arrives | SourceSection / OBS | QUALIFIED: [wait_time.json](../../conformance/evidence/wait_time.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-3-067 — 4.6.3 Stop procedure execution until a telemetry condition is fullfilled | SourceSection / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-4-068 — 4.6.4 Aborting the wait | SourceSection / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-6-5-069 — 4.6.5 Showing progress in time conditions | SourceSection / OBS | QUALIFIED: [wait_interval.json](../../conformance/evidence/wait_interval.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-7-070 — 4.7 Injecting TM parameters | SourceSection / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-071 — 4.8 Getting and setting TM parameters limits | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-1-072 — 4.8.1 Identifying limits | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-10-081 — 4.8.10 Checking alarm status | SourceSection / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-2-073 — 4.8.2 Types of limits | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-3-074 — 4.8.3 Limit specification | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-4-075 — 4.8.4 Retrieving OOL definitions | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-5-076 — 4.8.5 Modifying OOL definitions | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-6-077 — 4.8.6 Enabling and disabling limit checking | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-7-078 — 4.8.7 Adjusting limits | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-8-079 — 4.8.8 Loading limits from files | SourceSection / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-8-9-080 — 4.8.9 Restoring limits | SourceSection / LIMIT | QUALIFIED: [limit.json](../../conformance/evidence/limit.json) | Not freshly qualified |
| CMP-LRM244-SECTION-4-9-082 — 4.9 Displaying messages | SourceSection / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-STATE-WAITFOR-INTERRUPTED — INTERRUPTED | State / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-STATE-WAITFOR-PAUSE — PAUSE | State / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-STATE-WAITFOR-WAITING — WAITING | State / OBS | QUALIFIED: [wait_control.json](../../conformance/evidence/wait_control.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-COLON-DMY — dd-mmm-yyyy:hh:mm[:ss] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-COLON-SLASH — dd/mm/yyyy:hh:mm[:ss] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-COLON-YMD — yyyy-mm-dd:hh:mm[:ss] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-DMY — dd-mmm-yyyy [hh:mm[:ss]] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-SLASH — dd/mm/yyyy [hh:mm[:ss]] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ABSOLUTE-TIME-YMD — yyyy-mm-dd [hh:mm[:ss]] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-ACTION-COMBINATION — ACTION \| ACTION | Syntax / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-BREAK — break | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-CASE-SENSITIVE-NAMES — case-sensitive identifiers | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-COMMAND-ARGUMENT — [argument-name, value] | Syntax / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-COMMAND-SEQUENCE — [command, command, ...] | Syntax / CMD | QUALIFIED: [cmd.json](../../conformance/evidence/cmd.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-CONTINUE — continue | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-DATA-CONTAINER-VAR — Var(type, modifiers...) | Syntax / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-DICTIONARY-LITERAL — {key: value, ...} | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-DICTIONARY-LOOKUP — mapping[key] | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-DOCSTRING-COMMENT — triple-quoted comment block | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-DYNAMIC-ASSIGNMENT — name = value | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-FOR-IN — for target in iterable: ... | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-FUNCTION-DEFINITION — def name(arguments): ... return ... | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-IF-ELIF-ELSE — if condition: ... elif condition: ... else: ... | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-IMPORT — import module | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-INDENTED-BLOCK — indentation-defined block | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-INDEX — value[index] | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-INTEGER-BINARY — 0b101001 | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-INTEGER-HEXADECIMAL — 0xFF | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-INTEGER-OCTAL — 035 | Syntax / PY | QUALIFIED: [database_values_composed.json](../../conformance/evidence/database_values_composed.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-KEYWORD-MODIFIER — Function(arg, Modifier=value) | Syntax / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-LINE-COMMENT — # line comment | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-LIST-LITERAL — [item, ...] | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-MULTILINE-BACKSLASH — multi-line backslash continuation | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-MULTILINE-COMMA — multi-line comma continuation | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-MULTILINE-STRING-PLUS — multi-line string with + | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-MULTIPLE-ASSIGNMENT — x, y, z = value | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-PROCEDURE-ARGUMENT — StartProc(name, arguments) | Syntax / FLOW | QUALIFIED: [child_arguments.json](../../conformance/evidence/child_arguments.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-PROMPT-LIST-ALPHA — Type=LIST\|ALPHA | Syntax / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-PROMPT-LIST-NUM — Type=LIST\|NUM | Syntax / UI | QUALIFIED: [ui.json](../../conformance/evidence/ui.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-QUALIFIED-ACCESS — module.entity | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-RELATIVE-TIME-DAYS — +/-ddd hh:mm[:ss] | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-RELATIVE-TIME-SECONDS — +/-ss.nnn | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-SHARED-TEST-AND-SET — SetSharedData(..., Expected=value) | Syntax / DATA | QUALIFIED: [data-race.json](../../conformance/evidence/data-race.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-SLICE — value[start:end] | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-DAY — %d | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-HOUR — %H | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-MINUTE — %M | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-MONTH-ABBREVIATED — %b | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-MONTH-NUMERIC — %m | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-SECOND — %S | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TIME-OUTPUT-YEAR — %Y | Syntax / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TM-DESCRIBED-MNEMONIC — 'T MNEMONIC description' | Syntax / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TM-MNEMONIC — 'MNEMONIC' | Syntax / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-TRY-EXCEPT-DRIVER — try: call except DriverException, ex: handler | Syntax / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-URI-LIMITS — limits://name_of_file | Syntax / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-URI-MEM — mem://report | Syntax / SPECIAL | QUALIFIED: [v05_special_complete.json](../../conformance/evidence/v05_special_complete.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-URI-MMD — mmd://folder/name | Syntax / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-URI-USR — usr://folder/name | Syntax / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-VERIFY-BETWEEN — [mnemonic, bw\|nbw, lower, upper] | Syntax / OBS | QUALIFIED: [v05_observation_complete.json](../../conformance/evidence/v05_observation_complete.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-VERIFY-BOOLEAN-TREE — AND(condition, ...) / OR(condition, ...) | Syntax / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-VERIFY-CONDITION — [mnemonic, operator, expected] | Syntax / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-VERIFY-CONDITION-LIST — [[condition], [condition], ...] | Syntax / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-SYNTAX-WHILE — while condition: ... | Syntax / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-BOOLEAN — Boolean | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-BOOLEAN — BOOLEAN (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-DATETIME — DATETIME (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-FLOAT — FLOAT (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-LONG — LONG (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-RELTIME — RELTIME (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATA-CONTAINER-STRING — STRING (data-container type) | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATABASEDICTIONARY — Python dictionary database | Type / DATA | QUALIFIED: [v05_database_complete.json](../../conformance/evidence/v05_database_complete.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DATACONTAINER — DataContainer | Type / DATA | QUALIFIED: [dta.json](../../conformance/evidence/dta.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DICTIONARY — Dictionary | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-DRIVEREXCEPTION — DriverException | Type / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-TYPE-FILE — File | Type / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-TYPE-FILEHANDLE — file handler | Type / FILES | QUALIFIED: [files.json](../../conformance/evidence/files.json) | Not freshly qualified |
| CMP-LRM244-TYPE-FLOAT — Float | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-HANDLEEXCEPTION — Handle exception object | Type / COMMON | QUALIFIED: [common.json](../../conformance/evidence/common.json) | Not freshly qualified |
| CMP-LRM244-TYPE-INTEGER — Integer | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-LIMITDEFINITION — OOL definition dictionary | Type / LIMIT | QUALIFIED: [v05_limit_complete.json](../../conformance/evidence/v05_limit_complete.json) | Not freshly qualified |
| CMP-LRM244-TYPE-LIST — List | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-PRIMITIVESHAREDVALUE — primitive shared-data value | Type / DATA | QUALIFIED: [data.json](../../conformance/evidence/data.json) | Not freshly qualified |
| CMP-LRM244-TYPE-PROMPTRESULT — Prompt return value | Type / UI | QUALIFIED: [v05_ui_complete.json](../../conformance/evidence/v05_ui_complete.json) | Not freshly qualified |
| CMP-LRM244-TYPE-STRING — String | Type / PY | QUALIFIED: [python.json](../../conformance/evidence/python.json) | Not freshly qualified |
| CMP-LRM244-TYPE-TELECOMMANDITEM — TC item | Type / CMD | QUALIFIED: [v05_command_complete.json](../../conformance/evidence/v05_command_complete.json) | Not freshly qualified |
| CMP-LRM244-TYPE-TELEMETRY-EXPRESSION — telemetry expression object | Type / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-TYPE-TELEMETRYITEM — telemetry item object | Type / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
| CMP-LRM244-TYPE-TIME — TIME | Type / TIME | QUALIFIED: [time.json](../../conformance/evidence/time.json) | Not freshly qualified |
| CMP-LRM244-TYPE-VAR — Var | Type / DATA | QUALIFIED: [v05_data_complete.json](../../conformance/evidence/v05_data_complete.json) | Not freshly qualified |
| CMP-LRM244-TYPE-VERIFYRESULT — Verify composite object | Type / OBS | QUALIFIED: [obs.json](../../conformance/evidence/obs.json) | Not freshly qualified |
