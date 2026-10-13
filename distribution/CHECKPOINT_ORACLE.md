# Corrected historical DTA checkpoint oracle

The first integrated rebuild, `97f9a6b22e51489bb9b08396c41184b1`, was rejected by
the unchanged native recorder. Its complete diagnostics remain under that run's
`diagnostic/native` directory. All other runtime reports and all ten context
lifecycle tests passed. The one failing checkpoint case constructed a variable
with both `Range=[0,10]` and `Expected=[3,5,7]`.

The supplied SPELL Language Reference 2.4.4, printed page 85, explicitly forbids
using Range and Expected together. The independently qualified DTA correction
enforces that rule. The old checkpoint fixture contradicted that language
contract; accepting it would undo the qualified correction.

`test_constraints_confirm_and_format` now checks Range and Expected separately,
through both pickle and cloudpickle. It preserves the confirmation and format
state checks, invalid assignment checks, valid recovery and original-value
isolation checks. A new independent test rejects the forbidden combined
declaration and malformed combined checkpoint state, verifies unchanged state
after rejection, and confirms subsequent valid assignment still works.

No runtime recipe or recorder threshold changes for this correction. The
checkpoint suite increases from thirteen to fourteen isolated native tests.
The failed build is retained; successful qualification requires a new pair of
independent offline builds from the corrected test snapshot.
