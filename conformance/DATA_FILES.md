# DATA and FILES qualification

This milestone provides four-dimensional evidence for 29 of 94 DATA rows and
40 of 45 FILES rows. The reports are `evidence/data.json` (24 grouped checks)
and `evidence/files.json` (36 grouped checks). Shared checks cover contracts
which jointly describe one behavior. The other 65 DATA and five FILES rows
remain open; these results do not complete v0.5 or qualify a distribution.
`evidence/data-race.json` adds four checks for the atomic test-and-set syntax
and section, using two competing executors in the same native context.

The exact development runtime image is
`sha256:16f972f302f111b8f088712941fea9eff1f4987b96d504c556eb2a9a737665c4`,
tagged `openbexi-spell-host:v05-data-files-native`.

## Filesystem behavior

The original native executor, original wrappers, original File adapter and real
owned filesystem paths perform all operations. Oracles independently inspect
bytes with pathlib, directory entries and POSIX permissions. They cover default
READ, WRITE truncation, READ_WRITE preservation, APPEND, empty/Unicode content,
repeated reads, descriptor closure, missing/inaccessible paths, relative
basenames, unsupported arguments, path queries, path append, empty-directory
deletion and rejection of nonempty-directory deletion. Rejected list writes
leave the file empty. A separate DAP controller observes real REPEAT/SKIP
choices, repairs an absent owned file, chooses REPEAT, and checks its contents.

Exact upstream hashes guard these small original-source corrections:

- File supports the documented `isdir`/`isfile` spellings while retaining its
  existing `isDir`/`isFile` methods.
- Relative basenames use the current directory for parent permission checks.
- Text files use UTF-8 explicitly, avoiding the embedded runtime's ASCII default.
- WriteFile validates every list member before writing. It accepts the
  documented list of strings and rejects mixed lists without partial output.
- DeleteFile delegates directory deletion to File.delete, whose `os.rmdir`
  operation permits empty directories and rejects nonempty directories.

The unchanged COMMON image fails 12 of the 36 final grouped checks, including
aggregate section checks. Retained negative evidence:
`.qualification/v0.5/files-baseline/46d7bc4a303f447cbdde7ee98d8c8cff/`.
Passing evidence:
`.qualification/v0.5/files/95769c4a49e64291996bdc0bba974625/`.

## Shared blackboard behavior

The original language helpers, native CIF, context and native shared data tables
perform real IPC operations. Tests include primitive numbers/strings/Booleans,
nested lists/dictionaries, empty values, Unicode, signed 64-bit integer bounds,
single/batch syntax, partial batch compare-and-set results, mismatched expected
values, unavailable keys/scopes, scope isolation, key/scope enumeration, clearing
single/multiple/all values, scoped removal and preservation of GLOBAL.

The Python corrections make batch detection depend on the first list item,
validate list lengths before indexing, support the p.97 two-positional-argument
example, and honor `ClearSharedDataScopes(Scope=...)`. Previously that last
spelling silently removed every nonglobal scope.

Failure testing also exposed a native context fault. Clearing all values in a
missing scope threw outside the request handler's error conversion. The context
stopped responding and the host could not recover through ordinary IPC. The
checked native patch catches `SPELLcoreException` in precisely this branch and
returns the existing error reply. Tests now receive DriverException, then
successfully read/write existing data and create/remove scopes in the same
native session. No Python existence precheck substitutes for this correction.

Retained failure evidence:
`.qualification/v0.5/data/fdda2c521c574bb2b996d75e6942d035/`.
Passing evidence:
`.qualification/v0.5/data/c55352e3e5d1405fb17bbef189d45ace/`.

The separate race controller opens two original executor processes through the
original context's REQ_OPEN_EXEC protocol. Both reach a start barrier before
release. Eight scalar rounds and an empty-list boundary each produce exactly
one successful compare-and-set; a third native procedure independently reads
the winner's value from the same context. Both contenders fail a wrong expected
value, then a valid competition recovers with exactly one winner. Native IPC
notifications and each procedure's results are retained in
`.qualification/v0.5/data-race/4dc3456e4489424988719289a4881758/`.
This establishes competing-process atomicity instead of inferring it from
sequential comparisons.

## Manual and source decisions

- LRM p.92 explicitly lists lowercase `isdir` and `isfile`; aliases expose these
  documented spellings without removing original callers' methods.
- LRM p.91 says a list of strings. Original conversion of arbitrary objects to
  strings is narrowed to that declared contract before any write occurs.
- The manuals do not specify Unicode file encoding. UTF-8 is the explicit
  CPython 3 text-file contract for this port; byte files remain outside this API.
- LRM p.99 prose says `ClearSharedDataScope` singular, while both its examples,
  function reference and original implementation use `ClearSharedDataScopes`.
  No speculative singular alias was added. The alias-candidate row stays open
  pending the inventory-wide source-conflict decision.
- LRM p.99 sketches a Boolean for batch ClearSharedData. Original 2.6.10 returns
  one Boolean per named item. The port preserves that more informative result
  consistently with batch SetSharedData; tests explicitly expect `[True, True]`.
- Attempting to remove GLOBAL is acknowledged as an idempotent no-op by the
  original 2.6.10 context. Tests verify the table and existing values survive;
  they do not require an exception which the original implementation never emits.

## Build provenance and reproduce

`source_port/data_files_patches.py` checks all three original Python preimages.
`source_port/data_files_native_patches.py` checks both the original context source
and the exact central-port result before applying its narrow catch block.
Original notices remain in every patched source.

The Python overlay and manifest live at `/opt/data-files-conformance-patch` in
the image. Original, ported and patched context source, recipe, inherited object
hashes, compile/link commands and resulting binary hash are retained at
`/opt/data-files-native-patch`. The context is relinked against the original
separate context graph, without replacing the executor's distinct native graph.

```powershell
python conformance/data_files_build.py
docker build --network=none -f conformance/data_files.Dockerfile -t openbexi-spell-host:v05-data-files .
docker build --network=none --build-arg NATIVE_BASE=openbexi-spell-native:v06-diagnostic-6a340659e519 -f conformance/data_files_native.Dockerfile -t openbexi-spell-host:v05-data-files-native .
python conformance/run_data_files.py files --image openbexi-spell-host:v05-data-files-native
python conformance/run_data_files.py data --image openbexi-spell-host:v05-data-files-native
python conformance/run_data_race.py --image openbexi-spell-host:v05-data-files-native
```

The inherited compiler/source/object development image is exactly
`sha256:7c3eb7b7b33bb49690a35c51cb0a096c8c30bc770f9994eb54563d4aea4725cb`.
It is used for compiling the changed context graph; its wider diagnostic build
does not establish distribution acceptance. The Python overlay inherits the
previously qualified COMMON image. Accepted host and DSS release images remain
unchanged. The ten existing native host regression cases pass on the combined
development image (94.375 seconds); report and transcripts are in
`.qualification/v0.5/data-files-host-regression/`.

## Remaining scope

FILES still requires GetResource, SetResource and Examples 111-113 through the
actual DSS resource service, including GDB mapping behavior.

DATA still requires native DTA types and prompt/notification semantics, ARGS and
IVARS host editing, PROC metadata and Step/parent transitions, real read-only
SCDB/GDB/manoeuvre databases, user database create/load/save/revert and every
documented format, ranging state behavior, and the remaining whole-section
shared-data contracts. Expected and Scope remain open because their other applicable
families are not covered by the shared-data subset. Native DTA's historical
qualification and the scoped blackboard checks are not substitutes for those
whole-row contracts.
