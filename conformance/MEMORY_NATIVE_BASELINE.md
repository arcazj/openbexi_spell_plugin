# Memory and database lookup baseline

These sixteen probes retain behavior of original SPELL functions through the
native executor, original protobuf services and persistent simulator driver.
They do not promote inventory rows. LRM 2.4.4 pages 100–103 describe memory
reports, comparisons, lookups and driver-defined TM/TC queries. Original helper
code also requires filters described as optional in the manual; the default
filter case records that discrepancy without concealing it.

Six controls exercise the existing GENERIC JSON snapshot profile. Four query
probes cover exact TM/TC identities and inclusive catalog-code constraints.
Six probes specify the proposed GENERIC TM reference-memory profile: a retained
binary DSS telemetry packet, logical addresses given by catalog item codes,
inclusive Begin/End, frozen RAW/ENG values, and deterministic ASCII rows
`address\tname\tJSON-value\n` sorted by address. Type/Source select TM/GENERIC.
CreateGoldenImage with Type='TM' captures the packet; the existing default JSON
snapshot remains supported. These profile probes are expected to expose missing
behavior until production implementation and independent review are complete.

The native DB manager's `mem://` location is bound to project `data/mem`.
Destination report files, packets before/after fixture actions, original RPC
bytes, SQLite effects, observations and complete installed-source provenance
are retained. The only fixture step advances the real DSS engine once; it does
not edit a returned lookup or manufacture an executor result. An outer timeout,
incomplete capture or unexpected prompt is a harness failure.
