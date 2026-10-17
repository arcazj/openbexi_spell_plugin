# SPELL host extension 0.3.1.dev1

This development candidate includes the console input correction. Its distinct
version lets a local wheel installation upgrade an existing 0.3.0 host. It does
not accept the full plugin v0.5/v0.6 release gates. Native child execution also
requires the corresponding corrected runtime image; select its exact identity
with `OPENBEXI_SPELL_IMAGE` as recorded in the qualification report.

This optional package connects a host's CPython interpreter to the original
SPELL native runtime in an owned Docker container. It does not install a
`spell` alias into the host interpreter. Procedures import the original library
inside the runtime container.

The package supplies OpenBEXI backend API 1, a DAP endpoint shared with the
JetBrains extension, and a headless runner. The image is resolved to its immutable
ID before each launch. No native IPC port is published.

Each launch copies a bounded snapshot of the selected project into its own
container. Git metadata, environments, build/cache directories, `.session`,
`.qualification`, `.openbexi` and `.env` files are excluded. Symlinks are rejected.
The snapshot limit is 256 MiB total and 32 MiB per file. Select a smaller project
folder if those limits are exceeded. Docker Desktop file sharing is not needed.

New or changed output files are saved under `.openbexi/runs/RUN_ID/artifacts`;
source edits and deletions made by a procedure are recorded there and never
overwrite the host's working files. A manifest records input and output hashes.

Run with `openbexi-spell-host --project FOLDER --program FILE -- '{"value":21}'`.
The optional argument is one JSON object, made available through native `ARGS`.
Set `OPENBEXI_SPELL_IMAGE` to the locally qualified runtime image while developing.
The default is `openbexi-spell-host:0.3.0`.

The companion OpenBEXI learning desktop explicitly configures
`OPENBEXI_SPELL_BACKEND=packaged-desktop`. In that Linux container, the host uses
the separately installed `/opt/spell-native` runtime and the same private
snapshot/output rules. It does not require a Docker daemon socket. An exclusive
lock permits one native procedure tree at a time; each run owns a fresh synthetic
DSS and original-schema driver. Its run manifest identifies the packaged runtime
manifest by SHA-256. The default Docker backend remains available to Windows and
JetBrains hosts.

The teaching argument `{"LAB_MODE":"Monitoring"}` asks the real local driver
dispatcher to reject effects while allowing telemetry reads. It is separate from
an authenticated shared Monitoring session. Immutable Execution still requires
the release service and its approval workflow. The packaged desktop runs trusted
teaching procedures under its own user account; it is not an untrusted-code
sandbox between desktop users.

The current development host starts visible, automatic `StartProc` children
through the original native protocol and routes each console answer to the
procedure that requested it. Nested children and successive parent/child prompts
are supported. One prompt is exposed at a time; `openbexi/inputRequest` and
`spell/prompt` include `promptId` and `procedureId`. A client can return `promptId`
with `openbexi/input` or `spell/promptAnswer` to reject stale answers. Older clients
can answer the single exposed prompt without a token.

Child debugger threads, manual child execution controls, browser presentation,
and children continuing after the root procedure exits remain open work.
The native child and prompt checks do not qualify those behaviors.

This is a Development runtime with the original example driver. Operational DSS
drivers, Execution and Monitoring, full conformance and broader platform
distribution are separate roadmap phases. The matching JetBrains ZIP provides
native Run/Debug through the same host runtime.
