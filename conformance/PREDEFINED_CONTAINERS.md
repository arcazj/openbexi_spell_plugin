# Predefined ARGS and IVARS

LRM 2.4.4 page 86 defines two automatically created typed containers that can
store custom variables and be read/edited through the client. Page 89 describes
passing arguments to a child and accessing the resulting ARGS values.

The qualifier joins three independently retained runs on the same installed
native image: 68 typed-container checks, 64 actual dictionary IPC checks, and
10 real parent/child argument checks. Each coverage dimension requires the
corresponding typed and IPC observations; ARGS also requires child arguments.
The IPC procedure proves both containers initially exist, are empty and have
the native DataContainer type, then verifies their edited values after resuming.

The report checks retained sources, native ITEM messages, prompt observations,
dictionary replies, rejected edits, output markers and installed identities.
Malformed input, wrong types, range violations, missing dictionary targets,
chunk boundaries and Unicode round trips remain required controls.

Only `DATA-CONTAINER-ARGS` and `DATA-CONTAINER-IVARS` are allocated. The whole
Var, StartProc and PROC database contracts remain separate. These checks use
explicit `spell.runtime` imports and native client IPC; graphical presentation
in the installed IDEs remains part of later host qualification.
