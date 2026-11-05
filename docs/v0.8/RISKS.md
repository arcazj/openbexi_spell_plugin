<!-- CURRENT QUALIFICATION -->
> **Current qualification — November 5, 2026:** IDE v1.2.1 and full SPELL v0.8 remain unqualified; all eleven release groups are open. See [current status, verified results and next work](CURRENT_STATUS.md). Earlier candidate IDs and bounded acceptance below apply to their recorded subjects.
<!-- END CURRENT QUALIFICATION -->

See the [latest measured root-cause report](ROOT_CAUSE_20261105.md) for the validated compiler change, freed-buffer attribution and remaining startup/deadline blockers.

# Open risks and qualification stop conditions

The current subjects, receipts and eleven open groups are recorded in [current status](CURRENT_STATUS.md) and [release gates](RELEASE_GATES.json). Published v0.8-rc1 and IDE v1.2.1 remain unqualified.

1. **Sustained memory fails.** The current local 300-second ASan/UBSan/no-swap handoff grows 229,232,640 bytes against 67,108,864 allowed. Historical original hours also fail. Allocation/allocator observations narrow investigation but do not prove a fix.
2. **Local foundation exceeds its budget.** The compiler correction reaches 1,380 completed passes without completed failures before 600 seconds. The short-volume experiment reaches 1,450 passes but fails three original concurrency/deadline checks and still times out. Hosted acceptance does not erase these local failures.
3. **Public native workflow remains incomplete.** Private existing-execution controls and retained-worker cohorts do not establish full public launch, debugger/source/results, graphical prompts, three browser identities, 20 observers, WSS recovery or Git-conflict acceptance.
4. **Complete compatibility is open.** All 763 requirements need fresh current-pair evidence. Historical source/capture drift and missing hashes cannot be replaced by current files or partial TIME/PY/DATA coverage.
5. **Deployment and recovery remain unqualified.** Compose/kind prelaunch is insufficient for full native workloads, denials, process/node/partition/storage faults, restore and fencing of old authority before replacement authority.
6. **External resources are missing.** Production-like enforced-NetworkPolicy cluster and independent implemented-system security reviewer remain unavailable. Earlier architecture/internal reviews do not satisfy implemented-system review.
7. **Delivered dependencies need full disposition.** Final portable native image, Qt/PySide/shiboken/ICU/helper closure, SBOM, licenses/notices/corresponding source, advisories and clean final installation remain open. Archived derivatives are unpromoted.
8. **Environment identities differ.** Hosted host Python is pinned to 3.13.17, but runner image revisions differ. Local/native/desktop dependency bytes are separate subjects. One successful environment does not establish another supported deployment.
9. **The local desktop has legacy native bytes.** Healthy port 6088 and published Python wheel integrity do not establish full v0.8 native acceptance; the existing image uses the v0.7 native baseline.
10. **Authority and uncertainty remain binding.** Stale actors must stay fenced; ambiguous effects retain holds without replay. Recovery/upgrade must preserve evidence and explicitly reconcile authority. Untrusted Python sandboxing and distributed HA are not inferred from current isolation tests.
11. **Promotion requires final-pair evidence.** Preserve published tags/assets and original unqualified disclosures. Repeat affected acceptance after runtime/dependency/package changes. Stable publication is authorized only after all mandatory gates pass; production migration remains unauthorized.

The latest checkpoint records no active qualification jobs and stopped temporary helpers. Reconcile live remote/container state before retrying or dispatching another run. Never relax original deadlines, concurrency, sanitizers, no-swap accounting or audit retention to obtain a pass.
