# Blocking child failure policy

LRM page 88 requires blocking StartProc to wait for a child's FINISHED, ERROR or
ABORTED state. An ERROR or ABORTED child must then trigger the parent's normal
failure policy. Nonblocking calls return after loading and remain successful
when the child fails later.

Eight native scenarios exercise both child errors and language Abort with the
default ABORT/REPEAT/SKIP/CANCEL choices. The controller observes the terminal
child and paused parent three times before answering. The parent must not return
or create another child attempt while awaiting that answer. CANCEL returns False,
SKIP returns True, REPEAT creates exactly one further successful attempt, and
ABORT terminates the parent without subsequent effects. Continuing parents then
start a successful child in the same execution session.

The report also requires the existing nine mode controls and eight failed-load
and recovery controls on the same installed runtime. It checks retained source,
events, native logs, result files and independent attempt counts. These establish
the three child-state requirements, the Blocking modifier and section 4.16.1.2
when all checks pass. GUI visibility, procedure-library priorities and the whole
StartProc function retain separate acceptance gates.
# Prompt observation correction

The first diagnostic preflight retained four failed ERROR cases and four passed
ABORTED cases. Its controller incorrectly required the child name in the prompt
caption. The original `tskhelper.py` supplies the child identifier and Boolean
return policy in the SKIP/CANCEL options; an ERROR caption can be empty. The
corrected oracle checks those options and all four action codes. Terminal child
state, three observations of the blocked parent, exact attempt counts, return
values and independent recovery effects remain required. The failed run remains
under `.qualification/closure-preflight/c58b9b4ea7d54cc29dcb7654219318e9`.
