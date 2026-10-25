# Remaining native mutation and settlement contract

This inventory is a release blocker list, not a completed implementation matrix.
The private owner protocol currently covers fresh RUN, STEP and main-Executor
PAUSE. Public runtime control remains disabled. The full G3/F gate cannot be
inferred from either the service suite or the native C/D component fixtures.

The native references below are paths inside the independently reproduced frozen
composition, from `docs/reference/SPELL2.6.10-src.zip` and its recorded port recipe.
Candidate changes are applied by [build_admission_context.py](../../host_runtime/build_admission_context.py).
Authority checks live in [commands.py](../../server/src/openbexi_spell_server/commands.py),
[control.py](../../server/src/openbexi_spell_server/control.py) and
[control_journal.py](../../host_runtime/python/control_journal.py).

| Priority | Path | Current evidence / remaining work |
|---|---|---|
| P1 | Initial RUN versus fresh owner intent | Dev35 retires the exact member's startup lane under the shared execution/SQL order. Nine regressions fail dev34; PR native unused-permission rejection passed. Full reliability and all other mutations remain unqualified. |
| P1 | `SPELLserverCif::processMessageCommand`: ABORT | `cancelPrompt()` can complete the transition before the controller sees a command. Admission must precede prompt wakeup; checking only `executeCommand` is insufficient. |
| P1 | Same method: CLOSE/BLOCK | `setClosing()` changes IPC behavior before controller consumption; BLOCK returns without entering that controller. Require an exact early admitted transition and separate termination/hold proof. |
| P1 | `SPELLserverCif::processMessage`: prompt answer/cancel | Both paths occur before the ordinary procedure-target check. Bind prompt identity, original member, owner connection/epoch and answer digest; reject late/copied/observer answers before wakeup. |
| P1 | Other commands and mailbox STOP | STEP_OVER, SKIP, GOTO, SCRIPT, RELOAD, INTERRUPT, FINISH, ACTION and other command IDs are outside the current owner whitelist. `SPELLcontroller::run` handles STOP before `executeCommand`. Close all alternate external paths before exposure; internal safety/lifecycle commands need distinct provenance. |
| P1 | `SPELLserverCif::processRequest` | SET_CONFIG, SET/CLEAR_BREAKPOINT, CHANGE_VARIABLE, CHANGE_RESOURCE and UPD_DICTIONARY directly call processors. Bind exact arguments/member and authorize before evaluation or mutation. The local `procId` variable is not itself a target check. |
| P1 | Child redirection | `processMessage` can route through `processMessageForChild` on ParentId. Nonempty ParentId is denied for admitted RUN/STEP/PAUSE; the full message/request matrix still needs exact target checks. |
| P1 | Native controller-client messages | ADD_CLIENT, REMOVE_CLIENT, BACKGROUND, NODE_DEPTH and watch/resource toggles alter native state outside the command controller. Native GUI ownership cannot substitute for durable v0.8 owner capability. |
| P1 | Deferred/discarded command disposition | A final-admission receipt does not prove completion: pending commands can be discarded, and SKIP/GOTO can be deferred onto tracing. Inventory all mailbox/deferred/prompt items and retain immutable origins through a terminal disposition. Never restamp old items after handoff. |
| P1 | Complete family barrier | Current main PAUSE and observed-Python-thread experiments do not cover every thread, native callback, child, driver operation or future child start. Establish complete participant closure and drained effect/command queues, or keep transfer blocked. |
| P1 | New-owner runtime identity | Original StartGrant remains bound to its original epoch/connection. A separate resumed-runtime identity/channel and fresh new-owner grants must follow a proved barrier. Loosening `_original_grant` or refreshing old commands would violate the contract. |
| P1 | Browser/controller liveness | Explicit `session.close` is tested. Real WSS drop, lease expiry, two-tab reconnect and late disconnect versus accepted transfer still need implemented runtime/browser tests. |
| P1 | Recovery and resource faults | OOM, worker disappearance, Context restart and node partition must retain uncertain holds and fence driver writes. No automatic worker reuse or replacement is qualified. The non-OOM LOADED startup timeout remains a separate compatibility/reliability issue. |
| P2 | Observer read scope | The installed IDE observer fixture reads execution summaries through the gateway. It does not qualify arbitrary native variable/config/resource reads. Define read ACLs and consider evaluation/repr side effects before adding those endpoints. |

Every new mutation needs real native negative cases before its first side effect,
not just a JSON authorization check. Exercise stale epochs, copied capabilities,
owner revocation, timeout/response loss, queued-command races and sibling members.
A blocked or uncertain command must preserve its diagnostic and hold; it cannot
be upgraded into quiescence or transfer permission.

The subsequent full gates also include paired IDE Run/Debug and three-user
browser/WSS behavior, complete compatibility, production-like Compose/Kubernetes
admission/storage/node fencing, recovery, security and release packaging.
[RELEASE_GATES.json](RELEASE_GATES.json) remains authoritative and all groups
remain unqualified.
