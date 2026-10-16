# Procedure database qualification

The LRM 2.4.4 page 81 specifies a dictionary at `PROC['ARGS']`. The
2.6.10 executor and service instead initialize this entry from the argument
expression as text. The proposed native correction copies the arguments already
evaluated by `installCallingArguments()`, stores the initial dictionary in the
current interpreter, and copies it into each new procedure database. It does not
evaluate the caller expression a second time or add a visible procedure global.

This is a diagnostic candidate. No contract is qualified by this document,
source inspection, successful compilation, or the two source guard tests.

`run_proc_metadata.py` captures four baseline cases on the installed runtime.
`run_proc_dictionary.py --suite baseline` repeats the same four cases with an
explicit native library overlay. `--suite lifecycle` adds twelve cases covering:

- Parent and child identities, argument types, private dictionary isolation,
  real child execution and step/previous-step updates.
- Reload after completion and after deliberate procedure errors, with an
  independent file counter proving the caller expression was evaluated once.
- Close and reopen under the same context and instance name, proving private
  procedure data is discarded and each new interpreter evaluates its own
  arguments once.
- Empty arguments, zero/False/empty-string values, Unicode and negative values,
  invalid dictionary keys and successful reads after those errors.

Every attempt retains the exact procedures, host/controller sources, native
events, library/source identities and failure logs. Any failed lifecycle leaf
stops that sequence and prevents qualification.

The page 81 `INPUT_DATA` description says "output directory" twice. Page 90
explicitly assigns input files to `PROC[INPUT_DATA]` and output files to
`PROC[OUTPUT_DATA]`; the original native initialization agrees with page 90.
The initial baseline only observes these paths. The lifecycle suite configures
distinct private input/output directories in the genuine generated context,
then runs the unchanged host and native launcher. Procedures check those paths,
read input, recover from a missing file, and write separate output. The
configuration, fixture launcher and file contents are retained for inspection.
Unicode file contents explicitly use UTF-8. They do not rely on the embedded
interpreter's locale-dependent default text encoding.

The original executor represents each step as `[id, title]` and includes the
instance suffix in the procedure name. Checks preserve these representations
and cross-check parent/child names against actual context notifications.

The retained error-reload probe found another original-source defect: the
`CANCEL_RECOVER` reload branch reset the frame but retained the old procedure
database, and the outer execution loop treated every error continuation as
recovery. A reload after failure therefore kept modified PROC entries and an
old call stack. The correction rebuilds the execution environment for this
reload branch and uses the existing reload flag to distinguish a new run from
checkpoint recovery. The twelve lifecycle cases must pass with this correction.

Fresh composed builds and all existing native regression suites are required
before accepting the correction into a published checkpoint. Full v0.5 still
requires all 763 inventory rows.
