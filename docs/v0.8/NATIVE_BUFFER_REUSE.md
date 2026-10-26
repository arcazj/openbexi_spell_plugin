# Native IPC buffer reuse — dev66 candidate

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
