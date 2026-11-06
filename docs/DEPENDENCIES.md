# Dependencies and verification

The cleanup retains all dependency declarations, lock files, original source/manual inputs, patch recipes, compatibility fixtures, licenses, release-gate tooling and current deadline/memory diagnostics. Build caches and historical worktree copies are replaceable; source-bound results and failed evidence are archived with hashes.

| Dependency | Retained purpose / authoritative declaration |
| --- | --- |
| CPython 3.13 | Package constraint `>=3.13,<3.14`; reference Linux checks pin 3.13.17; existing local baseline uses 3.13.15 |
| setuptools 80.9.0 | Build backend in each `pyproject.toml` |
| PySide6-Essentials 6.10.3, debugpy 1.8.22, Pygments 2.21.0 | IDE desktop extras; do not remove the active desktop environment |
| pytest 8.4.2 | Original test runner |
| ruff 0.14.1, mypy 1.18.2, grpcio 1.84.0, protobuf 7.36.2 | SPELL `server/requirements-test.lock` |
| Docker Linux engine, native compiler and headers | Native fixtures, isolated execution and diagnostic reproduction; recipes pin their inputs |
| Original SPELL source and manuals | SPELL `docs/reference`; required for native builds, provenance and all-763 compatibility |

Use the repository's `pyproject.toml`, component manifests, lock files and Dockerfiles for the complete dependency closure; this table is an entry point, not a replacement lock file. Preserve optional Kafka, distribution and JetBrains dependencies when exercising those profiles. Credentials, active application data and unrelated host resources are outside cleanup deletion scope.

For foundation verification, install `server/requirements-test.lock`, the immutable companion IDE recorded in `docs/v0.8/IDE_PAIR.json`, PySide6-Essentials 6.10.3 and the native system prerequisites in the [fresh-checkout workflow](../.github/workflows/repository-verification.yml). Run `python scripts/qualify_v08_server.py`; its original complete-suite limit remains 600 seconds. The independent root SDK uses `.[test]` and `python -m pytest tests -q`.

Keep `profile_context_deadlines.py`, `summarize_context_deadlines.py`, `profile_context_bridge_memory.py`, `qualify_v08_memory_comparison.py`, native build profiles, all original acceptance runners and their fixtures. The 300-second memory gate must pass before both original one-hour scenarios. Do not prune these tools because recent runs failed.

[Maintenance and recovery](REPOSITORY_MAINTENANCE.md) records the external archive and exact cleanup decisions.
