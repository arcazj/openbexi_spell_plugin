# SPELL host extension 0.3.0

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

This is a Development runtime with the original example driver. Operational DSS
drivers, Execution and Monitoring, full conformance and broader platform
distribution are separate roadmap phases. The matching JetBrains ZIP provides
native Run/Debug through the same host runtime.
