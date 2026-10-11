# v0.1 qualification

This report records the v0.1 bounded release; its complete source hashes belong
to tag `v0.1.0`. The newer isolated original-source alpha milestone has its own
[qualification and remaining native gates](SOURCE_PORT.md).

The standalone plugin/DSS suite passed 176 tests on Windows x64 / CPython 3.13.15,
with warnings treated as errors. It includes retained independent binary packet/
engine/transport tests, UTC/TIME and common-policy oracles, the actual adapter
through HTTP and binary TCP, unsupported capability rejection, critical-command
rejection and no replay after unknown or confirmed command effects.

An installed core/plugin test executes a Python procedure and a SPELL procedure
in one monitored session and confirms an actual DSS command effect. Packaged
catalogue bytes match their digest; original archive bytes match the pinned SHA.
Exact source/report/package bindings are recorded in
[QUALIFICATION.json](QUALIFICATION.json). Source hashes use canonical Git index
bytes. Local reports and wheels remain in the ignored `.qualification/v0.1/`.
Two builds with `SOURCE_DATE_EPOCH=1791590400` produced identical wheels.

The native local fixture is currently available at
`http://127.0.0.1:8086/api/v1/state`. It has a manual clock and synthetic data.
The Docker test image builds from a digest-pinned CPython base, the retained
hash-bound zlib build and fixed OS library inputs. The final image was rebuilt
after resolving a temporary builder DNS failure with an observed host address;
the original HTTPS source digest check remained mandatory. Docker container start requests
stalled on this host, including a no-network diagnostic container. Those clients
were stopped and their unstarted containers removed; Docker runtime acceptance
is not claimed. The native fixture is the working test service. Compose defaults
to port 8085 for a future successful Docker startup.

Old test stacks were stopped and removed; obsolete image tags and build cache
were cleaned. Eleven obsolete image tags and 248 unreferenced qualification
volumes were removed, as were superseded dangling images and build caches.
Existing operational data volumes, unrelated checkpoints and
Kubernetes images were preserved. Legacy files/history and changed worktrees are
archived outside the fresh repositories. Windows locks left some old qualification
cache material in the migration placeholder, and automatic approval review
blocked filesystem deletion commands; those caches were not silently discarded.

Full original-source CPython porting, every legacy language family and actual
IntelliJ/PyCharm host installation are explicit later gates. The current wheel
contains the Apache-licensed bounded SDK/DSS, not the complete upstream GPL library.
