# TC argument ValueType and Units

This bounded original-source checkpoint covers only the two COMMON modifiers
`ValueType` and `Units`. Full BuildTC/Send, arbitrary driver data types, calibration,
scheduled commands and atomic groups remain open. Passing tests do not accept
the full v0.5 release or its v0.6 dependency.

LRM 2.4.4 p48 explicitly requires argument casting and gives integer-to-string
as its example. Pages112-113 list LONG, STRING, BOOLEAN, TIME and FLOAT. The
original TC model passed an unconverted value to ValueClass, which re-inferred
integer/float/string and overwrote the requested metadata. Boolean and TIME
inference also retained a default LONG annotation. The checked patch corrects
TcItemParamClass, without changing ValueClass behavior for PCS callers.

Explicit casts use Python `int`, `str`, `bool`, `float` and original SPELL TIME.
The manual does not prescribe separate Boolean text parsing: Python truthiness
is the declared interpretation, so a nonempty string `"False"` is true. TIME in
the manual is the original constructor/class; the existing DATETIME/RELTIME
metadata records whether the result is absolute or relative. Those source
aliases also require the corresponding time kind. Invalid casts and unknown
ValueType values raise original SyntaxException; replacement of an existing
argument occurs only after successful validation. Omission still infers types.

Page112 defines Units as a string name for a TC argument. The native item keeps
that string exactly, including empty or Unicode names. No unit conversion is
specified by that clause. The GENERIC catalog has no TC unit conversion metadata,
so its existing driver rejects nonempty Units before SendCommand or an effect.
This is tested as a driver limitation, not as support for calibrated-unit sends.
The TIME type likewise works in BuildTC, while the current command catalog has
no TIME-valued parameter; rejected TIME sends do not qualify broader Send.

Independent assertions inspect original native BuildTC values and metadata,
then send catalog-supported LONG/FLOAT/STRING values through original protobuf
and real binary DSS. The catalog's only BOOLEAN parameter belongs to the critical
RESET command, which this driver forbids. Its exact Boolean protobuf value and
no-effect rejection are checked, without claiming successful critical commands.
Every successful send requires exactly five
ordered stages and one ingress delivery per stage; invalid operations must have
zero effects. A wire integer outside signed64 raises DriverException before RPC,
preserving language error policy rather than leaking protobuf ValueError.

The diagnostic Docker recipe derives from the verified fresh native wheel,
captures its unmodified provenance, applies frozen LIMIT419b37a first, and then
applies only `tc_item.py` and proxy `tc.py`. It validates exact preimages and keeps
original/patched bytes and notices. `value_units_provenance.py` verifies the
unchanged base native binaries and composition plus the declared overlay chain;
it never represents the overlay as the original accepted wheel. Original LIMIT
tmhelper/tm.py blocks remain untouched by this tranche.

Use `run_value_units.py --image <exact image>` and promote only a fully passing
raw report through `value_units_report.py`. Failed baseline and raw RPC/packet
evidence remain in the ignored qualification directory. The initial baseline
also exposed an oracle that incorrectly equated a rejected SendCommand RPC with
an effect; that assertion was corrected to check zero binary effects. Both
baseline runs remain retained.
The first patched run retained two further oracle corrections: critical RESET
must fail closed, and a recovery receipt count starts after the preceding
deliberately rejected TIME RPC. Neither correction changes runtime behavior.
