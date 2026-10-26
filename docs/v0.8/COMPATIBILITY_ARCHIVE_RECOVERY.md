# Recovery of historical compatibility evidence

The published v0.6 archive contains the exact child-argument captures previously
unavailable at their Windows paths. All three archive parts and the manifest
match their published SHA-256 digests. Streaming extraction verifies each
selected blob against its content hash and declared size: 1,525 blobs recovered,
including 245 of the 302 hashes referenced by current conformance evidence.
The v0.5 manifest adds no matches for the remaining 57 hashes. The v0.7 raw
archive had matched only five of those 302 hashes.

The original successful child-argument result is
`a984cb549c57477bb62f166b390ead498655fb31874be28d18378d78408de4c4`.
The two failed harness captures are also recovered unchanged. Their compressed
original bytes, original paths and hashes are retained in the evidence folder;
decode `payload` as base64, decompress gzip and verify `sha256` before use.

Historical review restores 67 capture files and verifies 131 immutable source
inputs, plus the manifest-bound `distribution/evidence_sources.py` dependency.
The captured qualifier passes all ten checks for Examples 160–161 and argument
pair syntax. Eight mutations—failed/missing checks, changed source/contract,
missing child execution, changed host/runtime and invalid prompt evidence—are
rejected. No report bytes or expected hashes were rewritten to obtain a pass.

This is a historical evidence review, not a new native execution. Seven recorded
source files differ from current v0.8. The current-source check remains strict;
fresh v0.8 compatibility and the complete 763-requirement gate are unqualified.

Receipts:

- [Archive recovery and unresolved hashes](evidence/compatibility-archive/v06-recovery.json)
- [Historical child-argument review](evidence/compatibility-archive/child-arguments-historical-review.json)
- [Frozen source bindings](evidence/compatibility-archive/child-arguments-source-bindings.json)
- [Original successful capture](evidence/compatibility-archive/child-arguments-original.json)
- [Rejected harness capture](evidence/compatibility-archive/child-arguments-rejected-harness.json)
- [Missing-key assumption capture](evidence/compatibility-archive/child-arguments-missing-key.json)

The raw archives remain available from the repository's
[v0.6 release](https://github.com/arcazj/openbexi_spell_plugin/releases/tag/v0.6).
