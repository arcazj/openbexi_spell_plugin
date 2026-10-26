# Native IPC buffer reuse — dev66/dev67

The dev65 recovery evidence shows stable live objects but growing allocator
retention in the active bridge and both Executors. Dev66 removes repeated
allocation in these existing transport paths without changing sanitizer
settings, message frequency, deadlines, process checks or acceptance budgets.

- The private bridge keeps one JSON encoder behind its existing output mutex.
  It reuses strings and serialization buffers, removes fields missing from each
  new message, and lets the same JSON library handle ordering, escaping and
  invalid UTF-8 replacement. Notification publication still precedes ACK.
- Native input decodes its existing immutable packet string by reference. The
  original by-value API remains available and retains its copy semantics.
- Native output reserves the compression byte, prepends it in place and moves
  its owned payload into the unchanged partial-write loop. String setters move
  already-owned arguments into the message map. Class layouts are unchanged.

Sanitized component tests compare complete frames against the frozen encoder,
including every byte value, Unicode, missing/stale fields, empty messages,
reply/event transitions, maximum sequences and large-buffer reset. The actual
send/writeData methods are compiled against a capturing socket and zlib to
check compressed/uncompressed frames, partial writes and failures. This is
component evidence, not a substitute for the hosted native workload.

Over 10,000 representative frames, the frozen encoder allocates 36,170,000 bytes
in 830,000 allocations; the warmed reusable encoder allocates zero. Over 10,000
output messages, allocations fall from 21,660,000 bytes / 220,000 allocations to
3,530,000 bytes / 10,000 allocations. These are scoped measurements and do not
establish full-process memory stability. The four changed C++ translation units
compile with ASan/UBSan and the exact composed native headers.

All 170 focused component tests pass locally (Python 3.12.14); hosted Python
3.13 and the original native family remain mandatory.

The complete hosted native family and installed IDE recovery must still pass
both fixed resource checks: 1,792 MiB peak and 64 MiB window growth within the
2 GiB resident, zero-swap profile. All eleven full-release gates remain closed
pending their complete source-bound evidence.

## Dev66 hosted result and dev67 follow-up

Dev66 brings both memory peaks under the fixed ceiling, but neither profile
passes the growth limit. The handoff/IDE peak values are 1,747.4/1,754.2 MiB and
the window growth values are 224.6/234.4 MiB. All 19 artifacts and recorded source
hashes are verified in the [receipt](evidence/native-codec/dev66-hosted/qualification-summary.json).
A separate service test found the deployment image markers still at dev65;
dev67 aligns all package, image and manifest version markers.

Dev67 reuses each input thread's owned message storage. Every packet starts with
fresh constructor metadata; fields absent from that packet are removed, and
callbacks keep the same independent copies as before. Parsing validates bounds
before committing metadata, sorts non-owning field views with last-duplicate
semantics, and reuses property values. Malformed input still clears properties
without committing metadata. Scratch fields are cleared after every call,
reentrant calls use independent scratch, and oversized packet/view storage is
discarded. Original by-value decoding and message class layout are preserved.
The complete composed input and message translation units compile with ASan/UBSan.

The measured 10,000 repeated input decodes fall from 27,330,000 allocated bytes /
440,000 allocations to zero after warming the cache. This is component evidence;
it cannot establish the full-family resource verdict. Tests compare fresh and
reused messages across binary/Unicode fields, duplicates, empty packets, stale
metadata, copy isolation, malformed prefixes and oversized fields/inventories.

The dev66 prompt denial retained `scope_valid=false`. Original scheduler
`checkTime()` raises a system-scope warning when a prompt remains unanswered,
including at a timed default's deadline. That is a source-based hypothesis for
the observed denial, not a proven attribution. Dev67 records a fixed scope enum
and whether the message exactly matches that known warning; it never records
arbitrary event text and does not relax scope authorization.

All 172 focused regression tests pass locally. Full acceptance remains pending.
All eleven publication gates stay unqualified.

## Dev67 hosted verdict

Candidate `93dad418c1992c2863374cad53dfcbb3ba93858f` completed run `40397729336`.
All 1,290 service tests, 95 overlapping fault tests and 241 portable tests pass.
Twelve of fourteen core jobs and all five ancillary workflows pass, including
24 fresh startup cycles, 16 terminal cases and the 21-generation prompt cohort.
All nineteen artifact archives and recorded source hashes are verified.

Handoff peaks at 1,662.8 MiB with 224.9 MiB window growth; installed IDE peaks at
1,671.0 MiB with 238.8 MiB growth. Both complete the original 45-second soak with
eight original processes. Peaks pass 1,792 MiB; growth still fails 64 MiB.
The input change reduces peak memory, but this run does not show improved soak
growth. Further work must target demonstrated live-stream allocations; the
component benchmark does not close that blocker. No limits, sanitizer settings,
workload or deadlines changed. The dev66 scope denial did not recur and remains
unresolved. See the [retained receipt](evidence/native-codec/dev67-hosted/qualification-summary.json).
