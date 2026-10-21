# SPELL v0.7 installation and recovery

SPELL v0.7 pairs with OpenBEXI IDE 1.2.0 and the
`openbexi-ide-spell-v07` Linux amd64 Docker desktop. Use Docker Desktop's Linux
engine and CPython 3.13. The supported operational scope is the GENERIC DSS
simulator on a trusted host OS and Docker daemon.

Download the packages, runtime archive and SHA256SUMS from the
[v0.7 release](https://github.com/arcazj/openbexi_spell_plugin/releases/tag/v0.7).
The separate desktop archive and Compose files are in the
[IDE 1.2.0 release](https://github.com/arcazj/openbexi_ide/releases/tag/v1.2.0).

```powershell
docker load --input openbexi-spell-v0.7-linux-amd64.tar.gz
python -m pip install openbexi_spell_host-0.7.0-py3-none-any.whl
```

Install the shared provider, DSS bridge and simulator SDK in the service's
interpreter to use durable Development, read-only Monitoring and approved
Execution. Install the dependencies pinned in the wheel metadata, then install
`openbexi_spell_shared-0.7.0-py3-none-any.whl`,
`openbexi_spell_dss-0.7.0-py3-none-any.whl` and
`openbexi_spell_plugin-0.1.0-py3-none-any.whl`.
The SDK's bounded `spell` namespace belongs in this service interpreter, separate
from the original native SPELL interpreter inside Docker.

The native source wheel remains `openbexi_spell_source-0.6.0-cp313-cp313-linux_x86_64.whl`.
Its bytes, original-library composition and 763 qualified language requirements
are preserved. The changed operational bridge, host/shared packages and
JetBrains ZIP use 0.7.0. The durable binding protocol remains compatible with
the earlier provider; a package version is not a protocol version.

For IntelliJ IDEA or PyCharm, install `openbexi-spell-0.7.0.zip` using
**Settings > Plugins > Install Plugin from Disk**, restart, then configure the
CPython 3.13 interpreter with the matching host wheel. Runtime image:
`openbexi-spell-dss:0.7.0`.

## Admission limits

The private loopback driver admits four concurrent RPCs with 64 KiB messages.
Each durable driver journal admits 100,000 effects in total, at most 16,384 per
procedure run, and 64 MiB of logical effect records, including a full 64 KiB
receipt reservation for each pending intent. Its event journal separately
admits 100,000 events and 64 MiB, with 4,096 events per run. These are logical
record limits; operators must also provision space for SQLite indexes, WAL and
filesystem overhead. A full journal rejects new work before external writes;
it retains existing receipts and uncertainty holds. A duplicate confirmed
request can still retrieve its receipt. Do not delete journal rows to make room.

The service also bounds connected clients (64), nonterminal procedures (128),
execution slots (1..16), input queues, output, replay and audit records. Native
workers use Docker memory, PID, CPU and temporary-filesystem limits. A saturated
authority needs an offline archive and a newly provisioned authority after
shutdown and external-effect settlement; saturation never authorizes replay.

## Offline backup and restore

Stop the durable service and verify its workers have stopped before maintenance.
The OS authority lock rejects backup while a service owns the directory. The
backup includes consistent SQLite snapshots (including committed WAL records),
captured source, effect journals, events and release decisions. Keep backups in
a private location: they contain source and operational evidence.
Archives are bounded to 16,384 regular files, 128 MiB per file and 512 MiB in
total, with a 4 MiB manifest. Links, duplicate names and unsafe paths are
rejected. Check these bounds when provisioning the authority; larger deployments
need a separately reviewed offline archival process.

```powershell
openbexi backup --state-directory C:/service/authority --output C:/backups/authority.zip
```

Restoration requires a new destination on the same supported host layout. Keep
the original project and interpreter identity; this command does not migrate
Windows authority paths to Linux. Provide a JSON receipt with exactly these
fields, replacing every example value with verified evidence:

```json
{
  "backup_sha256": "SHA256_FROM_THE_BACKUP_REPORT",
  "session": "SESSION_ID_FROM_THE_BACKUP_REPORT",
  "minimum_epoch": 123,
  "actor": "operator identity",
  "worker_shutdown_evidence": "reference to verified shutdown of every old worker",
  "effect_settlement_evidence": "reference to the independently checked external effect ledger"
}
```

`minimum_epoch` must be at least the last controller epoch used by the old
authority, including activity after the backup. The operator supplies that fact
from retained service/effect evidence; a snapshot cannot discover later effects.
The backup hash detects corruption and identifies the selected snapshot. It is
not a signature or a substitute for trusted operator evidence.

```powershell
openbexi restore --backup C:/backups/authority.zip --state-directory C:/service/restored-authority --receipt C:/backups/restore-receipt.json
```

Restore verifies the archive's complete inventory, paths, sizes and SHA-256
hashes before installing the new directory. It advances the epoch, audits the
receipt, revokes all restored Execution approvals and marks every nonterminal
procedure `RECOVERY_REQUIRED`. It preserves pending driver intents and never
replays or resumes a procedure. Starting the service rotates credentials again.
Reconcile each exact procedure/fence offline with independently verified worker
shutdown and effect-settlement evidence using `openbexi reconcile`. Approve an
Execution release again only after reviewing its current source/runtime and
revocation history. No live endpoint clears these holds.

This release does not add native checkpoint resume, automatic replay, real
mission/RF authorization, vendor certification or stable v1.0 acceptance.
