# v0.8 prelaunch monitoring event replay

This opt-in-independent endpoint is a **read-only** replay channel. It is not
a browser WebSocket, execution controller, native pause acknowledgment or
evidence of full v0.8 acceptance.

## Contract

The certificate-authenticated desktop gateway accepts POST
`/v1/contexts/{context_id}/events` with an exact JSON object:
`{"after_sequence":0,"limit":32}`. The gateway delegates to a fixed
Listener; the Listener checks the authenticated user's Context scope; the
Context requires the independent `execution:read` permission. Limits are
1..32 and `after_sequence` is a nonnegative integer less than 2^63.
There is no idempotency key, token-in-query, cookie, browser Origin, or
public WebSocket admission. Listener and Context both validate the shape.

Only an explicit allowlist of ownership/claim/reservation transitions is
observable. Native lifecycle, prompt, driver and original audit records
remain unavailable through this route. Every returned row is projected
to `sequence`, `type`, and an optional *canonical UUID* `execution_id`.
Stored event bodies, operator identities, messages, capabilities, and
other fields are never returned. The result includes
`context_id`, `after_sequence`, `next_sequence`,
`latest_sequence`, `has_more`, `events`, and
`runtime_enabled:false`.

If a page fills, `next_sequence` is the last visible event. Otherwise
it advances to the highest audit sequence, including filtered internal
events, so a client does not repeatedly rescan hidden rows. Cursor values
never move backward even when supplied above the latest sequence.
Rows are read inside a single SQLite snapshot, with no mutation and no
reservation/ownership changes.

## Test obligations and limitations

Real-mTLS regression tests must check Context-scoped certificates, read ACL,
cross-Context denial, forged fields, bool/float/negative/oversize cursors,
idempotency-key rejection, multi-page monotonic replay, suppression of raw
native secrets and unchanged audit capacity. The explicit denylist of
browser headers remains active in the transport layer.

This does not qualify browser/WSS connection liveness, three-tab behavior,
native RUN/DEBUG, Git collaboration, participant barriers, or production
edge deployment. The full v0.8 release remains blocked with all mandatory
`RELEASE_GATES.json` groups unchanged.
