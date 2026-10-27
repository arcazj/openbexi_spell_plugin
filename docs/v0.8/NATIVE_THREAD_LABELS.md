# Native thread monitor allocation correction

The source-verified `0a14360` diagnostic records repeated allocations in
`SPELLexecutorImpl::dispatch`. The exact monitor used at that call site takes a
`const std::string&` and copies it into `m_where`, although both uses of that
member are disabled debug statements. Each literal call therefore allocates a
temporary string and an owned copy.

The private native composition adds a `const char*` overload which performs
the same `beginSafeAllowThreads()` call, retains the same state token and uses
the unchanged destructor to restore it. It does not retain the label. Class
layout, the dynamic-string constructor, GIL ordering, error handling, authority,
deadlines, sanitizer settings and mandatory memory limits are unchanged. The
complete original class is SHA-256 guarded before writing.

The compiled original/candidate class harness checks nested release/restore,
exception unwinding, dynamic labels, two concurrent threads and equal class
size under ASan/UBSan. For 10,000 literal monitor scopes, allocations decrease
from 20,000 / 610,000 bytes to zero. The Python collaborator is a test fixture;
the hosted native rebuild must independently exercise the actual interpreter.
This component result alone does not establish whole-runtime memory stability.

A bounded metadata-only temporary-file inventory now accompanies host resource
samples. It reports file count, logical size and allocated blocks by category
(native console, native diagnostic logs, AsRun, other), without names or file
contents. It excludes symlinks, deduplicates hardlinks and reports incomplete
traversals. Existing memory acceptance uses the original kernel counters without
subtracting these values. No log is deleted, truncated or redirected. These
measurements address the previously unattributed one-hour file/shmem growth.

The preceding core run `40456278980` is complete: 12/14 jobs passed; handoff
and installed-IDE recovery still failed memory growth. All five ancillary
workflows passed. Fresh hosted recovery, diagnostics and endurance are required
for this new composition. Full v0.8 remains unqualified and release remains HOLD.
