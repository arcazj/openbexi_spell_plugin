"""Fail-closed publication preflight for the full v0.8 acceptance plan.

This validates gate receipts; it does not run missing qualification or publish.
Subset/native-negative receipts can never stand in for full gate evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

REQUIRED = {
    "services": {"listener_worker_survival", "context_isolation", "bounded_authority"},
    "native_family": {
        "before_run_child_admission",
        "all_participant_pause",
        "control_prompt_queues_settled",
        "effects_settled",
        "owner_epoch_cas",
        "original_provenance_preserved",
        "explicit_new_owner_resume",
    },
    "compatibility": {
        "all_763_requirements",
        "original_driver_contract",
        "native_semantics",
    },
    "driver_faults": {
        "independent_dss",
        "correlation",
        "network_faults",
        "uncertain_no_replay",
    },
    "ide_browser": {
        "three_authenticated_users",
        "native_run_debug",
        "twenty_observers",
        "wss_gap_resync",
        "git_conflicts",
        "paired_ide_sources",
    },
    "compose": {
        "clean_boot",
        "ten_executions_twenty_viewers",
        "negative_auth_egress",
        "process_loss",
        "storage_failure_restore",
    },
    "kubernetes": {
        "kind_minikube",
        "production_like_cluster",
        "pod_identity",
        "rbac_admission_network_denials",
        "node_partition_storage_recovery",
    },
    "recovery": {
        "descendant_shutdown_proof",
        "old_authority_fenced",
        "effect_settlement",
        "restore_upgrade_rollback",
    },
    "security": {
        "independent_review",
        "source_secret_integrity",
        "bounded_load",
        "sbom_licenses",
        "vulnerability_disposition",
    },
    "ci": {
        "full_candidate_checks",
        "clean_checkout",
        "runtime_driver_browser_deployment",
    },
    "packaging": {
        "stable_versions",
        "checksums",
        "clean_install_smoke",
        "release_runbooks",
    },
}


def assess(root, candidate, ide_commit, *, dirty=False):
    root = Path(root).resolve()
    manifest = json.loads((root / "docs/v0.8/RELEASE_GATES.json").read_text())
    failures = []
    if (
        manifest.get("schema") != "openbexi.release-gates/1"
        or manifest.get("version") != "0.8.0"
        or set(manifest.get("gates", {})) != set(REQUIRED)
    ):
        raise ValueError("Full v0.8 gate manifest differs")
    authorization = manifest.get("publication_authorization", {})
    if authorization.get("request") != "Qualify and release full v0.8":
        failures.append("Explicit full-release publication authorization is missing")
    version = tomllib.loads((root / "server/pyproject.toml").read_text())["project"][
        "version"
    ]
    if version != "0.8.0":
        failures.append("Server package is development version " + version)
    if dirty:
        failures.append("Candidate has tracked or untracked runtime source changes")
    results = {}
    for name, required in REQUIRED.items():
        gate = manifest["gates"][name]
        errors = []
        if gate.get("qualified") is not True:
            errors.append(gate.get("reason", "Mandatory gate has not passed"))
        else:
            reference = gate.get("receipt")
            if type(reference) is not dict or set(reference) != {"path", "sha256"}:
                errors.append("Immutable gate receipt is missing")
            else:
                path = Path(reference["path"])
                selected = (root / path).resolve()
                if (
                    path.is_absolute()
                    or not selected.is_relative_to(root)
                    or ".." in path.parts
                ):
                    errors.append("Receipt path escapes the candidate checkout")
                elif not selected.is_file():
                    errors.append("Gate receipt file is missing")
                elif selected.stat().st_size > 2 * 1024 * 1024:
                    errors.append("Gate receipt exceeds its size bound")
                else:
                    data = selected.read_bytes()
                    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
                        errors.append("Gate receipt digest differs")
                    else:
                        receipt = json.loads(data)
                        if (
                            receipt.get("schema") != "openbexi.v08.acceptance-gate/1"
                            or receipt.get("gate") != name
                            or receipt.get("passed") is not True
                            or receipt.get("candidate_commit") != candidate
                            or receipt.get("ide_commit") != ide_commit
                            or type(receipt.get("checks")) is not dict
                            or set(receipt["checks"]) != required
                            or any(
                                value is not True
                                for value in receipt.get("checks", {}).values()
                            )
                        ):
                            errors.append(
                                "Gate identity, source binding or mandatory checks are incomplete"
                            )
                        if (
                            type(receipt.get("evidence")) is not list
                            or not receipt["evidence"]
                        ):
                            errors.append(
                                "Executed test/deployment evidence references are missing"
                            )
        results[name] = dict(qualified=not errors, errors=errors)
    qualified = not failures and all(r["qualified"] for r in results.values())
    return dict(
        schema="openbexi.v08.publication-preflight/1",
        version="0.8.0",
        candidate_commit=candidate,
        ide_commit=ide_commit,
        full_v08_qualified=qualified,
        eligible_for_publication=qualified,
        publication_performed=False,
        failures=failures,
        gates=results,
    )


def evidence_only(path):
    return path.startswith("docs/v0.8/") and (
        path.endswith(".md")
        or path in ("docs/v0.8/STATUS.json", "docs/v0.8/RELEASE_GATES.json")
        or (
            path.startswith("docs/v0.8/evidence/")
            and Path(path).suffix
            in {".json", ".txt", ".log", ".xml", ".png", ".sha256"}
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        help="Verified executable commit; later evidence-only commits are allowed",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checkout = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    candidate = args.candidate or checkout
    if not re.fullmatch("[0-9a-f]{40}", candidate):
        parser.error("Candidate must be an exact commit SHA")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate, checkout], cwd=root
    ).returncode:
        parser.error("Candidate must be an ancestor of the checkout")
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", candidate, checkout], cwd=root, text=True
    ).splitlines()
    dirty = any(
        subprocess.run(cmd, cwd=root).returncode
        for cmd in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"])
    )
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    dirty = dirty or any(
        p.startswith(
            (
                "server/src/",
                "host_runtime/python/",
                "host_runtime/native/",
                "host_runtime/build_admission_context.py",
                "driver_plugin/src/",
                "src/dss/",
                "shared_plugin/src/",
            )
        )
        for p in untracked
    )
    dirty = dirty or any(not evidence_only(p) for p in changed)
    ide = json.loads((root / "docs/v0.8/IDE_PAIR.json").read_text())["ide_commit"]
    result = assess(root, candidate, ide, dirty=dirty)
    result["qualification_checkout_commit"] = checkout
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["eligible_for_publication"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
