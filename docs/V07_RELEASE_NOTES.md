# SPELL v0.7

SPELL v0.7 adds operational safeguards to the accepted native runtime and pairs
with OpenBEXI IDE 1.2.0 and `openbexi-ide-spell-v07`.

- Durable driver quotas reserve space for receipts before admitting effects.
  Saturation rejects new work and preserves receipts and uncertain intents.
- Driver-request admission and pause now share one session critical section,
  preventing a pause race from creating an unnecessary recovery hold.
- Offline authority backup/restore verifies complete archives, preserves pending
  effects, advances the epoch, revokes restored approvals and never replays work.
- The JetBrains workspace safely returns to the editor after resizing,
  restoring or reopening its tool window.
- Procedure code rows stay white, with one soft current-line highlight and
  green/red/amber result cells.

Host, shared provider, DSS bridge and JetBrains packages are 0.7.0. The native
source wheel remains the byte-identical accepted 0.6.0 payload; the independent
bounded simulator SDK remains 0.1.0. The fresh native sequence passes all 61
suites and 2,157 checks. All 763 language requirements remain qualified, with
none open. The installed operational gate passes 90 tests without skips.

See the [exact qualification and artifact hashes](https://github.com/arcazj/openbexi_spell_plugin/blob/v0.7/docs/V07_QUALIFICATION.json),
[installation and recovery](https://github.com/arcazj/openbexi_spell_plugin/blob/v0.7/docs/V07_INSTALLATION.md)
and the [matching Docker desktop](https://github.com/arcazj/openbexi_ide/releases/tag/v1.2.0).

The accepted domain is the GENERIC simulator on a trusted host OS and Docker
daemon, with Linux x86_64 native workers and CPython 3.13. This release does not
add real mission/RF authorization, native checkpoint resume, automatic replay
or stable v1.0 acceptance.
