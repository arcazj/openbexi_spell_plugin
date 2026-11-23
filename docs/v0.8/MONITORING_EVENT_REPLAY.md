> **Qualification status:** full v0.8 remains unqualified. [Current results and next work](CURRENT_STATUS.md) supersede historical summaries below; original evidence and acceptance limits remain binding.

# v0.8 prelaunch monitoring event replay

## Browser workspace

The v0.8.0 Gateway can serve a certificate-authenticated workspace at
`/workspace/`. Install the server's `browser` extra. The pinned wheel checksums
are in [the browser dependency lock](../../server/requirements-browser.lock).
Set `browser_origin` to the Gateway's exact HTTPS origin and put its host and
port in `allowed_hosts`. Provide sufficient `max_handlers` for the intended
number of simultaneous users. Each WebSocket holds one handler. The Gateway
reserves six slots for other requests and caps concurrent streams at 32.
Forty-eight handlers support the three-user and twenty-observer qualification
fixture.

Each browser uses a distinct provisioned client certificate. The workspace
maps its HTTPS actions through the existing Gateway, Listener and Context
authorization. Same-origin JSON requests carry the current controller proof.
Proofs and heartbeat challenges live in the page's memory. Closing a tab stops
renewal. The **Disconnect** button closes its known logical sessions.
**Reconnect control** requires a separate operator action.

The secure WebSocket at `/workspace/contexts/{context_id}/events` negotiates
the `openbexi.events.v1` subprotocol. The Gateway checks the browser origin,
client certificate, Context scope and execution read permission before it
accepts the connection. The browser sends a bounded `{"after_sequence":0}`
cursor and receives the same redacted replay page described below. Subsequent
reads keep the cursor in that tab. After reconnection the browser requests the
next page and refreshes public execution state. Each replay rechecks the live
Context policy. Mutations travel through explicit HTTPS actions. Connection
loss leaves their outcome for the operator to reconcile.

The browser qualification script requires Playwright Core 1.65.0 and its
pinned Chromium 158.0.8127.18. Provision independent `alice`, `bob`, `observer`
and `watch-01` through `watch-20` certificate directories. Each contains the
role-specific `tls.pem` and `tls.key`. Alice's `connection.json` supplies
the Gateway URL. Configure trust for the fixture CA. Run
`node scripts/qualify_v08_browser_workspace.cjs <profiles> <new-evidence-directory>`.
The fixture needs one unspent assigned worker and an approved procedure that
finishes after Run. The test covers explicit A–B–A ownership transfer while a
procedure is reserved, stale proof rejection, observer replay and the later
native launch and result. Transfer of a running family has separate native
barrier and host-evidence requirements.

## Desktop HTTPS replay

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
