# Proposed telemetry deadline correction

The original language includes a one-minute GetTM acquisition. The existing
proxy and transport both cap waits at 30 seconds, and their ordinary RPC envelope
also uses that cap. This candidate allows positive finite telemetry timeouts up
to 3600 seconds and uses the same bound in the helper conversion, original RPC
budget, private relay, and transport. Other families retain their existing bounds.

The transport checks live authority while waiting and immediately before
returning an observation. Invalid bounds and revoked authority cannot write an
effect record. A failed wait may be retried against a later real source update.

The new recipe is applied after the full-limit diagnostic recipe and checks all
five source preimages before writing any output. It has not been added to the
integrated production recipe list or accepted as native language qualification.
The unchanged telemetry baseline is frozen separately in C:/obtelemetry_full.

Fifteen focused backend cases passed. The strengthened timed test sends the
original protobuf request over gRPC through the actual private relay and driver
dispatcher to the real DSS transport. It observes the request still pending after
36 seconds, advances DSS to produce a new sample, and checks the returned raw
and engineering value. This tests behavior beyond both the old transport and
relay limits. The corrected no-update recovery test waits for acquisition to
start before advancing the source, avoiding a scheduling race.

The first collection failure was a pytest case-name conversion of a 10,001-digit
integer, not a product failure. Explicit descriptive case IDs preserve that
invalid-input test without changing the integer safety limit. All JUnit results
are retained under .qualification. Native baseline, image provenance, native
candidate cases, independent requirement review, and full composition remain
pending.
