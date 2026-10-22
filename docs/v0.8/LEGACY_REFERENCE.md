# Legacy reference, with evidence boundaries

`DOCUMENTED-LEGACY`: references below use one-based PDF page numbers, including
front matter. Originals and SHA-256 hashes are recorded in the baseline audit.
They describe behavior, not an instruction to restore Python 2 or Eclipse.

| Reference | Finding and boundary |
|---|---|
| Server Manual 2.4.4, PDF p5 | Listener receives initial client connections; `ListenerPort` and `ContextListenerPort` are separate configuration fields. Example values 9980/9981 are examples, not mandatory modern ports. |
| Server Manual 2.4.4, PDF p5–6 | Context configuration names an executor program and other runtime programs. Process roles are explicit. |
| Server Manual 2.4.4, PDF p8 | Driver configuration includes enabled interfaces and `maxproc`, the per-Context parallel procedure limit. |
| Server Manual 2.4.4, PDF p8–9 | Context has a unique ID, driver, spacecraft and GCS configuration. Driver settings apply to procedures in that Context. |
| Server Manual 2.4.4, PDF p4 | Legacy interpreter dependencies are Python 2-era; they are not the modern execution engine. |
| GUI User Manual 2.4.4, PDF p17, p49–50 | Per-procedure CTRL/MON indicator; monitoring disables execution controls and prompt input. This does not establish a modern persisted consent/fencing protocol. |
| GUI User Manual 2.4.4, PDF p48 | Loss of the controlling GUI pauses procedures; a driver operation can defer processing a pause command. Modern disconnect grace and fencing are explicit design changes requiring tests. |
| Driver Development Manual 2.4.4, PDF p15 | Command stage/status updates are a driver contract, distinct from the core adapter's UI presentation. |
| Driver Development Manual 2.4.4, PDF p24–25, p37 | Interface setup receives Context/driver configuration; cleanup belongs to lifecycle, and Time has its own interface. No generic vendor wire format or GCS→DSS topology follows merely from the term driver. |
| Language Reference 2.4.4 | Behavioral reference for language helpers; pair it with the existing qualified requirement corpus rather than equating CPython 3.13 syntax support with SPELL semantic parity. |

Source available here is **SPELL 2.6.10**, in `docs/reference/SPELL2.6.10-src.zip`,
not 2.4.4 source. Its Listener, Context, Executor, IPC and driver files can
explain the published v0.7 implementation. They cannot establish byte-for-byte
2.4.4 protocol compatibility. No vendor GCS specification is provided.

Source review inspected `lib/SPELL_LST/src/SPELLlistener.C`,
`lib/SPELL_CTX/src/SPELLcontext.C`, `lib/SPELL_CTX/src/SPELLexecutorManager.C`
and `lib/SPELL_IPC/src/SPELLipcMessage.C`. The Context source sets an executor's
controlling client, rejects attaching a second controller, and separately
registers monitoring clients. Executor management uses process ownership;
IPC messages carry sender/receiver, sequence, type and key fields. File hashes
and line references are in the baseline audit. These findings describe the
available 2.6.10 source, not unverified 2.4.4 framing or modern consent tokens.

`VERIFIED-v0.7`: `host_runtime/python/native.py` uses native requests
`REQ_GUI_LOGIN`, `REQ_CTX_INFO`, `REQ_OPEN_EXEC`, `REQ_EXEC_INFO`, and
`REQ_CLOSE_EXEC` through `spell-host-ipc`. This is actual code evidence, stronger
than inferring messages from diagram arrows. Exact original message encoding
remains encapsulated by the accepted bridge; it is not a public v0.8 protocol.

`UNKNOWN`: universal legacy controller-transfer semantics, exact 2.4.4 wire
framing parity, site GCS APIs, GCS→DSS routing, and real spacecraft operation.
Do not fill these gaps with invented port numbers or vendor protocols.

`TARGET-v0.8`: retain the qualified native behavior and driver facade behind
typed, Context-bound adapters. Add modern server ownership/concurrency outside
the language semantic layer. Any changed native recipe or facade requires new
compatibility qualification; old evidence must remain tied to its own sources.
