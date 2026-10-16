# Manoeuvre database read-only candidate

LRM p79 requires manoeuvre databases to be read-only. This candidate routes
`mmd://` database objects through the existing native-qualified SCDB read-only
view, preserving the configured backend, location and extension. Reads return
detached values, writes/create/commit fail, and a failed refresh leaves the last
successful contents available. The policy applies to the database object API;
it does not change filesystem permissions or prevent explicit unrelated file I/O.

The correction changes one selection condition in the original database manager.
Its preimage is bound to the independently captured command runtime, and its
full installed-source map is checked during the diagnostic build and capture.
The eight baseline/candidate cases and later independent review must pass before
any requirement promotion. Fresh composed-package regression remains mandatory.
