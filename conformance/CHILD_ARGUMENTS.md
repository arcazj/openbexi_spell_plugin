# Native child arguments

LRM p89 Examples 160-161 pass `args=[['A',1],['B',2]]` to `StartProc`
and read `ARGS['A']` in the child. Eight controls exercise actual native parent
and child executors, using the installed host's child-start service.

The independent observations include returned values and exact types, empty
argument lists, malformed definitions rejected before any child opens, missing
key errors, and successful transfer/access after a rejected operation. Context
inventory, child status, parent/child files, events, native logs and cleanup are
retained. Zero, false and empty text must survive with their distinct types.

Run `run_child_arguments.py --image <immutable-id>`, then normalize a passing
report with `child_arguments_report.py`. Only the two examples and argument-pair
syntax can qualify. Whole StartProc, its broader argument-transfer section,
complex objects, library priorities, other execution modes and checkpoint
recovery remain separate. No new row is promoted until installed runs pass.
