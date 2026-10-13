# Send verification checkpoint result

All 18 new native checks, 54 unchanged command checks and 36 unchanged timing
checks passed on
`sha256:a39cabc68099f9c6857309d0fa6fa6533528a0133a2dfaaf9f0b9218228cc0f7`.
The canonical report is `conformance/evidence/send_verify.json`; it binds the
source inputs, complete diagnostic provenance chain and raw report hashes.
The checkpoint adds no qualified inventory rows and leaves full v0.5/v0.6
acceptance false.

Retained reports below `.qualification/v0.5`:

| Run | Result |
| --- | --- |
| send-verify/7107fff5a1484903ab405a660d4f0a42 | Baseline: 16 failed composed checks and two passing direct-TC controls |
| send-verify/62c00be9a45640858e436b4c17202b99 | Corrected: 18/18 passed |
| send-verify-cmd/6f87812b7ee24481a533c02db31a4cf9 | Command regression: 54/54 passed |
| send-verify-timing/89c4fcf8682a488cbcac280b580f0839 | Timing regression: 36/36 passed |

Every baseline composed failure occurs before a SendCommand RPC. The candidate
executes exactly one command for each composed call. Global Retries=2 permits
three acquisitions, Retries=0 performs one, and a condition-specific zero
overrides global three. RAW telemetry is 28000; ENG is 28. String case controls
and mixed condition/global formats retain their stated semantics. Caller
dictionaries remain unchanged, failed verification never resends implicitly,
and direct commands still reject the three verification-only settings.

Negative Retries is rejected after the one command, before acquiring telemetry.
That ordering follows the original Send-then-Verify phases; the manual does not
promise validation of all verification options before command transmission.
This observable effect is part of the failure oracle, not hidden as an
effect-free validation claim.

Only `spell/lang/helpers/tchelper.py` changes. Its exact post-timing preimage
`c40677470312d45aa2d28de92ab05aaa116e1d1d6644038dc94957bcbe6c8ec8` becomes
`551c3990be8393c8eead143ab4da509e368418b72425e573370d22f910630c58`.
The checked recipe preserves original notices and both byte sequences. The
baseline's 49 exact input files are additionally retained before the runner
input list was extended to bind `SEND_VERIFY.md`; the native oracles are
unchanged between baseline and candidate.
