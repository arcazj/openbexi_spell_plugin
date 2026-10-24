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

Any dual controller, observer mutation, accepted stale epoch, duplicate active
logical procedure, replayed uncertain TC, leaked credential, unapproved semantic
regression, failed mandatory CI or missing required qualification blocks release.
