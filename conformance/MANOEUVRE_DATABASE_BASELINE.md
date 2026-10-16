# Manoeuvre database baseline

LRM 2.4.4 p79 Example 138 loads `mmd://Man01/Part1` from the configured
manoeuvre location and extension. That page explicitly makes manoeuvre databases
read-only and describes retrying a failed load with another name. Existing user
database tests already cover the generic load-name prompt, nested `usr://`
locations, typed save/load and failure-preserving writes; these eight probes
address the remaining manoeuvre location and object policy.

Four load cases cover the literal URI, configured extension, empty/custom files,
original octal/hex values, missing/invalid names and recovery. Four object cases
check rejected mutations, detached nested values, rejected save/create and atomic
refresh after a missing file. Configuration XML and all actual files are retained.

The current SCDB view protects only the named runtime SCDB object. The original
database manager otherwise constructs writable file databases for `mmd://`.
The baseline records that behavior before any extension of the read-only view.
No requirement is qualified by preparing or completing this diagnostic capture.
