# openbexi_spell_plugin engineering master prompt

Current state: the Apache bounded SDK/DSS is qualified at v0.1.0. The separate
original-source 0.2.0a1 alpha preserves 94 modules, generated RPC and the original
driver lifecycle; see docs/SOURCE_PORT.md. Full v0.2 remains open while the native
DTA/UTIL/EXC/WS and executor semantics are ported and independently qualified.

Build SPELL as an independently installable plugin/library for openbexi_ide,
PyCharm and IntelliJ IDEA, with DSS testing. Do not mix satellite dependencies or
SPELL bootstrap into the neutral IDE core. Start the fresh project at 0.1.0 from
the already tested SDK and DSS components; preserve bounded profile limitations.

The supplied seven manuals (390 pages) and exact 2.6.10 source archive are source
authority. Read the Driver Development Manual carefully. Reuse the existing
language, helpers, adapters, data/model contracts, registry, factory, manager,
original RPC schema and driver lifecycle. Apply small traceable porting patches;
do not reinvent the framework. Preserve applicable GPL/LGPL notices for upstream
code, separate from the existing Apache-licensed modern adapter. No missing
native container may be substituted by an empty dictionary or fake success.

Procedures import SPELL explicitly. A worker installs/injects only its configured
context, EXEC, CIF and driver services; do not inject symbols into Python builtins.
The original library's native DTA/EXC/UTIL/warm-start require CPython 3.13 porting
and independent memory/error/behaviour qualification before compatibility claims.

Preserve exactly three fundamental operating modes: Development (mutable local
Python/SPELL Run/Debug), Monitoring (read-only; no input, execution, prompt answers
or evaluation) and Execution (approved immutable sources, server authority and
qualified operational isolation). Session controller ownership is exclusive,
fenced and leased; execution slots are configurable. Atomic logical-procedure
admission spans operational versions/contexts. Losing a controller pauses safely
and requires explicit reacquisition/resume. Unknown external effects are held,
never replayed automatically.

DSS means Dynamic Satellite Simulator, distinct from Monitoring. Preserve the
existing binary packet identities, immutable epoch/sequence deduplication,
transactional command journal/outbox, telecommand stages, telemetry validity and
freshness, simulator dynamics and optional Kafka transport. Executor and DSS are
separate processes with unambiguous endpoints. The deterministic local fixture
has a manual clock and accurately declares its transport/capabilities.

Account for default/override policy, typed arguments/radix/calibration, TC
confirmation/time-tag/partial-group semantics, TIME absolute/relative/lazy NOW,
Verify composite truth/tolerance/retries/fresh samples, WaitFor deadlines/actions,
TM extended metadata/limits, Prompt type behaviour, read-only SCDB/GDB and scoped
typed data dictionaries, native Step/Goto, child procedure roles/admission,
atomic shared data, memory/ranging/PCS/resources/task/user/time service families.
Record manual version conflicts instead of silently picking convenient behaviour.

Retain Git collaboration, isolated workspaces, captured dependencies and immutable
approved release identities. Full operational server and language functionality
are later migration/conformance gates, not automatic v0.1 claims. Real JetBrains
plugin ZIP installation/activation/Run/Debug/removal and Plugin Verifier evidence
are required for host compatibility. Follow the roadmap, update docs, test actual
services and installed artifacts, remove proven obsolete resources, and commit
each tested phase without rewriting remote history outside explicit scope.
