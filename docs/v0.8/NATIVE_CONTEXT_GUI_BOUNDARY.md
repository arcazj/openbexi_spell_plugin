# Dev38 private Context GUI boundary

This development increment closes native GUI management and controller-roster
entrypoints. It does not implement positive owner ABORT/CLOSE, prompt replies,
setters, full-family pause or handoff. Public execution remains disabled.

The legacy native server accepts client-proposed reconnect keys and reuses
released keys. Login also creates a client roster entry before the Executor CIF
is involved. Context CLOSE, kill, detach, background and recovery handlers have
effects which a guard in the Executor command handler cannot prevent.

The reproduced candidate now treats only its `CTX-TO-GUI` transport specially.
It rejects every nonzero proposed key before `addClient`, uses monotonically
increasing keys, never reuses a closed connection's key, and rejects connection
1025. Exhaustion requires independent worker termination; it never resets the
counter or reconnects. The frozen v0.7 programs remain unchanged.

`REQ_V08_GUI_KEY` reveals only the caller's transport-assigned key. This query
neither logs in nor changes the client roster. The protected host asks over its
owned bridge, then binds that key through an in-process callback. Native peers
cannot invoke this binding callback through the Unix service. Binding is one
attempt only and pins the exact original bridge PID, agent parent, read-only
executable and process incarnation using pidfd. No bearer bootstrap secret is
sent over the native wire or stored in operator configuration. A foreign caller
can learn its own key but cannot register it. Proposed keys cannot displace the
host's connection; key reuse cannot impersonate it after disconnect.

Every GUI request/message except that read-only key query reaches the exact
original native Context's authenticated Unix admission callback before legacy
client lookup, login/logout, management dispatch or forwarding. Admission
requires the bound key and a live bridge. One original login and one exact root
OPEN are permitted, with the original root ID, arguments, CONTROL mode and
automatic/visible/nonblocking flags. Extra or changed fields reject before
native model construction. The original StartGrant is checked through Context
RPC; the independent before-spawn gate and all original member checks remain.
The root OPEN attempt is retained before its authority RPC or native reply, so
unknown outcomes cannot authorize another model/open attempt.

The closed inventory in `NativeGuiBinding` permits bounded private diagnostics,
notification ACKs, and the existing RUN/STEP/PAUSE paths. Those commands still
require their distinct immutable grants at forwarding and final consumption.
The 19 explicitly closed Executor commands/prompt replies/setter requests still
reach the existing CIF denial guards, so their original-Executor negative
oracle remains mandatory. They gain no effect authority. Unknown operations,
Context lifecycle/controller/shared-data/default mutations and direct roster,
background, depth and watch/resource-toggle messages reject before dispatch.
Only bounded ASCII operation labels are retained in denial diagnostics; no
arguments, values, connection keys or authority material are emitted.

## Qualification

Local tests compile the production key-allocation policy with C++17 and check
all 1024 allocations, rejected proposed keys and exhaustion. Python checks
exercise original/forged keys, exact bootstrap fields, concurrent root opens,
lost authority replies, dead bridges, read-only executable/parent binding,
one-attempt binding failure and management/roster defaults. Source reproduction
checks the placement before the actual legacy handlers. Full native compilation
and process controls require the hosted Linux runtime.

Hosted qualification must additionally reject five foreign requests (including
login with a copied Host label and client-roster reading), two proposed keys,
and closed-key reuse. The original admitted family must continue afterward.
Context C must reject 18 management requests and eight roster/state messages,
retain FIRST=1/SECOND absent and PAUSED status, and complete the original
19-operation Executor and stale-controller STEP oracles. Original family,
startup-lane retirement and same-owner RUN/PAUSE/RUN remain required. See the
source-bound `dev38-*` receipts for actual outcomes; this specification is not
an execution result.

## Remaining limits

This is private host/channel admission, not a native multi-user read ACL, a new
owner identity, a durable controller-transfer protocol or an all-participant
barrier. The root bootstrap does not authorize later management actions. Native
child starts on the separate Executor-to-Context path retain their existing
before-spawn family gate and qualification limits.

The original Listener and Executor-to-Context IPC surfaces still require their
own complete management/peer inventories. This increment does not rebuild or
authenticate the legacy Listener management port. Same-worker denial of service,
complete process isolation, production routing, internal lifecycle provenance,
recovery, all deferred queues and positive action compatibility remain release
blockers. Procedures remain approved/trusted; this is not a hostile Python
tenant sandbox. Every full gate in `RELEASE_GATES.json` remains false.


## Dev39 denial response correction

The dev38 PR run [40156748754](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40156748754)
and push run 40156745123 both failed the family profile at the first foreign
login denial probe. The original Context denied login, but the generated error
response used literal `Error` and `Reason` fields. The frozen bridge forwards
only the original `FIELD_*` inventory: those literals disappear. The client
therefore received an error without the required denial marker. All ten root
Executors had reached native-ready before this probe; no successful family
or complete dev38 GUI-boundary result is inferred.

Dev39 uses `MessageField::FIELD_ERROR` (`ErrorMsg`), `FIELD_REASON`
(`ErrorReason`) and `FIELD_FATAL` (`FatalError`). Authorization and the
before-dispatch denials remain mandatory. A regression compiles the generated
C++ response branch against field constants from the immutable original archive,
applies the same original bridge field inventory, and executes the real Python
`Bridge.exchange` response reader. It fails on the prior response with empty
forwarded fields and passes after the correction. Its message shells do not
replace native IPC qualification. The original five foreign denials, key
reconnect checks, 18 management and eight roster-message cases still must
pass through the actual hosted Context/bridge processes.
