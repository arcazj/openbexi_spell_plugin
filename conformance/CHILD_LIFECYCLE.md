# Native child close/kill qualification

The original parent API reset its child identity before sending close/kill and
sent the wrong context field. It could return success while the child stayed
open. The correction captures the child ID, releases its lock during IPC, checks
the typed context reply, and resets only after confirmed success for that ID.

The context handles these parent requests directly after checking sender,
receiver, message type, exact child instance and immediate parent. Original
one-way GUI/parent notifications remain intact. A rejected lookup preserves the
requested instance ID in its diagnostic, even when the original manager tries
a service alias internally. Empty child state is an idempotent no-op.

An attempted synchronous GUI relay was rejected: real GDB stacks showed the
context's client mutex held while waiting for the GUI, whose forwarded request
needed that same mutex. The abandoned source archive, failed native runs and
stacks are retained; the host IPC bridge remains unchanged.

`evidence/child_lifecycle.json` verifies three checked native source recipes,
the exact runtime image, unchanged host donor `166caff`, input hashes and raw
archives. Four original controls failed; the corrected 14 controls pass:

- close/kill of a prompted child, a finished child, and no child (six);
- two explicit rejected attempts after external removal, retaining identity (four);
- serialized replacement children paused until Run, then prompt and finish
  with exact markers and context inventory checks (four).

The unchanged executor gate passes 23 tests. The unchanged context gate passes
10 tests / 25 actual lifecycles, including two service checkpoint rejections.
The earlier removed-child run rejected correctly but lost the instance suffix
in its diagnostic; its failure remains retained under `ba115d9b...`. The final
runtime is `sha256:3005c0ee34a3d81b54b9894dd2de7f5bc7dd05ad2ab2e5b541ad0eb7c6db71dc`.

This is a diagnostic overlay, not a fresh wheel or release acceptance. No
language rows are promoted. General concurrent replacement/notification races,
uncertain-effect fault injection, Eclipse GUI compatibility and shared native
debugging remain outside this qualification. Composition with shutdown donor
`a97118e` must explicitly chain their disjoint changes to `SPELLexecutor.C`.
