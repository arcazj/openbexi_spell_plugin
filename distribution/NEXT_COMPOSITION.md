# Next integrated runtime composition

This work starts at checkpoint `fabeaf882966614314ebd799d54eea2b83f020ba` in
the isolated `v06-integrated-next` worktree. The earlier 422 qualified clauses,
341 open clauses, native rebuild pair and images retain their recorded source
and image identities. They are not results for this new runtime.

The new composition includes the independently qualified Event, scheduler,
resource, LIMIT, database-import, user-database, Notify and ValueType/Units tranches. Event
adds behavior checks only. The other tranches retain their checked correction
recipes and original failure evidence. The central CPython port recipes remain
unchanged.

`distribution/evidence/next-qualified-sources.json` records the exact donor
commits, report hashes and expected corrected source bytes. The composition
tests use this retained source baseline, so later refreshes of canonical
conformance reports cannot silently replace their expected results.

## Source and package boundaries

`source_port/integrated_patches.py` validates the original SPELL archive and
every native/Python preimage before modifying a build tree. Python corrections
run in a scratch tree; the manifest records each stage's input and output
hashes, including OBS → LIMIT, CMD → ValueType and database-import → user-database
chains. All recipe identities
also enter the native continuation identity.

Driver corrections have a separate repository-source profile. LIMIT's proxy
`tm.py` and ValueType's proxy `tc.py` are composed in a fresh driver source
snapshot before `pip wheel`. No installed file is patched. The driver wheel
contains its original and corrected source evidence, all recipe bytes and a
manifest covering every packaged Python module, including `limit_support.py`.
These files are covered by the wheel's complete RECORD.

The independent driver audit checks RECORD hashes and lengths, the complete
Python member set, each source chain, and agreement with the native wheel's
recipe identities. The conformance auditor additionally binds driver repository
preimages and unchanged support modules to the runner's source inputs. Legacy
overlay evidence retains its explicit historical profile.

## Repeating qualification

Use the retained toolchain image `openbexi-spell-toolchain:v06-a1f60eb52594`,
requiring exact identity
`sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2`.
The commands below create unique evidence directories and do not replace prior
builds:

```powershell
python distribution/qualify_driver_package.py --toolchain-image openbexi-spell-toolchain:v06-a1f60eb52594 --toolchain-id sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2
python distribution/rebuild.py --toolchain-image openbexi-spell-toolchain:v06-a1f60eb52594 --toolchain-id sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2
python distribution/build_images.py --native-wheel <fresh-pair-wheel> --toolchain-image openbexi-spell-toolchain:v06-a1f60eb52594 --toolchain-id sha256:b02799b7bf8715a8b7933999189c751a7407455beab6cd6d387b08d57b50a4f2
```

The driver preflight builds and installs two wheels independently with
`--no-cache --network=none`, verifies each installed package, and compares the
complete wheel bytes. It does not run the native language suites. The full
native pair retains the unchanged native recorder gate, installed runtime tests
and byte comparison. Host/DSS construction requires the explicitly selected
fresh wheel and verifies both installed packages plus the compiled bridge.

Coverage can advance only after the actual native suites pass on the exact new
runtime image. Full v0.5 and v0.6 acceptance flags remain false while clauses are
open. Source composition and package provenance alone do not qualify language
behavior.
