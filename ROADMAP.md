# openbexi_spell_plugin roadmap

## v0.1 â€” independent plugin and DSS testing baseline

Retain the bounded SDK/TIME/common policy and existing DSS engine/packets/
transactional command journal. Package independently; add a loopback deterministic
fixture and a thin SDK-to-DSS binding. Exercise installed local and shared CLI
runs. Preserve exact original source/manuals and licenses. Fresh Git history and
current docs replace the old monolith's release series, without inheriting its
acceptance claims.

This bounded v0.1 phase is complete on Windows x64 / CPython 3.13. Docker image
building is verified; container startup remains unqualified on this host. See
[qualification](docs/QUALIFICATION.md) and its source/package manifest.

## v0.2 â€” original-source library foundation

Reproducibly build/install from the supplied 2.6.10 archive; record source hashes,
original notices and small traceable patches. Generate original RPC stubs. Reuse
language/helpers/models/registry/factory/driver manager; port native DTA, EXC,
UTIL and warm-start to supported CPython 3.13 APIs. No empty-dictionary fallback
or invented substitute counts as supported native containers. Qualify imports,
context/EXEC/CIF injection, service setup/cleanup, memory/error paths and original
behaviour against independent tests. Keep the v0.1 bounded alias separate.

The source/RPC alpha `0.2.0a1` preserves 94 source modules and generates the
original schemas. All 143 native library units now pass compilation checks;
the original standalone executor links its 120 units and passes 23 command
checks, including fresh-process crash recovery with native data. See
[source port status](docs/SOURCE_PORT.md), [executor recovery](docs/EXECUTOR_RECOVERY.md)
and [native context/server qualification](docs/CONTEXT_SERVER.md). The listener,
context and one real server procedure now start, run and exit normally through
original IPC; process/socket regressions also pass. Broader native controller/CIF behavior,
service failure/restart/recovery and ownership/error-path checks still gate v0.2.
The [service milestone](docs/SERVICE_RUNTIME.md) now qualifies the actual service
executable, native runtime data, worker result, Close, Python `finally` and normal
child exit. Its nine binding checks and all preceding native/recovery checks pass
on the newly pinned CPython 3.13.15; the earlier 3.13.14 build skipped trace-triggered
cleanup in an independent CPython probe.

The [controller milestone](docs/CONTROLLER_RUNTIME.md) now passes five original
server scenarios and 13 context lifecycle runs, including Step/Skip/Goto,
rejected jumps, paused variable editing, prompts, abort cleanup and cancellation
of a missing executor's reconnect worker. Remaining CIF/service/error-path gates
stay open.

The [service restart milestone](docs/SERVICE_RESTART.md) passes Python-failure and
process-loss injection through the original watchdog. Both require a new verified
native executable, reaped previous child, worker result and normal context
shutdown. All 15 lifecycle runs pass; this is cold restart, not service checkpoint
resumption or live-service reconnection.

The [CIF milestone](docs/CIF_RUNTIME.md) adds real blocking parent/child execution,
shared-data type/key/deletion checks and timed WaitFor. It fixes a child-launch
lock cycle and passes all 18 lifecycle runs with the preceding native gates.

The [ownership milestone](docs/IPC_OWNERSHIP.md) qualifies failed-socket descriptor
accounting, atomic worker admission/drain, eight concurrent requests cancelled by
two disconnect callers and process listener unregistration. All preceding native
gates and 18 lifecycle runs pass. Native installation, reconnect semantics and
remaining ownership review still gate v0.2.

## v0.3 â€” real IDE host plugins

Implement a versioned OpenBEXI extension and an actual IntelliJ Platform ZIP with
accurate module dependencies, settings/actions/tool window and the shared Python
library. Verify and exercise install/activate/explicit-import Run/Debug/uninstall
in real private IntelliJ IDEA and PyCharm sandboxes. Plain Python IDE operation
survives plugin removal. A Python wheel alone is not JetBrains compatibility.

## v0.4 â€” drivers and operating modes

Reuse the original Driver Development Manual and framework lifecycle. Bridge the
original RPC schema explicitly to the existing binary/Kafka DSS transport; test
every required service family, uncertainty, fencing, recovery and cleanup. Retain
exactly Execution, Monitoring and Development. Move reusable operational server
components out of the legacy archive only when their dependencies and immutable
release identities are consciously migrated.

## v0.5 â€” full SPELL conformance

Allocate all 763 existing inventory rows; historical 195 ADAPTED / 79 PARTIAL /
489 GAP classifications are not automatically promoted. Resolve every manual/
source version conflict, native Step/Goto/warm-start and full service family gate.
Require independent positive, boundary, failure and recovery evidence for every
supported contract. Unsupported requirements stay open and prevent full release
acceptance; import checks and generated stubs do not establish conformance.

## v0.6 â€” distribution and compatibility

Qualify reproducible installable artifacts, clean installation/removal, upgrades
from supported earlier releases, and complete Python/SPELL workflows in
openbexi_ide, IntelliJ IDEA and PyCharm. Publish an explicit supported platform
matrix backed by actual host tests, source/license provenance and user docs.
Qualify the shipped DSS image at runtime as well as build time. Coordinate the
neutral IDE's independent release numbers and required shared-service features.

## Later â€” operational qualification and stable release

Proposed v0.7 covers security/capacity and operational recovery/backup acceptance;
v1.0.0-rc1 freezes features for end-to-end acceptance before stable v1.0.0.
These later releases remain outside the current execution target of v0.6.

The active sequence is v0.2, v0.3, v0.4, v0.5 and v0.6. Update documentation and
commit each tested phase in order. A partial milestone may be committed, but
its parent release remains open until every release gate has passed.
