# Python language contract qualification

The PY package contains 122 original LRM rows. The python_contracts.py suite
assigns positive, boundary, failure and recovery cases to each row, including the
18 published examples. Each individual case records its executed source and
literal expectations. The 14 section rows depend on explicitly enumerated child
cases and pass only when every child passes that evidence dimension. These are
488 checks, not 488 independent procedure processes. Twelve syntax rows repeat
the applicable concrete example assertions, recording their own execution.

Three cases in this suite record CPython migration and rejection, with an explicit
false legacy_spelling_supported field. They do not establish original-spelling
support. Separate native evidence resolves the actual manual scopes: page-79
`SCDB.has_key`, page-83 database octal values, and the page-21 native procedure
`<>` comparison. Broader Python sections remain open; migration checks cannot
qualify a parent section.

The suite runs inside the original native SPELL executor on Linux x86_64 and
GIL-enabled CPython 3.13. It imports the installed original spell.lib, retaining
the native context and registry. A real separate procedure module demonstrates
import, qualified function execution and module cache identity. Nothing patches
builtins or injects language symbols into procedure globals.

The oracle is imported from a small procedure, so its dynamic function objects
do not become procedure checkpoint state. This package qualifies language
evaluation. Native line stepping, jumping, checkpoints, worker recovery and
service lifecycle have separate executor/FLOW acceptance requirements.

## Source decisions for CPython 3.13

The required interpreter is CPython 3.13. LRM p.14 explicitly applies Python
rules and directs readers to the Python reference. Builtins and imported Python
modules retain CPython syntax. The native procedure compiler and AST analyzer
have a separately qualified, token-preserving `<>` compatibility bridge; see
[the bounded comparison evidence](LEGACY_COMPARISON.md).

- The legacy <> comparison: p.21 warns that Python 3 removes it. Builtin compile
  rejects it with SyntaxError; != implements the supported comparison. Those
  rejection checks remain valid independently of native procedure compatibility.
- Python source spelling 035 raises SyntaxError. The supported 0o35 evaluates
  to decimal 29. Invalid digit 0o8, zero and negative octal are tested. The p.83
  requirement describes database input, qualified separately with original 035 text.
- Builtin dict.has_key raises AttributeError; key membership uses the in
  operator. Empty mappings, missing keys, present keys with a None value, and
  unhashable lookup keys are exercised.
- Division performs true division, including two integer operands; oct() uses
  the 0o prefix. A range is an iterable range and dict.keys() a live view;
  explicit list(...) materializes them. These Python 3 behaviors are asserted.
- round uses ties to even (2.5 becomes 2; 3.5 becomes 4). Mathematical functions
  from math are explicitly imported, as required by the no-builtins-injection
  rule; built-in operations keep their normal Python meaning.

The manual also contains defects unrelated to the version migration:

- Example 7's actual last value is a list, despite prose calling it a text file.
  The list and its nested dictionary are tested.
- Page 17 says dictionary keys can have any type. Python requires hashable keys.
  Integer, string and tuple keys work; list keys raise TypeError.
- Example 12 prints This for A[0:3] and A[:3]. The exclusive upper bound yields
  Thi; A[:4] gives This. Empty, negative and clamped ranges are covered, along
  with index errors and a rejected zero slice step.
- A triple-quoted string is an expression, and in first statement position
  becomes a docstring. It is not a lexical comment. The suite checks ignored
  string expression behavior and the resulting __doc__ value.
- Arguments use Python object-sharing semantics: mutating a supplied list or
  dictionary affects that object; rebinding a local parameter does not change
  the caller's variable. This is more precise than p.24's "by reference" wording.

Every failure assertion requires a specific exception type. Every recovery case
performs a rejected operation followed by valid input in the same namespace.
Arithmetic domains, zero divisors, bad source grammar, mixed operand types,
unhashable keys, absent modules/attributes and invalid indexing are real failure
inputs; no canned failure result substitutes for execution. Floating numerical
oracles use relative and absolute tolerances of 1e-13.

## Reproduce

    python conformance/run_python.py --image openbexi-spell-host:v05-common

Each run retains its exact image identity, CPython/platform information, source
hashes, DAP transcript, stderr and JSON report in a new
.qualification/v0.5/python/RUN-ID/ directory. The controller verifies the exact
122-row allocation and all four dimensions. Input hashes are taken before
execution and rechecked afterward. The selected passing report is
conformance/evidence/python.json. No accepted image or artifact is overwritten.
