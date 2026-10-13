# Native UI language contracts

This milestone qualifies 25 of the 60 UI inventory rows on the exact integrated
development image recorded in `evidence/ui.json`. The original native executor,
CIF and IPC handle procedure text, item notifications and typed prompts. This
does not establish actual browser/desktop rendering or full v0.5 acceptance.

The passing run is `.qualification/v0.5/ui/503118954a37421eb40d9650191939ee/`.
Its 62 grouped checks cover all four evidence dimensions. The same final oracle
on the preceding COMMON image fails 14 checks in
`.qualification/v0.5/ui/800548809135431db0c1d50270121f6a/`.
All failed intermediate runs are retained.

## Qualified behavior

- Display sends exact native procedure text at default INFO or explicit
  WARN/ERROR severity. Multiline/UTF-8 text survives; invalid severity emits no
  procedure text and a later valid call succeeds. Native INFO buffering may
  reorder writes relative to immediate warning/error messages, so the observer
  matches exact values and counts without inventing a delivery ordering.
- The original Notification callable sends actual ITEM names, typed string
  values and SUCCESS/IN PROGRESS/FAILED statuses. Empty values survive and
  malformed arguments have no item effects. Original ITEM strings use Python
  `repr`; the observer checks that declared wire representation.
- OK/CANCEL/YES/NO and their pairs expose exact native choices and Boolean
  return values. Invalid messages/timeouts fail before a prompt; explicit later
  calls recover. ALPHA preserves text and empty/UTF-8 boundaries.
- NUM preserves integer and floating results, including signed fractions, zero
  and scientific notation with upper/lowercase exponent markers. Invalid input
  raises the original DriverException and later numeric input succeeds.
- DATE constructs an absolute TIME directly from a Python string. Leap dates
  work; invalid dates, relative durations and expression-shaped answers fail.
  A harmless expression which formerly returned integer 17 is rejected.
- Keyed LIST returns its selected key, LIST|ALPHA returns its selected value for
  both keyed and keyless lists, and LIST|NUM returns a zero-based index.

An independent controller supplies real native IPC answers. Imported module
oracles qualify values, while 15 additional traced main procedures qualify list
protocol failures and explicit fresh-executor recovery. Malformed, suffixed,
negative and out-of-range indices must never silently select an option.

## Checked original-source corrections

`source_port/ui_native_patches.py` checks the exact original CIF helper preimage
and existing CPython-port result before applying a narrow patch. It replaces
atoi list-index parsing with strict conversion, implements keyed ALPHA values,
uses the LRM zero-based NUM index, and supports full Python integer/float parsing
without leaving a pending Python exception while constructing DriverException.

DATE calls the original TIME class with a Python string instead of interpolating
the answer into Python expression evaluation. Numeric conversion owns its
temporary Python string; successful results are returned as new references
without the original extra INCREF leak.

Original/ported/patched sources, notices, recipes, compiler/link commands and
binary hashes are retained under `/opt/combined-native-patch`. The observer
checks the installed library against the embedded manifest, and the report binds
the recipes, manual/archive and exact runtime image.

## Manual/source decisions and limits

LRM p.71 Example116 specifies indices 0 or 1 for LIST|NUM. The original source
added one; the documented zero-based index now wins. LRM p.71 specifies selected
values for LIST|ALPHA, including keyed lists; returning the whole key:value text
does not satisfy that contract.

LRM p.68 names a Notify callable, but original 2.6.10 exports Notification while
Notify is its string-valued modifier. No ambiguous alias replaces the modifier.
The FUNCTION-NOTIFY and Example109 rows stay open for a full source-conflict
decision; the actual status constants are qualified through Notification.

Malformed option replies follow original `ClientIF_Prompt` in SPELLcifPython.C:
a core exception calls `executor.abort(..., true)`. That forced abort prevents
continuation and does not guarantee Python finally execution. The controller
closes owned workers and then demonstrates valid fresh-executor recovery. An
earlier oracle incorrectly required a finally marker for this forced path; its
failed run is preserved. Ordinary language Abort and exception cleanup have
separate COMMON/FLOW evidence.

Full Prompt/return-type/section rows, timeout/default/beep behavior, Event,
ground resources, ranging error state, display/workspace applications and
printing remain open. Cross-family Severity/Type/Format/Default modifiers remain
open until every applicable family is qualified.
