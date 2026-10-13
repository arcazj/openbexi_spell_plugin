# COMMON policy qualification

40 of the 66 COMMON rows are qualified. The full inventory is now 82 QUALIFIED /
681 OPEN. v0.5 and v0.6 remain open; the accepted release artifacts remain v0.3
host and v0.4 GENERIC DSS. This milestone qualifies development images, not new
native wheels or host installations.

## Behavior and evidence

`evidence/common.json` contains 44 grouped checks for 36 contracts, each with
positive, boundary, failure and recovery evidence. `evidence/common-silence.json`
adds four grouped checks for four contracts. Shared checks cover the contracts
that jointly define one policy; the counts are not independent procedure counts.

The original native executor, context, registry, language helpers, CIF, shared
blackboard and file adapter perform the operations. No helper, registry entry,
executor or notification method is replaced. An independent DAP controller checks
the actual option lists, answers prompts and repairs an absent test file before
selecting REPEAT. Missing keys/files and failed compare-and-set produce real
failure inputs. The suite checks the twelve Boolean-result combinations in the
LRM, explicit and inherited policies, unchanged data after rejected operations,
Handle metadata, defaults, precedence, exception propagation and recovery.

Six additional native processes execute the terminal scenarios as traced
procedure code: automatic failure abort, True/False result abort, interactive
abort, uncaught DriverException and explicit fresh-process recovery. Abort and
uncaught error prevent the continuation marker and execute `finally`. Each
process begins with the original defaults even though the preceding process
changed defaults before aborting. Imported oracle modules do not establish
executor line-control or checkpoint conformance; FLOW retains those wider gates.

The silence controller observes original IPC directly because the current host
DAP adapter does not forward item notifications. It verifies suppressed procedure
text and ITEM notifications, real data effects, propagated exceptions and restored
feedback on subsequent calls. The recorded IPC contains visible feedback as a
positive control, rather than inferring silence from an inactive observer.

## Source patches

Each patch checks the exact 2.6.10 archive preimage and preserves its notices:

- Result prompts use PromptUser independently of PromptFailure. Disabling failure
  prompts no longer silently substitutes an OnFailure action for an OnTrue/OnFalse
  choice.
- NOACTION after a failed operation returns no available value (`None`), instead
  of manufacturing a Boolean result. OnTrue/OnFalse=NOACTION preserves the actual
  Boolean result.
- Common Boolean modifiers, action masks and FailureCode are validated. Explicit
  ambiguous automatic actions fail before operation effects. Inherited choices
  for a dormant result remain compatible with existing successful Send calls;
  if that result occurs in automatic mode, ambiguity raises SyntaxException.
- Valid functions absent from language.xml can acquire procedure-local defaults.
  ChangeLanguageConfig validates the target and complete modifier set before
  applying changes. Unknown modifiers do not leave a partial change.
- Helper action labels are copied per instance; setting a fallback OnFailure does
  not discard other configuration.

## Manual/source decisions

`ERRATUM-HANDLEERROR-DEFAULT`: LRM p.30 and the original wrapper establish a True
fallback. Page 114 explicitly describes an illustrative, spacecraft-dependent
configuration, whose False value is not a universal default. Function/interface
configuration and explicit call modifiers can override the fallback. Notify's
page-114 False value is likewise a profile example; the wrapper fallback is True.

`ERRATUM-PROMPT-FAILURE-MODIFIERS`: pp.28 and 116-117 distinguish operation
failures (HandleError, PromptFailure, OnFailure) from normal Boolean outcomes
(PromptUser, OnTrue, OnFalse). Page 111's description of PromptUser as controlling
failures and p.30's statement that failures always prompt are incomplete. The
detailed rules and independent behavior table take precedence.

Page 116 restricts HANDLE to interactive failure handling, FailureCode to integers,
and automatic policies to one action. Invalid policies are rejected; an inherited
multi-option policy is rejected when selected in automatic mode. NOACTION on
failure is an automatic policy with no invented success value.

The p.31 Python-2 exception syntax is ported to `except DriverException as ex`.
Example 25 needs the missing comma between `Verbosity=999` and `Notify=False`.

Silent execution concerns procedure messages and item feedback. Original
`lib/SPELL_EXC/src/SPELLexecutorImpl.C`, `processException`, deliberately emits a
system-scope diagnostic for caught exceptions. This remains visible. Native
shared-data change broadcasts also remain active: they synchronize blackboard
state and are not ITEM feedback controlled by Notify. The oracle checks these
boundaries rather than treating silence as suppression of errors or state changes.

## Reproduce

```powershell
python conformance/build_common_patch.py
docker build --network=none -f conformance/common.Dockerfile -t openbexi-spell-host:v05-common .
python conformance/run_common.py --image openbexi-spell-host:v05-common
python conformance/run_silence.py --image openbexi-spell-host:v05-common
python conformance/run_native.py --image openbexi-spell-host:v05-common --output .qualification/v0.5/time-common
docker build --network=none -f driver_plugin/conformance.Dockerfile -t openbexi-spell-dss:v05-common .
```

The host image is
`sha256:39eac7c5b3229988ce5b6afb994b3bf988645fdf0989082303ed8f7bba167872`.
The combined DSS image is
`sha256:34d20137501f19e34c46bda10022b7fd7eb2ff8b6a2aad47d9b6f6c65e643266`.
Both retain original and patched Python files, recipe and manifest under
`/opt/common-conformance-patch`, alongside the inherited original source/notices.
The source patch hash is
`e89e5001f1431bf5cfcd0d1905b28b7866695dbc2ecd8267f8d21011c018fd27`.
`evidence/common-images.json` records installed source hashes for both images;
the observer also verifies installed files against the embedded patch manifest.
The original host image retains its accepted native session adapter; the DSS
image retains its later driver-enabled adapter. Their distinct hashes are
recorded explicitly instead of treating the repository copy as both artifacts.

TIME was rerun on this image: all 168 checks pass. The current native host DAP
regression passes all ten cases; the combined DSS image passes all nine native
driver cases, including immutable Execution, fencing, pause, uncertainty and TIME
timeouts. Their reports are `.qualification/v0.5/common-host-regression-final/`
and sibling `openbexi_ide/.qualification/v0.5/common-native-driver-final.xml`.
All 213 plugin/host package tests and seven subtests pass with warnings treated as
errors in `.qualification/v0.5/common-plugin-regression-final.xml`. The final
COMMON oracles run on the prior TIME image fail 19 of the 44 grouped checks; this
baseline is retained in `.qualification/v0.5/common-baseline-final/`. All 44 pass
on the patched image, and all four direct-IPC silence checks pass.
The failed intermediate runs are retained. One exposed overly eager validation
of inherited Send policies; that behavior was corrected before the passing rerun.

The full-inventory checker caches source hashes and parsed reports within a single
validation, avoiding repeated reads of the large original archive. Every new
validation rechecks those files; stale or failing evidence remains an error.

## The 26 remaining COMMON rows

These require actual family behavior, not more shared-policy assertions:

| Rows | Required work packages and evidence |
| --- | --- |
| RECHECK, RESEND, RESUME | OBS/CMD: fresh telemetry retry, command reinjection, driver-specific partial-group continuation and uncertainty boundaries |
| PS, VECTOR | UI: real PrintDisplay format/output and failure recovery |
| ENG, RAW, ValueFormat | OBS/CMD/SPECIAL: calibrated versus raw values through real models and services |
| Default | UI/DATA: prompt timeout/default semantics and native variable defaults |
| Delay, Time, Timeout, Until, Wait | FLOW/OBS/CMD/UI: real timing, fresh acquisition, deadlines and scheduled commands across applicable families |
| End, Type | FILES/DATA/UI/SPECIAL: upper bounds, typed prompts and database/memory filters |
| Error, Ignore, Tolerance | LIMIT/OBS: actual out-of-limit definitions and verification semantics |
| Format | CMD/OBS/UI/DATA/SPECIAL: every applicable value/print representation |
| Message | FLOW/UI: wait messages and prompt/display handling |
| Name, Value | DATA/CMD/SPECIAL: all applicable named and typed data/model operations |
| Units, ValueType | CMD: native typed/radix/unit TC argument construction and transport |
| Section 3.1 SPELL drivers | All driver families, including explicit unsupported-service behavior; the GENERIC profile is not full driver compatibility |

Keep these rows open while their owning packages are implemented and tested.
The subsequent FLOW milestone qualifies USER-ACTION-DISABLE; four other
original errata remain open. Full v0.5 acceptance still
requires every one of the 763 rows; v0.6 distribution acceptance follows it.
