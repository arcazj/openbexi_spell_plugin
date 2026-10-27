# Native diagnostic retention and swap-helper permissions

This is a source-bound correction, not a full v0.8 release receipt.
Base commit: `2d0e8e1f982295c9976869f2c9a286d1cc403a82`.
Base tree: `75bd90caf527d9a25ba73250f4a23b6d71b1e86d`.

## Completed hour-long baseline

Both optimized endurance cases in hosted run `40433115741` completed at least
3,600 seconds, retained eight original processes, maintained progress and
verified the repeated controller-transfer/reconnect sequence. Neither passed
memory acceptance. The first/last ten-second windows explain the failure:

| Measurement (MiB) | Handoff | Installed IDE |
| --- | ---: | ---: |
| Whole-cgroup window growth | 131.30 | 132.53 |
| File-backed growth | 126.09 | 126.13 |
| Anonymous-memory growth | 2.91 | 5.92 |
| Growth in the final ten-minute comparison | 0.10 | 0.14 |

The `shmem` growth equals the file-backed growth; these accounting categories
overlap and must not be added. Shared-memory usage reaches approximately
128 MiB, matching the existing worker `/tmp` tmpfs capacity. Thread medians
remain 110/110 and 111/111 respectively. Four downloaded archive digests were
verified, together with every recorded evidence-file hash in both endurance
receipts and the swap receipt. Raw values and artifact IDs are retained in
`evidence/native-log-retention/local-validation.json`.

This is evidence of file/shared-memory-backed growth, not a per-file inventory
or proof of a native object leak. The source nevertheless has a concrete
retention-budget mismatch: each native diagnostic logger permits a 10 MiB
active file plus five backups. Four rebuilt logging roles can therefore retain
approximately 240 MiB in a 128 MiB tmpfs, before other files are counted.

## Correction and retention tradeoff

The exact-source native composition now retains a 1 MiB active diagnostic file
and one backup per rebuilt logging role. This is an approximately 2 MiB target
per role (plus the record crossing rotation), or 8 MiB across four roles in the
explicit complete-family builds. The mandatory builder rebuilds Context and
Executors; its frozen Listener is not modified by this patch.

The change deliberately retains less historical native diagnostic output.
Severity, formatting, immediate flush and directory-creation behavior are
unchanged. ASRUN/procedure records, audit records, sanitizer output, stdout
capture, authority policy, operation deadlines, memory limits and acceptance
criteria are untouched. This does not establish a bound on all worker files.
A new hosted endurance result is required to demonstrate the actual reduction.

## Swap experiment preparation defect

The encrypted device is successfully established, but the baseline comparison
fails at independent DSS startup with `ModuleNotFoundError: No module named
'dss'`. The helper sets a process-wide `umask 077`, inherited by the harness.
Generated bind-mounted Python code consequently becomes mode 0700/0600 and is
unreadable to the separate container user.

The helper now applies 077 only inside the backing-file creation subshell. The
backing file remains mode 0600 and its private directory remains mode 0700;
the comparison command inherits the caller's original mask. Cleanup and the
comparison's exit status are preserved. The helper does not make code or any
secrets more permissive than the caller's chosen policy.

## Executed local validation

208 distinct tests pass with zero failures, errors or skips:
- 187 profile/resource/swap/log tests using the exact updated CI test command;
- six sanitizer-backed trace/native-composition regressions;
- 15 sanitizer-backed message-storage/stream regressions.

The swap tests execute the real Bash helper with simulated privileged commands,
never configuring kernel swap. They reproduce the prior inherited 077 failure,
check masks 022/027/077, private backing modes, cleanup and failure exit codes.
Exact-source logging tests reject drift or duplicate application and verify that
ASRUN sources are unchanged. Actual log4cplus rotation and a complete native
Docker rebuild were not executed locally. Ruff lint/formatting, shell syntax,
and whitespace checks pass. Ten protected files remain byte-identical.

## Outstanding mandatory result

The latest mandatory handoff baseline in run `40433115844` still fails the
45-second growth limit (130.68 MiB versus 64 MiB). The long-run file-retention
finding does not prove that all short-run sanitizer growth is fixed. Both
mandatory recovery cases, both hour-long cases and the repaired swap comparison
must be rebuilt and rerun on this new source. No release gate is promoted, and
full v0.8 qualification remains false.
