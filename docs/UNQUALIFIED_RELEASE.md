# OpenBEXI SPELL v0.8-rc1

**UNQUALIFIED — qualification incomplete.** Published at the owner's explicit request before mandatory acceptance is complete. No production qualification is claimed.

## Delivered scope

This release supplies the exact Git source archive, Python wheels and source distributions, a full Git recovery bundle, SHA-256 checksums, focused-test results and a release manifest. It does not supply newly built native Docker images or Windows/macOS offline desktop bundles. Historical release packages and test results do not qualify these new artifacts.

## Installation and verification

Use CPython 3.13 in an isolated virtual environment. Download the wheel(s), `SHA256SUMS.txt`, and `release-manifest.json` from this release. Verify checksums with `sha256sum -c SHA256SUMS.txt` after downloading all listed files. Install the appropriate wheel with `python -m pip install /path/to/package.whl`; install documented optional dependencies when using desktop or driver components. See the source README and component READMEs for configuration. The manifest distinguishes installed-package/CLI checks from focused regressions and full qualification.

## Known incomplete acceptance

Sustained native memory budgets, complete 763-requirement compatibility, deployed controller/recovery tests, portable dependency packaging, full license/advisory disposition, production-like Kubernetes and independent implemented-system security review remain incomplete or failing. Original sustained memory tests exceeded the 64 MiB growth limit by about 1 GB; short/component passes do not supersede those failures. Unpromoted CPython buffer and Qt derivative experiments are archived, not promoted into this release. No production migration is authorized.

## Recovery and remaining work

`branch-recovery.bundle` and `branch-heads.json` preserve repository branches before cleanup. Verify the archive and recover any branch using Git bundle tools and its recorded commit. Published tags and original release artifacts remain immutable. `prompt4v0.8-qualification.md` contains the full continuation plan and evidence pointers. Full acceptance results remain unchanged.

## Source selection and pairing

Based on `eddd6758b16c7e6ef44b9cc605896d3143be2e30`, including owned GUI serialization, synchronized startup ACK and graceful DSS shutdown; adds the tracked native legacy-source delivery correction from `bcef4b6729c1fbfc98b47e26698fedccc49959f5`.

Tag `v0.8-rc1` maps to package version `0.8.0rc1` for server, host, shared and DSS bridge packages. The separate bounded SDK at repository root remains version `0.1.0`; it is not the native runtime. Existing v0.7 Docker-image defaults remain historical and do not deliver the v0.8 native source: build the native source through the provided recipes before attempting v0.8 native execution. No new native image is claimed.

Companion: [OpenBEXI IDE v1.2.1](https://github.com/arcazj/openbexi_ide/releases/tag/v1.2.1). Exact paired IDE commit is recorded in `docs/v0.8/IDE_PAIR.json`. Joint installed qualification remains incomplete.
