# Development Python supply-chain evidence — scope limited

The v0.8 candidate has a dedicated `v08-supply-chain.yml` GitHub Actions job
that builds and **installs the actual development service wheel** in a new
Python 3.13 virtual environment, separate from an independent audit-tool
environment. Tool versions are pinned to `cyclonedx-bom==7.5.0` and
`pip-audit==2.10.1`. The job generates a CycloneDX SBOM for the installed
environment and queries the PyPI vulnerability advisory database using
`pip-audit --path`. Failure of dependency resolution, SBOM validation,
inventory, lookup or a reported known vulnerability must leave the job failed.

An independent verification script `qualify_v08_supply_chain.py` checks
the service wheel's Apache license, package members, immutable SHA-256,
the `openbexi-spell-server` identity and exact `0.8.0.dev43` version
in the SBOM, the real pip-audit dependency inventory and no bundled private
PEM keys. Focused tests include fake vulnerable records, stale component
versions, missing inventory/license and embedded private keys.

Artifacts retain **only** SBOM, vulnerability results and redacted hashes,
not certificate material. Installation and vulnerability scan are executed
in a disposable CI environment and cannot silently upgrade vulnerable
dependencies or change the candidate.

This is a **bounded development Python dependency scan**, not a full v0.8
independent security approval. Python vulnerabilities in the native CPython
runtime, OS packages, OpenSSL, zlib, C/C++ components, third-party executable
drivers, user-written procedures, browser/WSS, installed IDE Qt, Java/JNI and
the final production images are **not comprehensively scanned here**.
It does not replace complete license review, independent source review,
penetration testing, production PKI/rotation or the full `security`
release-gate acceptance.

The authoritative `RELEASE_GATES.json` security gate and all other full
gates remain unqualified until the full implementation and executed evidence
pass. Publication and migration remain blocked.
