<!-- CURRENT QUALIFICATION -->
> **Current qualification — November 5, 2026:** IDE v1.2.1 and full SPELL v0.8 remain unqualified; all eleven release groups are open. See [current status, verified results and next work](CURRENT_STATUS.md). Earlier candidate IDs and bounded acceptance below apply to their recorded subjects.
<!-- END CURRENT QUALIFICATION -->

<!-- ROOT CAUSE FOLLOWTHROUGH 20261105 -->
> **Latest investigation:** [Context/DSS deadlines and complete memory trace](CONTEXT_DSS_DEADLINES_20261105.md): matched concurrent checks and live heartbeats pass; reference foundation passes all 1,823 tests in 547.880 seconds. The complete 303.491-second diagnostic still fails memory growth (304.76 MiB versus 64 MiB), with zero swap. All original limits and failed evidence are retained; no memory correction or release qualification is claimed.
<!-- END ROOT CAUSE FOLLOWTHROUGH 20261105 -->

# Local qualification runner requirements

The native harness is a trusted host observer. It uses Docker-host PIDs for `pidfd_open`, reads container cgroups and reads paused processes through `/proc/<pid>/root` using noninteractive privileged Python. Running it in a helper's private PID/cgroup namespaces is incompatible with that existing oracle.

The November 5 reproduction failed with `ProcessLookupError` at `v08_handoff_cohort.py:410` after native startup, child and driver checks. A read-only control against the already-running IDE container failed in the original helper, then passed in the corrected helper with the same container ID, PID, PID namespace and cgroup binding. This explains that specific observation failure. It does not establish the causes of earlier DNS, Docker-start, Context timeout or memory failures.

Keep the helper separate from the product's workers and Context. The local diagnostic helper uses host PID/cgroup/network namespaces, the existing Docker management socket, a dedicated durable volume, a 3 GiB memory limit and a 512 PID limit. It runs as UID 10003 and permits only the existing privileged Python observation commands through sudo. Its capability bound adds `SYS_PTRACE` for trusted process observation; it is not a product image or production deployment recommendation. Worker and Context namespaces, capability drops, authentication and resource limits remain unchanged.

Set `TMPDIR` and `HOME` to the dedicated volume's absolute Docker-host path before starting the harness. A temporary path private to the helper cannot be mounted by sibling containers through the host Docker daemon. The verified local path is `/var/lib/docker/volumes/openbexi-v08-qualification-20261104/_data`. Preserve its evidence and persistent files.

External DNS resolution is a distinct setup prerequisite. A local diagnostic may preprovision the frozen native base archive, but must still run the original archive size, SHA-256, copy deadline and loaded-image checks. The v0.7 base archive is an input to the candidate native build; it is not itself a v0.8 qualification result. Record the provisioning wrapper and archive digest separately from the unchanged product source.

Before expensive native execution, verify a live known container's Docker ID, host PID, `/proc` PID namespace, cgroup path, pidfd access and the privileged read path. Reject a mismatched runner early. Never compensate by bypassing pidfds, reading a recycled PID, thawing a paused worker to inspect it, relaxing operation deadlines or disabling isolation checks.

Hosted run 41957183593 passed 1,818 foundation tests and both native 45-second scenarios. Its environment receipts exposed a floating Python selector: foundation used 3.13.18 while the native jobs used 3.13.17. Subsequent reference runs pin host Python 3.13.17. Packaged native and desktop Python versions remain separately recorded build inputs.

The subsequent pinned run [41958849238](https://github.com/arcazj/openbexi_spell_plugin/actions/runs/41958849238) passed 1,818 foundation cases in 461.451 seconds and both native 45-second scenarios with host Python 3.13.17. Its three jobs used different CPU models and two runner image revisions, retained in [the environment contract](QUALIFICATION_ENVIRONMENTS.json). Local handoff and installed-IDE 45-second checks passed on the corrected helper. The isolated local foundation still timed out at 600 seconds, and the 300-second sanitizer/no-swap handoff failed with 256,954,368-byte growth against 67,108,864 allowed. At the checkpoint both temporary helpers were stopped; their volume and failed evidence remain retained.
