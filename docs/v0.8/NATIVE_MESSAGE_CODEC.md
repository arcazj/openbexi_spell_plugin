# Native IPC allocation correction

Dev58's two extended recovery cohorts OOM-kill the original Context at the
fixed 2 GiB, zero-swap limit. The resource acceptance remains failed. Live
allocations and resident memory are distinct; rising allocator retention alone
does not establish a live-object leak.

Dev59 removes demonstrated allocation overhead in the native IPC codec. The
original decoder creates a map of byte vectors and copies its fields into a
second property map. The replacement reads bounded fields directly into their
final storage and moves values into place. The encoder reserves the final wire
length once and appends fields without constructing temporary encoded strings.
The original class layout, method signatures, valid wire ordering, last-duplicate
behavior, empty/binary/Unicode values and missing-metadata behavior are retained.
Malformed length headers and payloads fail before metadata changes. Serialization
rejects keys whose length cannot be represented by the original 16-bit wire field.

The checked private builder applies the patch only when the exact frozen
`SPELLipcMessage.C` SHA-256 matches. Changed or repeated applications fail.
The published v0.7 wheel and source recipes remain immutable. This patch is
rebuilt into the private Context and Executor runtime; the frozen host bridge
is unchanged.

The ASan/UBSan compiled regression uses the frozen message class, implementation
and tokenization helper, with unrelated logging/Python dependencies replaced by
fixtures. It compares 256 valid message variations and additional duplicate and
partial-metadata cases, checks truncated/oversized data and counts real allocator
calls during 10,000 representative messages:

| Operation | Before allocated bytes | After allocated bytes | Before allocations | After allocations |
| --- | ---: | ---: | ---: | ---: |
| Decode | 27,330,000 | 12,160,000 | 440,000 | 100,000 |
| Encode | 14,600,000 | 3,520,000 | 200,000 | 10,000 |

A separate local link against the verified published native runtime confirms
the reduction with its real utility dependencies (decode 27,670,000 → 12,400,000
bytes; encode 15,210,000 → 3,760,000 bytes). Those component measurements are not
a pass of full native recovery. Hosted qualification must still complete the
same 45-second soak, original-process liveness, 2 GiB/no-swap, peak/growth and
zero-pressure requirements. No sanitizer options or authority deadlines change.
