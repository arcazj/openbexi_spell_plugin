# Original-source foundation milestone 0.2.0a1

This page records the `source-v0.2.0a1` Python/RPC milestone. Subsequent native
porting and its separate evidence are in [native port status](NATIVE_PORT.md).

The isolated `openbexi-spell-source` alpha wheel now builds from the exact supplied
2.6.10 archive. It contains 94 original Python modules, five hash-checked patches,
all three original RPC schemas and their generated Python/gRPC modules. The
original registry, factory, driver manager, helpers and models are reused.
Corresponding source, original notices, recipe and patch material travel with this
separate GPL/LGPL wheel. The Apache bounded plugin/DSS remains at v0.1.0.

The patches change only native import failure/deferment, the copied private thread
pool, an explicit urllib.parse import and driver cache cleanup. A real reload test
exposed a `__file__ = None` failure and a path leak in the original cleanup code;
the manager now removes its appended paths and preserves similarly named siblings.
DataContainer and Var require the real native library and raise clearly when it
is absent. No dictionary or replacement native type is counted as support.

Installed-wheel qualification passes 144 checks: 101 source/generated hash checks
and 43 interpreter/isolation/runtime checks. It loads original XML configuration,
creates actual test-driver subclasses through the original factory, verifies
forward setup and reverse cleanup, command broadcast, generic DBMGR creation,
cache cleanup/reload, modifier precedence, nested protobuf values, Unicode, integer
boundaries, thread-pool errors and a real loopback gRPC exchange. Unsupported RPC
returns UNIMPLEMENTED. CTX and EXEC injection remain explicit prerequisites for
executor-bound language calls. There is no automatic builtins injection.

This alpha wheel must use a separate interpreter: the working bounded adapter and
the source-derived wheel both own `spell`. The tested IDE continues using the
qualified bounded wheel. The source alpha is not admitted to the IDE language
extension as a qualified full SPELL runtime.

An unchanged-source compiler probe ran all 63 native units in DTA/UTIL/EXC/WS
against Linux CPython 3.13.14 / GCC 14.2.0:

| Component | Units | Compile | Fail |
| --- | ---: | ---: | ---: |
| DTA | 5 | 3 | 2 |
| UTIL | 8 | 5 | 3 |
| EXC | 31 | 8 | 23 |
| WS | 19 | 10 | 9 |

The build successfully exported diagnostics. These are syntax checks, not link,
load, memory or behavior qualification. Failures include `Python-ast.h`, accesses
to opaque PyFrameObject members and the removed PyTryBlock representation. The
original Step/Goto/frame serialization code requires a deliberate port and
independent behavior tests. [Python's frame API](https://docs.python.org/3.13/c-api/frame.html)
documents the public accessors and CPython 3.13 locals-proxy behavior; reading
those APIs does not resolve the original execution semantics by itself.

The native DTA/UTIL/EXC/WS build and runtime, Step/Goto/warm-start, complete RPC/DSS
service integration and actual JetBrains hosts remain unqualified. The original
source also has site-specific configuration defaults; the test uses explicit local
configuration. Full v0.2 stays open until the native/context/memory/conformance gates
pass. See the [build instructions](../source_port/README.md) and
[source-bound evidence](SOURCE_PORT_QUALIFICATION.json). Local artifacts are in
the ignored `.qualification/v0.2/`; v0.1 evidence remains with its release tag.

Docker cleanup reclaimed another 431.1 MB of unused build cache; the current DSS
image is retained. Automatic approval review rejected deletion of five obsolete
local generated build directories with `blocked by policy`. They remain under
`.qualification/v0.2/`; they are excluded from Git and the released wheel.
