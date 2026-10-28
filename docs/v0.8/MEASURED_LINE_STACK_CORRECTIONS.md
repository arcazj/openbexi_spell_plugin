# Dev76 candidate; fresh hosted acceptance pending

This commit renders measured incoming request IDs into the joined processor's
existing owned identity storage. It preserves the explicit client identity,
original public return API, class layout/vtable, 32-entry cache and five-worker
reuse pool. Concurrency, sanitizers, workloads, deadlines, resource accounting,
acceptance bounds and required audit records are unchanged.

All 226 distinct affected local component checks pass, including original audit,
LINE/filename, callback cancellation/exit and byte-format regressions. The real
message renderer measures 10,000 temporary allocations / 1,070,000 bytes through
the original public return path and zero through owned storage after warm-up.
The original and new rendered bytes match. The processor regression checks 64
live distinct identities, 10,000 joined reuse cycles and oversized destruction.
These measurements do not establish a whole-family pass or explain earlier exits.

Fresh core/native/installed-IDE/lifecycle/audit and original sanitizer-hour
acceptance must run at this exact executable. The following dev75 checkpoint is
the last hosted evidence, not acceptance for this code change. All eleven full
release groups remain open; stable merge/tag/release remain blocked.

Endurance failures now also retain original pidfd exit states and the previous
successful liveness interval. A bounded, optional kernel-log query records only
matching original victim PIDs in that interval; unavailability is explicit.
The original liveness condition and positive workload are unchanged. Observation
errors preserve the original failure; older unknown victims remain unknown.

[Local source-bound receipt](evidence/owned-request-identity-20261028.json).

---

# Dev75 measured ownership changes; full release unqualified

Parent executable: `8184bde25c58cb8b25a71fd794c38d3e3e1828d6` (dev73).
Paired IDE: `c5edbdaecfbc08d252b87d2fb3cc18c4b27d19bc`.

Actual dev73 allocation artifact12777243975 identifies repeated allocations in
`SPELLexecutorImpl::dispatch`, `getFullStack`, `getAvailableStack`,
`SPELLcif::notifyLine` and `SPELLserverCif::completeMessage`. These sampled paths
do not account for every growing byte or establish the cause of earlier exits.

Accepted procedure frames now borrow an exclusively owned filename copy for
their dispatch scope. Eight thread-local slots retain at most4KiB capacity
each after release; deeper nesting and oversized filenames use ordinary local
ownership. The immutable Python filename owner remains alive across nested
calls and GIL release. No borrowed reference leaves the dispatch scope.
Compiled original/corrected filters preserve all28 original cases and CPython
ownership checks.30,000 accepted dispatches allocate30,000 times before and
zero after warm-up. Added16-owner and100,000-byte controls preserve snapshots
past the cache capacity. These are component measurements, not native hours.

Callstack snapshots now copy under the original lock into caller-owned
storage. LINE notifications use eight exclusive scope-owned scratch slots with
ordinary local fallback. Existing duplicate suppression, recursive locking,
sequence/notification order, timestamp formatting and durable writer remain.
CSP metadata is assembled in the message's existing owned field. Original
public getters remain unchanged. A free adapter preserves the original
callstack interface layout and vtable and falls back to the original getters
for other implementations.

Compiled actual old/new native methods execute10,000 LINE and10,000 CSP calls.
Each path falls from30,000 allocations/1,580,000 bytes to zero after warm-up.
The entire10,004-record LINE outputs match,410,174 bytes each, SHA-256
`659f4c27f375b1100c5584cce7b7830990c0ac172b728dc1dab41645a9c56a8e`.
Metadata digests match. Empty/fallback, Unicode, duplicate, error-state,
recursive notification, maximum execution count, sixteen nested scratch owners,
oversized storage and eight concurrent scratch users execute. Transport and
audit sink adapters bound this component's scope; original native and durable
audit acceptance remain mandatory.

All153 affected local components pass, including existing dev73 audit and
callback exit/cancellation regressions. Later deeper-filename controls and
retained LINE measurement also pass; counts overlap. Initial harness compile,
path-collision and formatting failures remain retained. Original sanitizers,
deadlines, concurrency, workload, cgroup accounting, memory limits and required
audit records are unchanged. Retained buffer capacity remains measured; no
sanitizer retention is purged. Fresh hosted native/installed-IDE mandatory and
sustained acceptance must run at the exact dev74 source before qualification.

See [source-bound local receipt](evidence/measured-line-stack-corrections-20261027.json)
and [verified dev73 checkpoint](evidence/qualification-8184bde-20261027.json).
Both dev73 sanitizer hours remain failed, and all eleven release groups remain
open. No stable merge, tag, release or production migration has occurred.

Dev74 full native compilation failed through the interface boundary. Its logs
and unexecuted hour attempts remain retained. Dev75 adds actual interface
compilation and alternate-implementation fallback coverage;109 affected local
checks pass. No native runtime pass is inferred from these components.
