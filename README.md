# OpenBEXI SPELL plugin

Optional native SPELL integration for OpenBEXI IDE, IntelliJ IDEA and PyCharm, with a DSS bridge and shared execution services. The root Python package is the separate bounded simulator SDK.

## Current status

**Joint release on hold.** The tested candidate pairs IDE **1.2.2** (`fadac70d`) with SPELL **0.8.0** (`47e0cb37`) and simulator SDK **0.1.0**. Windows uses online installation. Published IDE 1.2.1 passed ordinary Python Run/Debug and stopped at native reservation. The candidate passed installed Windows native execution and browser handoff. Sustained memory, driver deadlines and inherited compatibility still block stable publication. [Qualification results](docs/v0.8/evidence/qualification-20261122/README.md)

Both five-minute sanitizer workloads exceeded the approved 64 MiB growth limit on the review rerun. Controller handoff grew by **296.55 MiB** and the installed IDE by **300.16 MiB**, with zero swap. The one-hour checks are gated on both five-minute passes. [Qualification status](docs/v0.8/CURRENT_STATUS.md) · [Roadmap](ROADMAP.md)

## Use and develop

[Installation and recovery](docs/V07_INSTALLATION.md) · [native host](docs/HOST_RUNTIME.md) · [JetBrains setup](docs/JETBRAINS_HOST.md) · [v0.8 implementation](docs/v0.8/README.md)

The existing local desktop at `http://127.0.0.1:6088` uses the v0.7 native baseline. Follow the setup guide for the matching release; desktop health does not establish v0.8 qualification. [Development dependencies and retained tooling](docs/DEPENDENCIES.md) describe fresh-checkout verification.

## Architecture reference

[Supplied ZIP, provenance and scope](docs/v0.8/reference/README.md). Both images below are unchanged extracts of the user-supplied architecture release package. They describe design intent; [current status](docs/v0.8/CURRENT_STATUS.md) defines implemented and qualified scope.

**Historical comparison (non-normative)**

![Historical SPELL and OpenBEXI v0.8 architecture comparison](docs/v0.8/diagrams/release-package/previous_comparison.png)

**Proposed v0.8 server architecture**

![Proposed OpenBEXI SPELL v0.8 server architecture](docs/v0.8/diagrams/release-package/v08_server.png)

[Documentation index](docs/README.md) links to setup, detailed evidence and historical records.
