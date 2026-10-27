# Scoped Executor trace filename ownership

This is a measured runtime correction, not a full v0.8 release receipt.
Base commit: `084e58593d242857bd8e56d5b4ec364ed9d3240d`.
Base tree: `6f0653649b832c508f256982b68d272ff52bc115`.

## Verified baseline and allocation path

The exact-source archive (artifact 12700677777) was SHA-256 checked and its
reconstructed Git tree matches the base. Hosted run 40428613683 has a passing
foundation receipt with 1,451 tests, no failures/errors/skips. This is baseline
coverage, not a substitute for testing the runtime modification below.

Both mandatory original-family recovery artifacts were independently checked,
including all 131 executed source hashes in each receipt:

| Scenario | Peak MiB | Window growth MiB | Verdict |
| --- | ---: | ---: | --- |
| Controller handoff | 1513.2578125 | 127.8828125 | Growth failed |
| Installed IDE | 1502.28125 | 122.02734375 | Growth failed |

Both 45-second soaks retained all eight original processes and progress at
every interval. Peak acceptance passes; growth exceeds the unchanged 64 MiB
limit. No mandatory gate is closed by these results.

Fresh frequency-ranked artifact 12700284964 from run 40428613619 contains
`SPELLpython313::text` -> `filename` -> `SPELLexecutorImpl::dispatch` in both
Executor allocation profiles. This identifies a remaining allocation path,
not proof that it accounts for all memory growth or that no other leak exists.

## Runtime correction

The dispatch method previously constructed a C++ filename string before
rejecting excluded frames, then repeated the conversion for accepted frames.
The correction owns the rendered Python Unicode object for one dispatch call
and applies the same substring filters to a length-aware UTF-8 view. Excluded
frames require no temporary C++ filename string. Accepted frames create one
owned string and reuse it at the second lookup.

The scoped owner survives nested calls and the existing GIL-release interval;
construction and destruction require the GIL. There is no persistent filename
cache. Unicode, embedded-NUL and conversion-error behavior remain unchanged.
An exact dispatch-method preimage rejects drift and duplicate application.
The remaining dispatch body is unchanged except for the second conversion.

The mandatory composition helper and all explicit build profiles use this
correction. The comparison's exact builder digest is updated, not removed.
The newly compiled harness is included in foundation source provenance.

## Executed local validation

406 distinct tests pass: six trace tests, 174 profile/resource/swap tests,
121 prompt/terminal tests, 36 messaging/codec/allocation tests and 69 recovery
and release-guard tests. There are no failures, errors or skips in these final
completed suites. A larger initial batch hit the execution limit before
producing JUnit and is retained separately; it is not counted as a pass.

The compiled trace harness uses ASan/UBSan and exercises 28 filter cases,
reference counts, nested lifetimes, GIL release, invalid Unicode fallback and
all three native composition modes. Across 30,000 measured lookups after
warm-up, allocation calls decrease from 30,000 to zero and allocated bytes
from 880,000 to zero. This is a component measurement, not a cgroup result.

Local Python is 3.13.5; full native builds require GIL-enabled CPython 3.13.15+
within 3.13. The version guard is unchanged. The complete rebuilt native family
and both mandatory Docker recovery scenarios require fresh hosted results.
See `evidence/native-trace-filename/local-validation.json` for source-bound
checksums and test receipts.

## Release decision

Existing 2 GiB/no-swap limits, 1,792 MiB peak and 64 MiB growth thresholds,
controller authority, operation deadlines, IDE pairing and all eleven release
gates remain unchanged. Optimized experimental passes do not clear mandatory
sanitizer failures. Full compatibility, public UI/debugger, deployed recovery,
independent security review and stable joint packaging remain required.
No stable tag, merge, publication or production migration is authorized by this
component receipt. New source requires new hosted qualification.
