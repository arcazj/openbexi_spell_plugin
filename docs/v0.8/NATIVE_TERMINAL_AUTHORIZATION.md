# Native ABORT/CLOSE: cryptographic capability and one-use effect boundaries

This private candidate integrates `CMD_ABORT` and `CMD_CLOSE` into the original,
source-derived native Executor. It is not the earlier unintegrated boolean
preflight prototype. It does not enable public runtime, prove terminal cleanup,
release a reservation, reuse a worker or approve ownership transfer.

## Authentication chain

The trusted Context issues the existing independent owner command grant with a
fresh 256-bit random capability. Its durable record stores a hash of that token
and a canonical immutable binding. `_bound` performs constant-time token-hash
comparison and checks the full binding; `_live` checks the original worker origin,
member binding, current owner, epoch, connection generation, live permissions and
deadline. TLS authenticates the Context/worker channel. These are online verified
opaque capabilities, not self-contained signed JWTs. There is no caller-supplied
`cryptographically_verified` Boolean.

The native process sends only the exact operation, immutable request ID, instance
and stage over the existing Unix-domain socket. The C++ wrapper authenticates the
agent PID/UID through SO_PEERCRED; the agent validates the original Executor PID,
parent, executable, process start identity and pidfd before accessing the stored
owner grant and its original worker capability. Neither native input nor a prompt
can replace these capabilities or assign an owner.

## Two distinct single-use boundaries

The original CIF cancels prompts for ABORT and sets `m_closing` for CLOSE *before*
controller dispatch. A controller-only guard would therefore be too late.

1. The new route runs at the top of original `processMessage`, before even the
   original IPC-interruption flag reset. `processMessageCommand` also diverts
   directly to the guarded implementation. It requires a one-way message with
   the exact ProcId and canonical V08ControlRequest; redirection, arguments and
   extra fields fail closed. The transport's descriptive `User` is not authority.
2. Context atomically consumes the original command capability from
   `FORWARD_UNPROVEN` to `TERMINAL_PREPROCESSED_UNPROVEN` before the native call to
   `cancelPrompt()` or `setClosing()`. The state change and audit event commit in
   the same transaction before the agent returns ALLOW.
3. A terminal command reaching original `executeCommand` must pass a second
   one-use transition to `EXECUTION_UNPROVEN` before pending-command changes,
   `startCommandProcessing`, `doAbort` or `doClose`. Live authority is checked again.
4. Original prompt cancellation can own an ABORT transition itself. In that case
   the CIF returns without a second abort dispatch and the ledger remains
   `TERMINAL_PREPROCESSED_UNPROVEN`. This is not a terminal-completion receipt.

Duplicate native requests cannot repeat the early effects or final handlers. The
agent records attempts before RPC; timeout or response loss never retries. A
committed-but-lost reply burns that phase without granting local permission.
Context restart fences retained grants. Unknown effects retain holds.

Revocation is linearized at each Context transaction. An early effect admitted
before revocation is not undone; revocation before the second transaction prevents
the later handler. Permission is not a claim that effects or cleanup completed.

## Explicit private provisioning

All three independent choices are required:

- Native builder: `--native-terminals` (may coexist with `--native-prompts`).
- Context: `native_commands: owner-queue` and
  `native_terminals: owner-terminal-candidate`.
- Worker: `native_child_gate: true`, `native_terminal_gate: true`, and a verified
  native build receipt containing `native_terminal_hooks: true`.

Without those settings existing ABORT/CLOSE denials remain in place. Public
Gateway/Listener execution methods and all full release gates are unchanged.
`CMD_STOP` and other unsupported external commands stay rejected. Internal native
safety operations retain their original provenance and do not gain external grants.

## Executable verification

`test_terminal_commands.py` exercises real Context/SQLite and mutually authenticated
TLS: both commands, token and full-binding corruption, owner/session/expiry/member
changes, phase ordering, concurrent duplicates, audit rollback, restart fencing,
role separation and one physical attempt after lost response.

`test_native_terminal_boundary.py` extracts and compiles the actual composed
`SPELLserverCif::v08ProcessTerminal` and `SPELLcontroller::executeCommand` bodies.
It uses the production C++ JSON/Unix transport, actual process authentication and
real Context grant verification. Scheduler, IPC object and handler dependencies
are instrumented fixtures. Counts verify no original early or controller effect
when permission is denied. This is not a full native interpreter lifecycle test.

The additional hosted native build job reproduces the complete original source
composition and builds/links the Context, Executor and shared runtime with both
prompt and terminal hooks and sanitizers enabled. Its receipt is compilation
proof only, not execution of an enabled terminal lifecycle cohort.

Actual native scheduler behavior on answer/cancel/ABORT/CLOSE, terminal normal/error
outcomes, external driver effects, descendant cleanup and historic startup failure
still require full source-bound execution evidence before Step 1 acceptance.
