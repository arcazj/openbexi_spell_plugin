# Driver write gate evidence

The exact tested source hashes and commands are in result.json (179 tests) and
compatibility-result.json (241 tests). Both use warnings as errors and have zero
failures/errors/skips. Source identities are hashes of the candidate worktree;
Git head in these local reports is its parent. Hosted CI supplies candidate-SHA
verification after the commit is published.

DSS processes run separately from pytest; dss-processes.jsonl records actual PIDs
and loopback TCP endpoints. These are fixture identities, not native worker
identity attestation. Wheel-smoke.json identifies the isolated installed server
wheel. It is a development build, not a published/qualified release.

The compressed interim compatibility diagnostics retain the strict preimage
errors caused by editing the legacy transport. That edit was reverted. The new
GPL fenced adapter requires Context admission and leaves the original transport
and all immutable patch recipe preimages unchanged.

See ../../DRIVER_WRITE_GATE.md for the exact trust boundary and remaining gates.
No native execution, browser or deployment pass is inferred from this evidence.
