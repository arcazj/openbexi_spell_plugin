# Execution through v0.6

Authorized target: finish and commit each release in order through plugin v0.6,
including prerequisite changes and qualification in the sibling openbexi_ide.
The working IDE v0.2 / bounded plugin v0.1 remains the testing baseline while the
original-source runtime is developed in isolated environments.

| Release | State | Required evidence |
| --- | --- | --- |
| v0.2 | In progress; source alpha 0.2.0a1 complete | Native UTIL/DTA link/load, references and errors; EXC control flow; WS recovery; real context/EXEC/CIF setup/cleanup |
| v0.3 | Pending v0.2 | Installed OpenBEXI extension and actual IntelliJ/PyCharm plugin ZIP, verifier and host Run/Debug/removal |
| v0.4 | Pending v0.3 and IDE service prerequisites | Original driver RPC families through DSS, three operating modes, controller fencing and uncertain-effect recovery |
| v0.5 | Pending v0.4 | Every inventory requirement assigned and independently qualified, source/manual conflicts resolved |
| v0.6 | Pending v0.5 | Reproducible distribution, platform matrix, clean installation/removal, upgrades, actual host and DSS-container workflows |

Native work starts with public CPython 3.13 frame/compiler APIs and Python error
ownership in UTIL. DTA keeps the original native types; EXC and warm-start need
behavioral qualification beyond compilation. No compatibility shim may pretend
that removed interpreter stacks or unsupported executor services work.

Existing source-alpha evidence is the historical `source-v0.2.0a1` snapshot.
New evidence must identify its exact source and patches. Release tags are created
only after the corresponding acceptance gates pass. Cleanup removes only
demonstrably obsolete project resources and preserves active test services.
