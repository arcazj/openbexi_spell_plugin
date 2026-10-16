# GENERIC reference-memory candidate

The TM memory profile stores the original binary DSS packet and SHA-256 in the
epoch-scoped ground database. It decodes RAW/ENG values from that captured packet.
Logical addresses are the immutable satellite catalog's item codes. Begin/End
accept inclusive decimal or hexadecimal addresses. Names select a concrete datum;
Address selects one address. JSON state snapshots remain supported independently.

Comparisons apply the same selectors and value format to both captured images.
Reports contain deterministic ASCII rows `address\tname\tJSON-value\n`. A private
report ID binds report retrieval to the exact persisted output of the original
GenerateReport RPC. The native proxy resolves Destination through the configured
SPELL DB-manager file location, applies its extension, writes a temporary in that
directory, and atomically replaces the destination only after successful retrieval.
An existing report survives a failed RPC. Unknown locations and paths leaving the
configured directory are rejected before the remote effect.

TMTCLookup retains the original protobuf schema. The proxy uses a versioned name
envelope when Begin/End are supplied, and the driver applies inclusive item-code
or command-code constraints to the catalog. An empty Name selects a bounded table;
a concrete name excluded by a valid range returns an empty dictionary.

Address integers are bounded to unsigned 32-bit values, ASCII reports to 8192
bytes, and all state/value limits continue to apply. Unknown types, sources,
images, reversed ranges and malformed addresses fail before effect intents.
Authority and epoch checks remain in the original dispatcher and guarded update.

Ten focused checks passed against the original RPC schema and real DSS data,
including proxy file writes. Native execution, independent evidence review and
fresh composed-package regressions are still required. This candidate qualifies
no inventory rows and is not a v0.5 release.
