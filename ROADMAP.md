# openbexi_spell_plugin roadmap

## v0.1 — independent plugin and DSS testing baseline

Retain the bounded SDK/TIME/common policy and existing DSS engine/packets/
transactional command journal. Package independently; add a loopback deterministic
fixture and a thin SDK-to-DSS binding. Exercise installed local and shared CLI
runs. Preserve exact original source/manuals and licenses. Fresh Git history and
current docs replace the old monolith's release series, without inheriting its
acceptance claims.

This bounded v0.1 phase is complete on Windows x64 / CPython 3.13. Docker image
building is verified; container startup remains unqualified on this host. See
[qualification](docs/QUALIFICATION.md) and its source/package manifest.

## v0.2 — original-source library foundation

Reproducibly build/install from the supplied 2.6.10 archive; record source hashes,
original notices and small traceable patches. Generate original RPC stubs. Reuse
language/helpers/models/registry/factory/driver manager; port native DTA, EXC,
UTIL and warm-start to supported CPython 3.13 APIs. No empty-dictionary fallback
or invented substitute counts as supported native containers. Qualify imports,
context/EXEC/CIF injection, service setup/cleanup, memory/error paths and original
behaviour against independent tests. Keep the v0.1 bounded alias separate.

The source/RPC alpha milestone `0.2.0a1` is implemented and independently checked:
94 source modules, generated original schemas and the original driver lifecycle
with traceable patches. See [source port status](docs/SOURCE_PORT.md). The full
v0.2 phase remains open: unchanged native compile diagnostics identify 37 failing
units out of 63. Port and qualify DTA/UTIL first, then EXC control flow and WS
serialization, and only then admit this runtime to IDE/plugin host qualification.

## v0.3 — real IDE host plugins

Implement a versioned OpenBEXI extension and an actual IntelliJ Platform ZIP with
accurate module dependencies, settings/actions/tool window and the shared Python
library. Verify and exercise install/activate/explicit-import Run/Debug/uninstall
in real private IntelliJ IDEA and PyCharm sandboxes. Plain Python IDE operation
survives plugin removal. A Python wheel alone is not JetBrains compatibility.

## v0.4 — drivers and operating modes

Reuse the original Driver Development Manual and framework lifecycle. Bridge the
original RPC schema explicitly to the existing binary/Kafka DSS transport; test
every required service family, uncertainty, fencing, recovery and cleanup. Retain
exactly Execution, Monitoring and Development. Move reusable operational server
components out of the legacy archive only when their dependencies and immutable
release identities are consciously migrated.

## Later — full conformance and operational acceptance

Allocate all 763 existing inventory rows; historical 195 ADAPTED / 79 PARTIAL /
489 GAP classifications are not automatically promoted. Resolve every manual/
source version conflict, native Step/Goto/warm-start and full service family gate.
Complete security, capacity, platform, backup/upgrade and actual host acceptance.
Update documentation and commit every tested bounded phase.
