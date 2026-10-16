# Procedure library and hidden execution baseline

Language Reference 2.4.4 pages 86–89 require filename and header-name selection,
configured folder priority, an explicit-path override, hidden children, and
combined execution modes with arguments. The retained 12 probes execute the
original native StartProc path. They record procedure files, actual selected
child output, context inventory, messages, native mode information and explicit
manual RUN ordering. No coverage rows are promoted from these diagnostics.

The priority probes declare the proposed project configuration in
`spell-library.json`: schema `openbexi.spell.library/1` and an ordered `priorities`
list, highest priority first. The manual does not prescribe a file format.
The baseline deliberately writes that configuration before native startup; it
does not substitute a resolver or modify the native manager. The unchanged
baseline is expected to ignore this new configuration until support is added.
With no configuration, the probe retains the original alphabetical folder order.

Source inspection found that the original child manager compares file IDs but
does not compare the procedure-name field, and that the procedure inventory is
ordered by file ID. The probes must confirm the resulting behavior before any
implementation correction is accepted. An expected baseline failure is retained
as a counterexample, never treated as successful acceptance evidence.
