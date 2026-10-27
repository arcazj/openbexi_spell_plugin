# Bounded runtime epoch reads

The byte-ranked native diagnostic at
`325feb57fff5cb48665f177c6ed6c3dd78b5658c` reproduces the unmodified 45-second
handoff workload of reference executable
`892914f10f12bd9a3043a69e07f363a143445ec3`. Artifact 12772857813 verifies all
139 native sources, 23 raw audit files and every observed ranking. The Context
stack resolves repeated 8,192-byte `basic_filebuf` allocations to
`v08_admit_gui` → `v08_native_request`: opening an `ifstream` for a 36-byte
runtime epoch. Its six sampled allocations (49,152 sampled bytes) were freed.
These sampled counts are not extrapolated to an exact lifetime total.

The correction reads at most 38 bytes through an owned `O_CLOEXEC` descriptor.
Every admission opens the current path again. Atomic epoch rotation is observed;
there is no identity cache, authority refresh, rebind or retry of an admission.
The accepted file contract remains 36 bytes, optionally one LF, then EOF.
Downstream epoch validation is unchanged. Partial reads and EINTR continue on
the same descriptor; malformed/oversized files or read failure deny admission.
RAII closes the descriptor on normal completion, error and cancellation. The
JSON value owns its bytes before the stack buffer disappears.

An exact frozen copy of the reference header is bound by SHA-256
`c6ddab63d76616b7e8a0b93513d62434b1a71bc1c158e083bd0c533784016bdd`.
Both implementations execute all 10,000 component reads under ASan/UBSan,
without a discarded warm-up:

| Measurement | Frozen reader | Bounded reader |
|---|---:|---:|
| Completed reads | 10,000 | 10,000 |
| 8 KiB file-buffer allocations | 10,000 | 0 |
| Retained allocator heap growth | 110,428,160 bytes | 786,432 bytes |
| Live bytes before / after | 73,994 / 73,994 | 73,994 / 73,994 |

Separate compiled checks cover exact old/new spellings, missing and oversized
files, interrupted/partial reads, explicit read failure, owned-descriptor closure,
8,000 concurrent reads during 100 atomic replacements and physical cancellation.
The fault wrapper covers both `read` and the compiler's fortified `__read_chk`;
no production sanitizer or fortification option is disabled.

The local execution environment refuses `AF_UNIX` socket creation with `EPERM`.
That attempted full transport component remains failed and retained. The complete
10,000-request JSON/Unix-peer-pin/admission test, including an epoch change midway
through the stream, must execute on the hosted disposable runner; it is not skipped
there. File-reader components alone do not establish native or installed-IDE
acceptance. The original 45-second resource checks, real native disk-full checks,
startup/terminal regressions and longer sanitizer diagnostics require fresh runs
on the new candidate. Original limits, deadlines, concurrency and audit records
remain unchanged. All eleven full-release groups remain false.
