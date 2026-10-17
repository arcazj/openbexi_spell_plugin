# OpenBEXI SPELL v0.5

All **763 original language requirements are qualified; none remain open**.
The final 190 cover limits, telemetry, commands, data/database, procedure,
prompt/UI and special-service contracts. Every requirement retains independent
positive, boundary, failure and recovery evidence.

Validation passes all 61 native suites (2,157 raw checks), repeated prompt and
child lifecycle controls, and 1,502 repository tests plus 64 subtests.
Two independent offline native builds and driver builds match byte for byte;
fresh installation/removal and exact installed provenance checks pass.

The final corrections preserve empty prompt defaults and empty Event messages,
carry timeout metadata through the host bridge, and allow command sequences
through the shared database lookup while retaining bounded memory queries.
Asynchronous executor errors now reach their notification handler without
consuming pending request replies; forced correlation collisions pass in both
independent builds and in the installed runtime.

Scope: Linux x86_64 / Debian 13 / CPython 3.13.15 with the diagnostic ASan/UBSan
runtime and GENERIC simulator. The wheels retain their qualified diagnostic
version labels (source 0.3.0, driver 0.4.0). Production distribution, versioned
upgrades and final installed host workflows remain v0.6 work; operational
qualification remains v0.7 work. Stable v1.0 is not yet accepted.

See [the exact acceptance manifest](V05_CONFORMANCE_QUALIFICATION.json) for
artifact identities and limitations. The portable evidence archive retains
original report bytes, source inputs and native captures under content hashes;
its MANIFEST.json maps those members to their original paths and commits.
It also lists any unavailable source snapshots from older failed or partial
diagnostics; those runs do not substitute for current acceptance evidence.

Load the diagnostic runtime with
`docker load --input openbexi-spell-v0.5-dss-runtime.tar.gz`. From a checkout with
the repository's test dependencies installed, reproduce the native sequence:

```powershell
python distribution/run_language_regressions.py --image sha256:1e8dd6cafc8968a4fe36dc16a7bac804ba345dbd3d15da9a220fd3b909e4751b
python conformance/check.py
```

The evidence archive is distributed as numbered `.partNNN` files. Download all
parts, `RELEASE_MANIFEST.json` and `reassemble_v05_evidence.py` into one folder,
then run `python reassemble_v05_evidence.py`. The script verifies each part and
the exact reconstructed archive against SHA-256 checksums.
