# SPELL source authority and compatibility review

The prior deep review read all seven supplied manuals (390 pages) and inventoried
the 2.6.10 source archive (716 members, 121 Python files). Syntax parsing was not
treated as runtime compatibility. Original inputs remain byte-for-byte in
`reference/`; `MIGRATION.json` records every copied SHA-256.

Archive SHA-256:
`2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed`.
The Driver Development Manual is 45 pages; its lifecycle is implemented by
`spell.lib.registry`, `factory`, `drivermgr` and generic service adapters. Reuse
those contracts, setup-forward/cleanup-reverse ordering and original service
interfaces when the source-derived port begins.

The original `protos/SPELLDriver.proto` defines TM/TC/EV/PCS/MEM/RSC/TASK/RNG/
USER/TIME services. Generated `spell.stubs.SPELLDriver_pb2` is absent from the
archive; it blocks `spell.lang.functions` and helpers. Native
`libSPELL_DTA_v3` is absent; some legacy imports print a fatal diagnostic and
substitute dictionaries. A zero exit status from those imports is not a pass.

`SPELL_UTIL` injects functions/constants/modifiers/user/time/file/math into
builtins. New explicit-import workers must consciously replace that bootstrap,
while reusing the language implementation. Native EXC/UTIL/WS use old Python
initialization/frame/data interfaces and are not CPython 3.13 ABI-compatible
merely because their Python files parse. Native Step/Goto/warm-start are required
independent porting/conformance gates.

The seven current PDFs are Development Environment 2.4.4 (57), Driver Development
2.4.4 (45), GUI User 2.4.4 (54), Language Reference 2.4.4 (118), Server 2.4.4 (11),
SPELL_DEV_Manual (37) and SPELL_Language_Manual (68). Older manuals and the newer
source have conflicts in defaults, active TM selection, limits and actions;
record and qualify them rather than silently merging semantics.

The upstream archive carries GPLv3 and mixed GPL/LGPL source headers. Original
notices remain inside it and an unchanged GPL copy is in `UPSTREAM-GPL-3.0.txt`.
It is a preserved source input, excluded from the current Apache-licensed bounded
wheel. A later source-derived wheel must include its applicable original notices,
license/source/patch materials and an honest compatibility matrix.

The current `spell.lang` package is the retained bounded SDK alias, not the full
upstream module tree. The v0.1 DSS adapter is newly explicit and limited; it does
not claim the future port or original driver integration is complete. The full
earlier review and raw source/manual analysis are retained in the migration
archive for later implementation.
