# Native durable shared Development

`shared_plugin/` supplies the optional GPL `openbexi-spell-shared==0.4.0.dev1`
provider for the neutral IDE's `openbexi.shared_backends.v1` contract. It depends
on the accepted `openbexi-spell-host==0.3.0` wheel and uses the original native
host image unchanged. It does not alter the earlier local-host acceptance files,
wheel, ZIP, image or release tag.

The full service/operator guide lives in the sibling IDE repository:
[native shared service](../../openbexi_ide/docs/NATIVE_SHARED_SERVICE.md).
The matching source/artifact evidence is recorded in
[SHARED_QUALIFICATION.json](SHARED_QUALIFICATION.json).

The installed entry point returns a trusted service provider with `api=1` and
`bind()`, `create()` and `recover()`. A bound worker implements `start()` (native
user code paused), `resume()`, confirmed whole-container `pause()`, bounded
`poll()`, prompt `input()` and owned `close()`. The core controls grants; the
provider cannot release its own slot through a Python checkpoint. Bindings persist
the native image ID, provider version and Development profile with each procedure.

The provider copies the verified Git capture into a private container, retains
the native entry pause through startup, forwards ordered native DAP output and
prompts, and exports completed results separately from captured source. Shared
pause freezes every process using Docker, with inspection before the service
releases a slot. It is not shared native debugger stepping or stack inspection.
Controller handoff and lease expiry require explicit resume in the new epoch.

Crash recovery checks the exact service/procedure labels and image before removal;
it rejects foreign containers and never automatically replays started work. Stop,
transport faults, an unconfirmed freeze or failed export retain uncertain-effect
holds requiring the IDE's offline reconciliation. New submissions resolve the
configured image; queued work preserves its original immutable image identity.
There is no independent in-container lease watchdog in this Development provider;
EOF cleanup after service loss is not a substitute for confirmed owned recovery.

The Development container is network-isolated with no host mounts, non-root image
user, dropped capabilities, no privilege escalation, 256 PIDs, 1 GiB memory/swap,
one CPU and private tmpfs. Its filesystem is writable and its original example
driver is a fixture. No DSS endpoint or operational effect authorization is added.

The qualified platform is Windows x64 / CPython 3.13.15 with Linux amd64 Docker.
Eleven real native scenarios cover console/results, descendant freezing and queue
reuse, controller/monitor fencing, native prompts, retained captures and bindings,
capture tampering, killed-service recovery, actual Qt clients, failed freeze,
lease expiry, foreign-container preservation and rejection of completion with
a detached live descendant. Seven installed-wheel checks
execute the original runtime with no source-tree imports, host SPELL package or Qt.
The IDE also passes its 96-test core suite and eight fresh-core Execution checks.

Plugin v0.4 remains open for original registry/factory/manager/interfaces,
`SPELLDriver.proto`, binary/Kafka DSS transport, approved Execution and operating
mode/effect receipts. v0.5 conformance and v0.6 distribution/upgrade/actual-host
gates remain open. No release tag is promoted by this prerequisite milestone.
