# Native child arguments

LRM p89 Examples 160-161 pass `args=[['A',1],['B',2]]` to `StartProc`
and read `ARGS['A']` in the child. This repository's accepted native profile
requires `from spell.runtime import ARGS`; it does not inject SPELL into builtins.
Ten controls exercise actual native parent
and child executors, using the installed host's child-start service.

The independent observations include returned values and exact types, empty
argument lists, malformed definitions rejected before any child opens, invalid
key rejection, and successful transfer/access after a rejected operation. Two
additional controls answer the actual child prompt for a missing variable, as
specified on pp84-85, then verify its value and subsequent access. Context
inventory, child status, parent/child files, events, native logs and cleanup are
retained. Zero, false and empty text must survive with their distinct types.

Run `run_child_arguments.py --image <immutable-id>`, then normalize a passing
report with `child_arguments_report.py`. Only the two examples and argument-pair
syntax can qualify. Whole StartProc, its broader argument-transfer section,
complex objects, library priorities, other execution modes and checkpoint
recovery remain separate. No new row is promoted until installed runs pass.

The first probe omitted the required import, causing seven NameError failures;
malformed-definition rejection passed. That harness error is retained in
`evidence/child_arguments_harness.json`. The corrected probe also verifies that
`ARGS` is absent from builtins before its explicit import.
The second probe assumed missing keys raised KeyError; its two waiting cases
instead exposed the documented initialization prompt. That raw run is retained
in the same record. Invalid-key tests now use an unhashable list and require
TypeError; the missing-variable controls require an actual child prompt and reply.
