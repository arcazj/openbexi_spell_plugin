# Bounded native message-copy storage

The frequency-ranked native diagnostic at `3ea8f2463721a97085fb82da1da04cc2ef1183c5`
(run `40409512613`, archive `12693321621`, SHA256
`a943a05c30a99b9543a2535054bcf0a1d63cbd4b0606eb5838ab5a9694043ebc`)
identifies repeated property-map copies in Context notification/forwarding and
Executor `sendGUIMessage` / `specificNotifyLine` paths. The original 45-second
soak still fails memory growth. Sampled stacks are attribution evidence, not
proof of a live-object leak.

This candidate recycles property-map storage only after its message is destroyed.
Copy constructors and copy assignment retain independent owned maps and exact
field values. The sorted merge removes absent fields and reuses matching nodes
and value capacity. Constructor metadata, message layout, wire encoding, input
validation, callback ownership, queueing, ACK ordering and authority are unchanged.
The pool holds at most 32 maps, each with at most 64 fields and 64 KiB of combined
key/value string capacity. Cached values are cleared. Contention, pool exhaustion,
oversized fields and shutdown use ordinary allocation/destruction; the pool does
not delay dispatch or discard messages. No allocator or sanitizer policy changes.

## Executed local component checks

Python 3.13.5 / C++ ASan+UBSan: 61 targeted tests passed, including five new compiled
storage tests, allocator diagnostics, resource-oracle rejection, spawn and native
transport checks. These are not the full hosted acceptance suite.

Over 10,000 iterations of three real message copies/assignments, the frozen
implementation allocated 33,870,000 bytes / 570,000 allocations; the candidate
allocated 930,000 bytes / 30,000 allocations. Both message classes are 176 bytes.
Tests cover binary/Unicode/empty fields, pointer construction, moves, self-assignment,
changing/absent fields, eight concurrent threads, pool exhaustion and oversized
messages. The frozen library archive and current source tree were digest verified.

## Required hosted verdict

Both non-profiled native handoff and installed-IDE recovery must still preserve
all eight original processes, advance each progress interval, complete the fixed
45-second soak, and pass 1,792 MiB peak / 64 MiB growth inside 2 GiB with no swap or
memory-pressure events. Component allocation savings cannot substitute for this
verdict. All full-release gates remain unqualified; no stable package is published.
