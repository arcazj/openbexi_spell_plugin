# Database value grammar

LRM p83 places `035` in the database format grammar. It does not require a
Python procedure to parse that spelling. These diagnostics load real configured
GDB files through the original DatabaseFile and ImportValue implementation.
They cover octal values, signed/zero/large boundaries, quoted and non-octal text,
recovery after malformed binary input, and binary/hexadecimal export metadata.
Runtime observations and any correction are pending; no row is promoted.

The separate p79 existence example uses `SCDB.has_key`, an original database
method. The inventory's historical `dict.has_key` label must be reconciled with
that exact manual scope before mapping its evidence. Built-in dictionary
compatibility must not be inferred from SCDB behavior.
