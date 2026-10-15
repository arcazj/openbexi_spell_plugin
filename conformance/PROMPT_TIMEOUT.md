# Native prompt timeout

LRM 2.4.4 pages 71–72, Example 118, require a timed prompt to select its
configured default. A zero or omitted timeout requires an operator answer;
a timeout without a default does not select an answer.

The [retained baseline](evidence/prompt_timeout_baseline.json) uses the installed
combined child runtime `sha256:2a18e4f10a028df06785a2b6326ee1a3b42fcdba6073b9b051916574ef656b66`.
Both 0.25-second timed defaults remained blocked after five seconds. Five controls
passed: zero timeout, omitted timeout, omitted default, explicit answer before
timeout, and rejection of a malformed timeout. No requirement is promoted.

Run `conformance/run_prompt_timeout.py --image <immutable-image-id>` for the
ten native IPC procedures, including the original `1*MINUTE` timeout and duplicate-answer/cancellation controls
added after the seven-case baseline. The controller never supplies a timed
default. Each report retains source identities, runtime provenance, prompt/answer
events, elapsed time, errors and cleanup results.

The [installed candidate](evidence/prompt_timeout.json) passes all ten cases and
binds two identical offline builds, each with 23 executor, 10 context and eight
fresh-install/removal checks. Its native CIF uses a monotonic deadline and one
synchronized selection among a default, operator answer and cancellation.
Existing prompt, error-policy and child lifecycle regressions must pass before
integration. The central coverage checkpoint and release flags remain unchanged.
Empty defaults and the full Prompt contract remain outside this narrow example.
