# Open risks and stop conditions

1. Per-execution authority is absent from the durable baseline. Missing any
   debug, prompt, slot or driver effect path can permit stale authority. G3
   blocks release until the complete mutation matrix passes.
2. Native worker RPC adaptation and static Compose worker reuse are unproven.
   Quiescence must include every descendant; uncertain runs keep reservations.
3. Compose networks do not enforce a complete egress firewall. Actual denial
   tests and deployment controls are required; do not claim otherwise.
4. Kubernetes is not qualified here. Node partition, storage fencing, RBAC
   admission restrictions and remote worker lifetime require a real cluster.
5. The legacy source version differs from the 2.4.4 manuals. Vendor GCS and
   GCS→DSS integration are unknown and remain disabled until validated.
6. Baseline has no hosted CI results. Green local tests are not green GitHub
   checks; the required CI and independent security review remain release gates.
7. Arbitrary untrusted Python and multi-tenant isolation are not established
   by the baseline or `-I`. Preserve approved-procedure/trusted-host scope and
   review the worker threat model before expanding it.
8. Existing authority schema cannot be upgraded by adding columns and silently
   resuming old work. Recovery must preserve uncertain effects, advance epochs
   and require explicit reconciliation.

9. The dev25 traced singleton-verification fixture stalled before child creation.
   Moving mandatory singleton checks to native bootstrap allowed the dev26 family
   to finish. The exact traced fixture failure is unresolved; generator/module-
   inspection/debugger behavior needs separate compatibility qualification before
   any full-v0.8 compatibility claim.

10. Dev28 PR native DSS hit four unchanged two-second effect deadlines while
    the push cohort and local stress passed. Exact performance cause is open.
    Dev29 changes only explicit qualification CPU weights and incomplete-
    operation safety fencing; neither is a full deployed load qualification.

11. The dev31 evidence-only push at `73ce9dd` failed while opening one native
    procedure: the unchanged 15-second startup deadline expired with status
    LOADED and no code position. Its PR cohort passed. The cause is unresolved;
    do not hide the failure with retries or relabel it as successful native
    qualification. The checksummed failed-artifact receipt is retained.

12. Dev32 PR native family OOM-killed worker 0 at its inherited 768 MiB cap,
    before reaching the owner-command probe. The push passed actual STEP and
    stale second-STEP rejection. Dev33 assigns explicit two/three-Executor
    qualification memory budgets and checks cgroup peak/OOM accounting. The
    failed attempt remains evidence; production resource admission and leak/
    sustained-load qualification remain pending.

Any dual controller, observer mutation, accepted stale epoch, duplicate active
logical procedure, replayed uncertain TC, leaked credential, unapproved semantic
regression, failed mandatory CI or missing required qualification blocks release.
