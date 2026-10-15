# Separate periodic schedule from on-demand ranging

This is a later, isolated tranche. It is excluded from the current composed
runtime freeze. The previous donor's 36 native observations expose the existing
one-state simulator behavior; only its three catalog rows qualify.

LRM p93 distinguishes periodic schedule enable/disable from on-demand activity
start/abort. This tranche keeps `ranging_schedule_enabled` as a persistent exact
boolean and `ranging` as independent activity state. It does not emulate RF or
implement a dual path, periodic plan execution, baseband calibration formulas,
or the still-open language GetRangingStatus constant translation.

Enable and Disable change only the schedule flag. Start and Calibration change
only the activity, regardless of the periodic schedule. Abort changes only the
activity to READY. Unknown options, invalid names, driver authority, effect
intent/receipt pairing, and unresolved-effect fencing keep their existing rules.

Opening an existing namespace migrates legacy DISABLED to false schedule plus
READY activity; legacy READY/RANGING/CALIBRATING infers an enabled schedule and
preserves the activity. An explicit schedule boolean, including false during an
active operation, is preserved. Unrelated namespace data and all other namespaces
must remain byte-for-byte unchanged where no migration is needed. Migration is
atomic and idempotent. Malformed states fail rather than being reset.

Independent controls will reopen newly written and migrated states, test both
schedule operations during ranging/calibration, start while schedule is disabled,
abort without changing schedule, and preserve a deliberately interrupted real
effect receipt without automatic replay. Migration controls seed only declared
legacy fixtures; operational changes traverse original native helpers and RPC.

An old runtime that conflates schedule/activity is not a qualified rollback
reader/writer for this migrated database. Rollback requires a retained compatible
database snapshot; running the old writer against the new state can erase active
activity or contradict the schedule flag. This tranche does not claim otherwise.
