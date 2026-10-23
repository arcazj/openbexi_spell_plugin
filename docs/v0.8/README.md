# v0.8 architecture review

Status: **baseline audited; independent review completed; owner authorized
staged implementation under the binding G1 resolutions**. No v0.8 release
or full runtime qualification is established. The normative requirements are in the
[master prompt](openbexi_spell_v0.8_master_prompt.md).

The proposed implementation adds a separate authenticated Listener and isolated
Context authorities, keeps execution management inside each Context, and gives
every execution its own controller epoch and explicit request/accept workflow.
One user can control many executions. The native SPELL engine and driver
semantics remain the qualified v0.7 starting point.

Review these documents in order:

1. [Verified baseline](BASELINE_V07.md), [legacy reference](LEGACY_REFERENCE.md),
   [process/port map](PROCESS_AND_PORT_MAP.md), and [gaps](GAP_ANALYSIS.md).
2. [Architecture and migration](ARCHITECTURE.md),
   [decisions ADR-01 through ADR-12](ARCHITECTURE_DECISIONS.md), and
   [protocol register](PROTOCOL_REGISTER.md), with
   [authority/lifecycle sequences](SEQUENCE_DIAGRAMS.md).
3. [Ownership protocol](CONTROL_OWNERSHIP_PROTOCOL.md),
   [concurrency](EXECUTION_CONCURRENCY.md), and [security/recovery](SECURITY_AND_RECOVERY.md).
4. [Acceptance plan](ACCEPTANCE_PLAN.md), [review findings](ARCHITECTURE_REVIEW.md),
   [test report](TEST_REPORT.md), and [remaining risks](RISKS.md).

The review outcome and owner authorization are recorded in
[G1_REVIEW_RESOLUTION.md](G1_REVIEW_RESOLUTION.md). The initial internal server
contract is [SERVER_CONTRACT.md](SERVER_CONTRACT.md). Release approval is a separate later decision after all runtime,
Compose, Kubernetes, browser, compatibility and CI gates pass. There is no
v0.8 tag, release, production replacement, or completed runtime qualification yet.

Diagrams are generated from editable DOT files in [diagrams](diagrams/).
Every target component in the v0.8 diagram is labeled proposed.

## Initial implementation

The [server foundation](../../server/README.md) provides internal TLS routing
and durable Context blackboards with 51 local CPython 3.13 tests. Execution,
ownership transfer and browser/WSS remain disabled. See TEST_REPORT.md and
KNOWN_LIMITATIONS.md for exact scope and pending gates.
