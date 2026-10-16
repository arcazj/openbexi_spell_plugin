LRM 2.4.4 pages 72-74 describe display/workspace opening and closing, Host and
Monitor routing, Reuse, plot time spans, and PS/VECTOR printing. Workspace names
are not valid PrintDisplay targets. Display names and monitor identifiers are
driver dependent. The original function docstrings specify True on success for
OpenDisplay, CloseDisplay and PrintDisplay.

The initial four probes retain native API availability, actual helper results,
binary TASK requests/responses, simulator state and execution logs. They check
workspace/format names, a default display lifecycle, routing options and VECTOR
printing. They are counterexample collection only: they do not provide all four
qualification dimensions or qualify any inventory requirement.

Implementation and final qualification require an explicit GENERIC display and
workspace catalog, observable display instances and options, and real PS/ASCII
output artifacts. A JSON snapshot is not evidence of a printed PS/VECTOR file.
The declared simulator profile must remain distinct from physical GCS displays
and printer hardware. Broader Format and Time modifier contracts remain separate.
