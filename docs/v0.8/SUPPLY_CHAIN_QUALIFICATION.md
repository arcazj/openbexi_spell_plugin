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

## Confirmed exact-code development scan — PASS

Candidate **`b333607e0b73f6030bd430b52e883ee7cd8a7836`** passed the hosted
[Python supply-chain job](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/40206043448).
The executed Python 3.13.16 environment contained **two installed components**:
`openbexi-spell-server 0.8.0.dev43` and `pip 26.2.1`. The validated
CycloneDX 1.6 SBOM included both. A pinned `pip-audit 2.10.1` lookup
returned **zero known advisories for these two Python packages**; this
does not mean the complete server image or native runtime is vulnerability-free.

A direct download of the retained Action artifact was checked for ZIP
integrity and JSON source identity. The archive SHA-256 is
`b2e10a4475e6b46e593bcf87ba0c788e47ba92641ac5911822826f4f2344bdef`.
The tested runtime wheel SHA-256 is
`88447345edccda5318288345fc2b8dc69a146525b94811ca94b77f9a1f5847ce`.
The three original artifacts are `runtime-sbom.json`,
`python-vulnerabilities.json` and `summary.json`; the summary explicitly
records `independent_security_qualified:false` and
`full_v08_qualified:false`.

This passes the narrowly defined installed-Python component scan only.
It does **not** authorize changing the full `security` gate or releasing
v0.8.
