# Legacy comparison in native procedures

The native compiler and AST analyzer accept the `<>` spelling documented on
page 21 of the SPELL Language Reference 2.4.4. A tokenizer translates only the
operator token to `!=`; source positions, encodings, strings and comments are
preserved. The checked patch runs after the qualified TIME correction.

The original installed runtime fails all eleven legacy syntax cases. The
corrected runtime passes all fifteen cases: value/boundary comparisons, raised
comparison errors and recovery, strings/comments, Unicode, multiline and nested
code, mixed modern/f-string syntax, chained comparisons, native jumps, a modern
control and three malformed-source rejections. Exact source, native logs,
compiled artifacts and diagnostic failures are retained.

[Composed evidence](evidence/legacy_compare_composed.json) binds these observations
to freshly installed wheels and the exact diagnostic donor. Independent builds
produce identical native artifacts and wheels; the complete regression sequence
is recorded in the [current checkpoint](../docs/LANGUAGE_CHECKPOINT.json).

Only `CMP-LRM244-OPERATOR-PYTHON-LEGACY-NOT-EQUAL` is newly qualified.
Imported Python modules and builtins `eval`/`compile` retain CPython syntax.
The two parent Python section rows are qualified by separate aggregate evidence.
Full v0.5, v0.6 and stable 1.0
acceptance remain false.
