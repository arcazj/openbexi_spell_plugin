LRM 2.4.4 sections 4.13 through 4.13.3 are being implemented against an explicit
GENERIC simulator display application. Native qualification is still pending;
the local protobuf tests do not qualify language requirements.

The catalog contains DSS_TELEMETRY and Displays/Telemetría (alphanumeric),
DSS_TREND (time plot), and two workspaces: DSS_WORKSPACE and
Workspaces/Operación. Each workspace opens its alphanumeric display and the plot
in one application instance. Workstations DSS and DSS_AUX have monitors 1 and 2.
Defaults are DSS, monitor 1, Reuse=True, a 60-second plot span, and PS output.
Reuse=False creates a distinct application; Reuse=True selects the most recent
application on the selected workstation and monitor. Closing a display removes
its instances on the selected workstation. Closing a workspace closes its member
displays there and preserves unrelated displays and other workstations.

Display names, hosts, monitors and printers are declared simulator resources, as
per the manual's driver-dependent naming rules. Folder-like Unicode names pass
through the native helper unchanged. The language does not impose a filesystem
path syntax. This profile accepts positive finite plot spans up to one day, at
most 16 application instances and 64 retained print jobs. Time applies to plots;
VECTOR applies to alphanumeric displays. PS output renders the actual acquired
values or plot. VECTOR is ASCII with recoverable escapes for non-ASCII text.
The existing shared ground-state size and collection limits also apply. Identical
acquired snapshots are stored once and referenced by hash; unused snapshots are
removed from that pool when no display or retained job refers to them. The
proposed state transition is checked against all limits before an effect intent.

PrintDisplay without Printer creates a downloadable document. Printer=DSS_REPORTS
places that document in the persistent virtual spool. Both remain available in
the journal across a driver reopen. No physical printer completion is implied.
PrintDisplay rejects workspace names. It selects the most recent application
containing the named display on Host when there are several instances.

The read-only local viewer can be started with:

    openbexi-spell-displays --journal PATH_TO_DRIVER_JOURNAL

It reports its loopback URL, shows the current application instances, and offers
the exact PS/ASCII documents for download. Select --namespace when the journal
contains more than one simulator epoch. Displays show the acquired snapshot;
reopening with Reuse=True refreshes that display. Plot axes use the requested
initial span and actual sample timestamps; no historical samples are invented.

The checked recipe adds the missing workspace functions, Monitor/Reuse modifiers
and PS/VECTOR constants. It also restores True return values for successful
native display calls. The original TASK protobuf schema is unchanged; workspace
calls carry a reserved private discriminator in its configuration dictionary.
That discriminator is rejected as a user-supplied modifier.

State validation runs inside the journal transaction after authority and cached
receipt checks, but before a new effect intent. Invalid state does not poison the
run, and a repeated receipted close still succeeds after the first call removed
the display. Native binaries are unchanged by this isolated Python correction.

The initial real-spool boundary test retained 30 completed jobs before repeated
full snapshot copies filled the shared state limit. Its database, original source
bytes and failing test report are retained under the ignored qualification
directory. Snapshot deduplication and complete capacity preflight replace that
behavior; the corrected tests fill all 64 jobs and check rejection/recovery for
both the shared size bound and the report-count bound.
