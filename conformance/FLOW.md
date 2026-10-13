# Native execution-flow qualification

This package qualifies the LRM 2.4.4 execution-flow section, pp.75-78: native
Step/Goto, DisplayStep, unconditional Pause, Abort, Finish, and user-action
configuration and triggering. Child-procedure states, admission, library
priorities, argument propagation and blocking/visibility/automatic modes remain
separate work. Conditional Pause with live telemetry still belongs to the
observation/timing package; this suite verifies its missing-Timeout rejection,
then recovers with unconditional Pause.

Every tested procedure is its actual traced main.py. The controller observes
original native IPC, status, current-line/stage notifications, user-action
messages, real callback effects and AsRun records. It sends original CMD_RUN and
CMD_ACTION requests without replacing the executor, registry, CIF, action
functions or any notification method. All windows/graphical-host rendering
claims remain outside this protocol-level evidence.

The source contains explicit positive, boundary, failure and recovery oracles.
Forward/backward transfers check skipped effects and exact execution counts.
Titles from variables, functions and short-circuit expressions retain literal
jump labels; a title function is evaluated only when its Step executes.
Run-time Goto arguments resolve to registered labels. Nested function jumps stay
in their own frame. Missing labels and cross-function targets stop execution;
an attempted jump into a loop is rejected while ordinary sequential execution
continues, preserving the intervening effect rather than entering an iterator
block without its iterator. DisplayStep changes stage information without
registering a jump label.

Terminal scenarios verify successful versus aborted status, optional/default/
empty messages, no subsequent procedure effects, and finally cleanup. Invalid
terminal arguments are rejected before termination, followed by valid Finish.
Independent processes demonstrate explicit recovery from terminal states.
Pause is observed quiescent before the controller explicitly resumes it,
including consecutive pauses and recovery after rejected conditional arguments.

User-action scenarios verify actual callback execution while paused and running,
replacement of the sole configured callback, INFORMATION/WARNING/ERROR metadata,
idempotent enable/disable/dismiss, suppression while disabled or dismissed, and
reconfiguration after failure. Rejected public arguments preserve the existing
configured action. A callback exception is observed and followed by a successful
replacement callback. These effects and control-state assertions supplement
notifications; a received message alone does not qualify action execution.

## Source decisions

LRM p.77's prose says EnableUserAction and DismissUserAction enable and disable
the trigger, but Example 133 explicitly uses DisableUserAction. The following
paragraph and Example 134 reserve DismissUserAction for permanent removal.
Original exechelper.py and SPELLexecutorImpl.C agree with the examples:
DisableUserAction preserves the configured function/label and disables it;
EnableUserAction re-enables that same function; DismissUserAction resets the
configuration and notifies clients to remove the trigger. This resolves
CMP-LRM244-ERRATUM-USER-ACTION-DISABLE. Tests inspect retained versus absent
ActionLabel metadata and invoke the actual trigger in each state.

Native error handling distinguishes an unknown target (procedure abort) from a
known target whose stack scope disallows transfer (warning and sequential
continuation). The manual's restriction concerns the transfer; it does not
promise that every rejected transfer terminates the procedure.

The manual requires Step's first argument to identify a static literal label;
its title may be computed. The port scans compiled instructions, never evaluates
title expressions, and never guesses a label from a variable or an unrelated
literal. This suite does not promise jump targets in code that CPython removed
as statically unreachable. An early fixture put an unconditional raise before
its target; that fixture was corrected to a skipped-effect marker. Both the
failed fixture run and corrected baseline/candidate runs are retained.

## Checked source corrections

The standalone source_port/flow_patches.py recipe checks exact preimages after
the existing CPython port and preserves original notices:

- The previous scanner required two literal strings and lost a valid Step label
  when its title was a variable/function/expression. flow_analyze.py performs
  conservative operand-stack/control-flow analysis of CPython 3.13 instructions.
  It retains literal first arguments through title evaluation, handles nested
  calls and branch merges, and does not register dynamic first arguments.
- Original SPELLasRun.C used INFORMATION/WARNING/ERROR bitmask values as indices
  into a three-element array. A real WARNING user action triggered UBSan.
  Logging now maps the named constants to INFO/WARN/ERROR explicitly.
- Public user-action helpers reject excess positional arguments before effects.
  SetUserAction requires exactly a function and label, and a documented severity.
  The normal final modifier dictionary and common keyword modifiers remain
  available through the existing wrapper.

The six adversarial scanner tests cover dynamic titles, dynamic first arguments,
unrelated literals, methods, function/exception scopes, keyword/spread calls and
control-flow branches. Native scenarios remain the decisive jump/control tests.

## Reproduce and limits

Run the six local scanner checks with:

    python conformance/flow_analyzer_test.py

Run original native procedure scenarios against a combined candidate containing
both native FLOW corrections and its Python helper overlay:

    python conformance/run_flow.py --image sha256:0eadf2e3b1e961a5e403b79b665e70b22c649179ccde40e86ffceae2ee7559ec

The combined build must retain UI and DATA native corrections; copying a
FLOW-only shared library onto another candidate would overwrite their changes.
The distribution combined-native recipe links all changed units together.
Each run retains traced procedure source, complete IPC observations, native
logs, AsRun records, exact image and input hashes in a unique ignored qualification
directory. No accepted release artifact is overwritten. FLOW conformance does
not by itself qualify a distributable native wheel or the complete v0.5/v0.6
release gates.
