"""Map the 418 originally incomplete rows to their exact source oracles and remaining work."""

import argparse
from collections import Counter
import json
from pathlib import Path
from v08_compatibility_final_rollup import EVIDENCE, ROOT, read, require, sha, totals


# The original per-report controllers and run entrypoints are resolved below from
# the hash-verified domain index. Each row retains its own four distinct check names.
PREREQUISITES = {
    "python": (
        "ordinary language",
        "source",
        "Run the original language cases on one worker and verify every declared parent/child dependency in its own dimension.",
    ),
    "python_sections": (
        "ordinary language",
        "composition",
        "Join the original language run with the legacy comparison compiler, SCDB existence and dictionary value grammar proofs on one installed subject.",
    ),
    "legacy_compare_composed": (
        "ordinary language",
        "composition",
        "Capture the original native compiler and AST analyzer agreeing on the manual legacy comparison spelling, including rejection and recovery.",
    ),
    "user_database": (
        "files and dictionaries",
        "native controller",
        "Exercise the remaining create and save case programs in separate writable user directories, including the original filesystem modes and persisted bytes.",
    ),
    "database_import": (
        "files and dictionaries",
        "configured fixture",
        "Mount the original catalog database fixtures and capture the native import, rejection and recovery results.",
    ),
    "database_scope": (
        "files and dictionaries",
        "configured fixture",
        "Capture the original page-79 existence method on the configured read-only database.",
    ),
    "database_values_composed": (
        "files and dictionaries",
        "composition",
        "Join the original database value grammar and user persistence results on one composed runtime.",
    ),
    "scdb": (
        "files and dictionaries",
        "configured fixture",
        "Initialize the original read-only catalog database at native startup, then inspect its lookup and error outcomes.",
    ),
    "v05_database_complete": (
        "files and dictionaries",
        "composition",
        "Join the original dictionary-family, format, typing, persistence and lifecycle component reports under one installed profile.",
    ),
    "files": (
        "files and dictionaries",
        "native controller",
        "Cover the original whole file-manipulation and error-policy case dependencies, including the native prompt and independent filesystem observations.",
    ),
    "child_arguments": (
        "procedure flow",
        "native controller",
        "Capture the original parent-to-child argument values and child results on a registered native family.",
    ),
    "child_execution": (
        "procedure flow",
        "native controller",
        "Observe the original child starts and automatic/manual transitions from both real processes.",
    ),
    "child_policy": (
        "procedure flow",
        "native controller",
        "Capture the original terminal and blocking-policy outcomes from independently observed parent/child processes.",
    ),
    "child_returns": (
        "procedure flow",
        "native controller",
        "Observe the original parent return values alongside the matching child's stored terminal state.",
    ),
    "flow": (
        "procedure flow",
        "native controller",
        "Run the original native flow scenarios with an independent IPC observer for pauses, action-state and terminal transitions.",
    ),
    "v05_flow_complete": (
        "procedure flow",
        "composition",
        "Capture all child modes plus the actual installed client's visibility results and join the original per-row dependencies.",
    ),
    "proc_dictionary_composed": (
        "procedure flow",
        "composition",
        "Join procedure metadata and lifetime results from original parent/child runs on the same subject, including resolved I/O paths.",
    ),
    "data-race": (
        "data and concurrency",
        "native controller",
        "Run the original competing native data owners and observe consistency and recovery through the independent controller.",
    ),
    "dta": (
        "data and concurrency",
        "native controller",
        "Capture native typed container item transitions and controller answers required by the original typed-data cases.",
    ),
    "predefined_containers": (
        "data and concurrency",
        "composition",
        "Join original typed ARGS/IVARS events, external client edits, resume, and child argument transfer where required.",
    ),
    "v05_data_complete": (
        "data and concurrency",
        "composition",
        "Combine the original file, concurrent update and typed-data component receipts on the deployed subject.",
    ),
    "wait_time": (
        "time and interaction",
        "native controller",
        "Independently time the original relative/absolute waits and observe WAITING/FINISHED transitions for the designated cases.",
    ),
    "wait_interval": (
        "time and interaction",
        "native controller",
        "Observe the original countdown/progress sequence and independent clock checks in native time-wait runs.",
    ),
    "wait_control": (
        "time and interaction",
        "native controller",
        "Observe original interruption, resumption and cancellation of time and simulated-data waits through native control IPC.",
    ),
    "scheduler": (
        "time and interaction",
        "native controller",
        "Capture the original native time-wait progress and status events using its independent clock observer.",
    ),
    "timing": (
        "time and interaction",
        "configured fixture",
        "Reconcile the original clock-based assertions with the independent simulated data source and its event history.",
    ),
    "common-silence": (
        "user interface and common behavior",
        "native controller",
        "Capture native output before, during and after original silent execution with an independent message observer.",
    ),
    "common": (
        "user interface and common behavior",
        "native controller",
        "Observe the original terminal/error-policy states and owner-side decisions for the two unmatched requirements.",
    ),
    "notification": (
        "user interface and common behavior",
        "native controller",
        "Capture original notification content, suppression and native message delivery against its independent message controller.",
    ),
    "prompt_timeout": (
        "user interface and common behavior",
        "native controller",
        "Observe native timed default, cancellation and owner reply interactions with the original controller and deadline.",
    ),
    "ui": (
        "user interface and common behavior",
        "native controller",
        "Capture the original independent UI IPC, including MSG_WRITE/ITEM content and per-case edge behavior. The existing 56 embedded verdicts cover 48 externally checked prompt assertions.",
    ),
    "v05_ui_complete": (
        "user interface and common behavior",
        "composition",
        "Join the original installed UI, native output, owner interaction and host audio component evidence for each allocated row.",
    ),
    "events": (
        "declared simulation integration",
        "configured fixture",
        "Combine original event observations from the native controller and its independent configured simulation records.",
    ),
    "resource": (
        "declared simulation integration",
        "configured fixture",
        "Capture original shared-resource ownership and state from the declared simulator plus native owners.",
    ),
    "obs": (
        "declared simulation integration",
        "configured fixture",
        "Use the original independent observation controller and its declared simulator faults, prompted outcomes and readback for the unresolved checks.",
    ),
    "cmd": (
        "declared simulation integration",
        "configured fixture",
        "Use the original independent simulation receipts and native outcomes for the unmatched declared profile checks.",
    ),
    "value_units": (
        "declared simulation integration",
        "configured fixture",
        "Capture original type and unit metadata against the independently decoded synthetic fixture output.",
    ),
    "limit": (
        "declared simulation integration",
        "configured fixture",
        "Supply the original simulation catalog, independent monitor and expected readings for the unresolved legacy checks.",
    ),
    "rng": (
        "specialized simulation",
        "configured fixture",
        "Supply the approved specialist fixture and original independent domain-oracle records for the exact inherited checks.",
    ),
    "command_display_composed": (
        "declared simulation integration",
        "composition",
        "Join the original simulation and virtual-display components with independent state and output observations on a common installed subject.",
    ),
    "v05_command_complete": (
        "declared simulation integration",
        "composition",
        "Join the allocated original native and private simulation component reports, including external output receipts.",
    ),
    "v05_common_complete": (
        "user interface and common behavior",
        "composition",
        "Join the declared native, configured driver and common-language component records for the remaining rows.",
    ),
    "v05_limit_complete": (
        "declared simulation integration",
        "composition",
        "Join original monitor, configured catalog and feature component reports in the same declared simulation profile.",
    ),
    "v05_observation_complete": (
        "declared simulation integration",
        "composition",
        "Join the original timed acquisition, failure and owner interaction reports with independent configured simulator evidence.",
    ),
    "v05_special_complete": (
        "specialized simulation",
        "composition",
        "Join the original specialist fixture, reference outputs and independently verified component records on a common declared subject.",
    ),
}


def tally(items, key):
    return dict(sorted(Counter(row[key] for row in items).items()))


def run():
    inventory, passed, failed, _, _ = totals()
    final = read(EVIDENCE / "compatibility-final-rollup.json")
    delta = set(final["47e_python"]["new_parent_ids"]) | set(
        final["47e_files"]["new_direct_ids"]
    )
    index = read(EVIDENCE / "compatibility-domain-oracles.json")
    sources = {d["report"]: d for d in index["historical_domains"]}
    domains, rows = {}, []
    for identifier, row in inventory.items():
        if identifier in passed | failed:
            continue
        refs = row["historical_oracles"]
        reports = {v["report"] for v in refs.values()}
        require(
            len(refs) == 4 and len(reports) == 1, "Expected one original report per row"
        )
        report = reports.pop()
        name = Path(report).stem
        category, kind, prerequisite = PREREQUISITES[name]
        if name not in domains:
            source = sources[report]
            require(
                sha(ROOT / report) == source["report_sha256"],
                "Original oracle report changed",
            )
            domains[name] = {
                "original_report": report,
                "sha256": source["report_sha256"],
                "category": category,
                "required_evidence": kind,
                "prerequisite": prerequisite,
                "original_runtime_image": source["original_runtime_image"],
                "controller_sources": source["controllers"],
                "original_runner_entrypoints": [
                    v["entrypoint"] for v in source["historical_commands"]
                ],
                "originally_incomplete": 0,
                "still_incomplete": 0,
            }
        domains[name]["originally_incomplete"] += 1
        domains[name]["still_incomplete"] += identifier not in delta
        rows.append(
            {
                "id": identifier,
                "inventory_package": row["package"],
                "manual_pages": row["manual_pages"],
                "domain": name,
                "category": category,
                "required_evidence": kind,
                "original_checks": {dim: ref["check"] for dim, ref in refs.items()},
                "after_47e": "PASS" if identifier in delta else "INCOMPLETE",
            }
        )
    remaining = [row for row in rows if row["after_47e"] == "INCOMPLETE"]
    require(
        len(rows) == 418
        and len(remaining) == final["across_tested_subjects"]["incomplete"]
        and len(remaining) + len(delta) == len(rows)
        and len(domains) == len(PREREQUISITES),
        "Incomplete row coverage changed",
    )
    return {
        "schema": "openbexi.v08.compatibility-prerequisite-map/2",
        "originally_incomplete": len(rows),
        "closed_on_47e": len(delta),
        "still_incomplete": len(remaining),
        "original_by_package": tally(rows, "inventory_package"),
        "remaining_by_package": tally(remaining, "inventory_package"),
        "original_by_category": tally(rows, "category"),
        "remaining_by_category": tally(remaining, "category"),
        "original_by_prerequisite": tally(rows, "required_evidence"),
        "remaining_by_prerequisite": tally(remaining, "required_evidence"),
        "interpretation": "The named historical report and controller identify the evidence required by the original contract. All cited report files were rehashed. An incomplete row does not establish a missing implementation. The 27 positive-dimension failures are recorded separately in compatibility-negative-rows.json.",
        "per_domain": {
            k: v for k, v in sorted(domains.items()) if v["still_incomplete"]
        },
        "rows": remaining,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    result = run()
    opts.output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(result["remaining_by_prerequisite"])
