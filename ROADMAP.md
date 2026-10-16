# openbexi_spell_plugin roadmap

## v0.1 — independent plugin and DSS testing baseline

Retain the bounded SDK/TIME/common policy and existing DSS engine/packets/
transactional command journal. Package independently; add a loopback deterministic
fixture and a thin SDK-to-DSS binding. Exercise installed local and shared CLI
runs. Preserve exact original source/manuals and licenses. Fresh Git history and
current docs replace the old monolith's release series, without inheriting its
acceptance claims.

This bounded v0.1 phase is complete on Windows x64 / CPython 3.13. Docker image
building and the later [in-container command workflow](docs/DSS_CONTAINER_RUNTIME.md)
are verified; host-published container access remains unqualified. See
[qualification](docs/QUALIFICATION.md) and its source/package manifest.

## v0.2 — original-source library foundation

Reproducibly build/install from the supplied 2.6.10 archive; record source hashes,
original notices and small traceable patches. Generate original RPC stubs. Reuse
language/helpers/models/registry/factory/driver manager; port native DTA, EXC,
UTIL and warm-start to supported CPython 3.13 APIs. No empty-dictionary fallback
or invented substitute counts as supported native containers. Qualify imports,
context/EXEC/CIF injection, service setup/cleanup, memory/error paths and original
behaviour against independent tests. Keep the v0.1 bounded alias separate.

This phase is complete on Linux x86_64 / Debian 13 / GIL-enabled CPython 3.13.15.
The qualified native foundation includes:

- All 143 original native library units; the 120-unit standalone executor and
  23 command checks, including fresh-process crash recovery with native data.
- Original listener/context/server/service operation, controller commands,
  child execution, shared data, scheduler waits and watchdog cold restart after
  Python failure or process loss.
- Socket/worker/process-listener ownership, concurrent disconnect, pending-service
  login cancellation, watchdog duplicate prevention and monotonic status waits.
  Live procedure/service reconnection also preserves and resumes the original
  child after context failure. The current context suite passes 25 lifecycle runs,
  including three live reconnect repetitions for each process kind.
- The separate diagnostic package 0.2.0, with seven fresh-image installation
  checks, actual installed listener/context/executor operation and clean removal.
  Two package builds from one qualified native build are identical;
  independent native rebuild reproducibility
  remains a distribution requirement.

See [execution status](docs/EXECUTION_TO_V06.md),
[installed native package](docs/NATIVE_PACKAGE.md),
[executor recovery](docs/EXECUTOR_RECOVERY.md) and
[context ownership](docs/CONTEXT_OWNERSHIP.md) for exact evidence and scope.
Historical milestone reports retain their own source snapshots.

The installed artifact and native foundation acceptance are recorded in
[native package qualification](docs/NATIVE_PACKAGE_QUALIFICATION.json).
[Native service checkpoint requests](docs/SERVICE_RECOVERY_SEMANTICS.md) are now
explicitly rejected before startup; original cold restart, live reconnection and
ordinary procedure checkpoint recovery are independently qualified.
See [live reconnection](docs/LIVE_RECONNECT.md) for the latest runtime evidence.
The example driver remains a local template fixture; operational
DSS driver qualification follows in v0.4 and full inventory conformance in v0.5.

## v0.3 — real IDE host plugins

Implement a versioned OpenBEXI extension and an actual IntelliJ Platform ZIP with
accurate module dependencies, settings/actions/tool window and the shared Python
library. Verify and exercise install/activate/explicit-import Run/Debug/uninstall
in real private IntelliJ IDEA and PyCharm sandboxes. Plain Python IDE operation
survives plugin removal. A Python wheel alone is not JetBrains compatibility.

Complete for local Development on Windows x64 hosts with the Linux x86_64
CPython 3.13.15 runtime in Docker. The installed OpenBEXI extension, actual
PyCharm and IntelliJ plugins, debugger, prompts, cleanup and removal all pass
on the same 0.3.0 artifacts. See [host integration](docs/HOST_RUNTIME.md) and
[the exact acceptance manifest](docs/HOST_QUALIFICATION.json).

## v0.4 — drivers and operating modes

Reuse the original Driver Development Manual and framework lifecycle. Bridge the
original RPC schema explicitly to the existing binary/Kafka DSS transport; test
every required service family, uncertainty, fencing, recovery and cleanup. Retain
exactly Execution, Monitoring and Development. Move reusable operational server
components out of the legacy archive only when their dependencies and immutable
release identities are consciously migrated.

Complete for the declared GENERIC simulator profile on Windows x64 service /
Linux amd64 Docker, with IDE 0.3 as the neutral durable authority. Original native
factory/models and all ten RPC families, actual binary TC/Kafka TM, immutable
approved Execution, Monitoring rejection, controller fencing, alias admission,
lost-acknowledgement holds, watchdog, pause, revocation and installed wheels are
qualified in [driver runtime](docs/DRIVER_RUNTIME.md) and
[its exact evidence](docs/DRIVER_QUALIFICATION.json). Critical/scheduled commands,
full mission semantics and unsupported vendor contracts remain explicit v0.5
requirements; no real-mission approval is inferred from simulator acceptance.

## v0.5 — full SPELL conformance

Allocate all 763 existing inventory rows; historical 195 ADAPTED / 79 PARTIAL /
489 GAP classifications are not automatically promoted. Resolve every manual/
source version conflict, native Step/Goto/warm-start and full service family gate.
Require independent positive, boundary, failure and recovery evidence for every
supported contract. Unsupported requirements stay open and prevent full release
acceptance; import checks and generated stubs do not establish conformance.

In progress: [the full inventory](conformance/README.md) has **573 qualified /
190 open** requirements. The [current record](docs/LANGUAGE_CHECKPOINT.json)
binds all 48 native suites to identical offline rebuilds. Command scheduling,
catalogue sequences, Group/Block execution and displays add 50 requirements;
all prior 523 requirements pass on the same runtime. Full v0.5/v0.6 acceptance
and final host workflows remain open.

## v0.6 — distribution and compatibility

Qualify reproducible installable artifacts, clean installation/removal, upgrades
from supported earlier releases, and complete Python/SPELL workflows in
openbexi_ide, IntelliJ IDEA and PyCharm. Publish an explicit supported platform
matrix backed by actual host tests, source/license provenance and user docs.
Qualify the shipped DSS image at runtime as well as build time. Coordinate the
neutral IDE's independent release numbers and required shared-service features.

The [current checkpoint](docs/LANGUAGE_CHECKPOINT.json) passes two independent
offline native builds with identical wheel bytes and eight install/removal tests
per build. Fresh host/DSS images pass installed provenance checks. Full language
conformance, versioned upgrades, production packaging and final installed
OpenBEXI/IntelliJ/PyCharm workflows remain open.

## v0.7 — operational qualification

Qualify installed service security/capacity, controller fencing, uncertain-effect
handling, overload and backup/recovery. Bind the checks to the shipped artifacts
and declared simulator/platform scope.

## v1.0.0-rc1 and stable v1.0.0

Freeze features for end-to-end acceptance, resolve candidate defects and repeat
affected gates before stable release. Publish concise release notes, installation
and recovery instructions, supported platforms and exact artifact identities.
The execution target now includes stable v1.0.0; see the
[release acceptance plan](docs/STABLE_RELEASE_PLAN.md).

The remaining sequence is v0.5, v0.6, v0.7, v1.0.0-rc1 and v1.0.0. Update concise
documentation and commit/push each accepted release to GitHub master in order.
A partial milestone may be committed, but
its parent release remains open until every release gate has passed.
