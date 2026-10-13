# Independent schedule/activity correction

The original native controls pass **21/21** on the candidate, using the same
oracles that fail **21/21** on the prior helper-only image. This donor promotes
**zero new inventory rows**. The prior donor's three catalog rows are unchanged.
The periodic plan executor, RF hardware, dual paths, baseband list/ENG/RAW handling,
status constants and complete ranging functions remain separate open contracts.

The checked recipe changes only `openbexi_spell_dss/ground.py`:

- Original SHA-256: `727669bbe36281faebbe7d5e53f9e1cf5db2d262ff7e9496e9aa89c3d9130880`
- Candidate SHA-256: `cb7524ea79718eec5c8467b701d00fe15318781cb7b5509df8fccfc3eb9aea07`
- Recipe SHA-256: `c9eeca8a7685b7bc3abc53385584f73b8b0c79a89b6d98a0011d147f4f333308`

Enable/Disable toggle a persistent exact-boolean schedule flag without changing
the active operation. On-demand Start/Calibration work while the periodic schedule
is disabled. Abort clears the activity and preserves the schedule. Existing
validation, authority, effect journal, receipt handling and fencing remain in use.

Opening a legacy namespace migrates DISABLED to idle READY plus a disabled
schedule; READY/RANGING/CALIBRATING retains its activity and infers enabled
schedule. An explicit schedule flag is preserved, including false while active.
The transaction is idempotent, preserves unrelated fields/namespaces, and rejects
malformed state without overwriting it. New and migrated data survive closing and
reopening the actual SQLite journal and reconstructing the real dispatcher.

The native sequence traverses original helpers and the binary driver. It verifies
enable/disable during both active ranging and calibration, disabled-schedule
on-demand activity, Abort under both schedule values, malformed calls and
recovery, persisted migration and reopening. The receipt-loss control lets the
real Ground effect commit, then deliberately fails receipt persistence. The actual
effect stays PENDING; two later real effect RPCs are fenced after journal reopen,
the activity remains unchanged, and no replay occurs. A read-only catalog request
still succeeds. This is controlled failure injection, not a simulated successful
command.

The final candidate journal retains **51 RECEIPTED effects and 1 PENDING effect**.
There are 71 captured ranging RPCs, including 59 successful responses. The final
activity is RANGING with schedule false. All per-operation request IDs, digests,
receipt bodies, persistent state observations, native logs and source inputs are
retained. Full native event/control arrays remain in raw evidence with their
canonical JSON hashes recorded in the compact report.

| Run | Exact image | Raw evidence and SHA-256 |
| --- | --- | --- |
| Baseline, 0/21 pass | ae9c39c8de3c59f5ab611f11143f79c834addc2b93a9dea25fd2efa11a6aed75 | .qualification/v0.5/rng-state/70c8a6be8f634af4aef621174afff859/result.json — 869fa9d672a8ce1827d267d1a1e58e4a65058460683fcc77bb3595424f2489ef |
| Candidate, 21/21 pass | ef2cabf5d4569f2ad550efd7880623371b53b0ac3480fa07f30199445c3a77b8 | .qualification/v0.5/rng-state/bc96ef62a1414ee680feef9c22fb3e6e/result.json — 12f8ce530de0ed858d1a2f4398ac2e22aec18003886f388f6ee3a5c981824ef8 |

Nineteen real-SQLite unit checks cover new defaults, all legacy states, explicit
false and true schedules during active operations, repeated reopening, unrelated
data preservation, malformed-state atomicity and strict source preimages. The
existing real binary driver regression suite passes **28/28** with the checked Ground
class loaded in its isolated test process, preserving the actual dispatcher,
gRPC server, transport, journal and DSS engine.

The legacy source profile and the 19 migration checks pass together **47/47**.
Both local runs bind the source inputs before execution and verify them afterward;
their JUnit records contain no failures, errors or skipped tests.

| Local regression | Retained result and SHA-256 |
| --- | --- |
| Separate-state real RPC, 28/28 | `.qualification/rng-state-driver/7373fecd70ac48239bfbb70923eef2f7/result.json`; `f9bace4700370b8c02ddcbd7f8213aed23b06ed7abb5f603bcc56377fc8a6e42` |
| Legacy RPC plus migration, 47/47 | `.qualification/rng-state-local/8a0f952903c740ac9a2d2790378f7193/result.json`; `3870c4cdf580b71176281db5e156b95ca9cdd5089cebab65855ad7fb2e06e737` |

The former general driver assertion that a disabled schedule prevents on-demand
start is retained only for its explicitly legacy source profile. The corrected
profile instead asserts initial schedule=false, successful on-demand start with
the flag still false, and Enable preserving active ranging while setting true.
This fixture distinction does not promote the legacy behavior as manual support.
The independent native oracle supplies the actual semantic counterexample.

The diagnostic overlay preserves the original native binaries and helper/proxy
donor; fresh composed wheels, RECORD verification and release regression remain
separate. This imported native oracle does not qualify generic procedure
checkpoint/warm-start recovery. Full v0.5/v0.6 acceptance remains false.

Old conflated-state runtimes are not qualified writers for the migrated database.
A rollback requires a compatible retained database snapshot. No database is
silently reset, and an old writer's contradictory state may be rejected on reopen.
