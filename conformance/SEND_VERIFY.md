# Composed Send verification options

This bounded checkpoint concerns global Retries, IgnoreCase and ValueFormat
in Send with telemetry verification. It does not qualify complete Send,
ValueFormat across all families, command scheduling, limits or mission drivers.

Language Reference 2.4.4 page54 explicitly permits Send and Verify modifiers
in the combined operation. Pages40 and44 define raw verification values and
global modifiers, with a condition dictionary overriding the corresponding
global value. Page109 defines IgnoreCase for Verify; page111 defines Retries.
The existing OBS decision interprets Retries as repetitions after the initial
acquisition. This tranche asserts actual acquisition counts and one command
receipt chain, preserving that separately documented interpretation.

The retained timing baseline40ef592c94ce47f6af9bbe321046bd66 records three Send
calls rejected for global Retries=0 before any SendCommand RPC. The strict TC
descriptor does not accept these three TM-only settings. The original helper
passes its entire global configuration into both the TC and TM phases.

The checked correction copies the TC-phase configuration and removes exactly
Retries, IgnoreCase and ValueFormat only when a verification condition exists.
It preserves the full configuration for the subsequent original TM verifier.
It does not mutate caller dictionaries or per-condition overrides, change
command-argument formatting, or weaken direct-TC validation. Source-only
RelTolerance, absent from this manual inventory, remains outside the tranche.

The manual describes sending and confirming the command before verification;
it does not require prevalidation of every verification option before sending.
Accordingly a negative Retries value is expected to fail in the original TM
phase after exactly one executed command and before any acquisition. The
oracle retains that precise effect order and rejects implicit retransmission.

Independent native checks exercise actual original helpers and verification
threads against real loopback DSS packets and receipts. The raw/engineering
fixture has distinct values28000/28, case sensitivity has positive and negative
controls, retries count individual RefreshItem RPCs, and every executed command
must have exactly five ordered stage receipts with one delivery apiece. Global
and condition configuration precedence is asserted using independent expected
values rather than implementation-derived results.

The Python-only diagnostic image derives from frozen timing image
`b572950314bb1f3c0858957efa0e77360df9aaa5a6096419e423c2c8248f2305`.
The provenance capture verifies the complete installed source/native set and
the original LIMIT, timing and new Send recipe/preimage chains. It does not
claim a newly independently reproduced wheel. All native observations and
earlier failures are retained under `.qualification/v0.5/send-verify`.
