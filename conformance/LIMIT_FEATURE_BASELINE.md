# Remaining limit behavior

The v0.4-derived profile implements one active engineering HARDSOFT definition.
These native probes retain the gaps before changing that implementation. A
rejection is a counterexample, never evidence of support for the requested
feature. The source inventory retains all 763 language requirements.

The reference is Language Reference 2.4.4, pages 59–68. It defines multiple named
definitions, ALL/ACTIVE/identifier selection, metadata and activation algorithms,
STATUS/STEP/SPIKE types, alarm controls, condition-based adjustment and GCS limit
files. The language allows driver subsets, but this release's full language gate
requires independently demonstrated behavior for each allocated requirement.

The existing implementation also needs review of the manual/source discrepancies:
the manual calls the condition function both SetLimits and AdjustLimits; the
examples use AdjustLimits. Its explanatory LoHigh spelling conflicts with the
LoYel key in the definitions and examples. Preserve the original spellings in
the inventory and record an explicit compatibility decision with native tests.

Run only after the active command/display package qualification is finished.
Use the fresh composed image, retain all output, and freeze these inputs before
implementing the next candidate.
