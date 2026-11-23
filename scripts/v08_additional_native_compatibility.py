"""Verify additional native compatibility checks against the original 763-row evidence map."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    ROOT
    / "docs/v0.8/evidence/qualification-20261122/compatibility-native-inventory.json"
)
sys.path[:0] = [str(ROOT / "conformance"), str(ROOT / "src")]
from deployed_generic_cases import require, verify_simulation  # noqa: E402


SPELL = "655f5b5a2de31bd4f8cba44794a1798342986512"
IDE = "fadac70d574760cbe21c5e5512a384dddfa36e80"
WORKER = "sha256:a545c9617133bfc8034f385ef0ffb71c5eb2cfc9a74fd078838ee33bdf6753d4"
CORE = "sha256:1426fbd0b032ebe86f128474f27ac20e2b12200a3c544a7467c5b8f05e98100d"
GATEWAY = "sha256:fdd6bf0f754c414d846b7199b1bddeaf4cea5d70a899ba7878a3de4bc6e80ac8"
OPTIONAL_CONTEXT = (
    "sha256:79208f72a4335dab86493d6ac3cf44ff1cd0ed7f6f0eb3a7e0bb19d477353e35"
)
CLIENT = "7694c8c3d2094ab84ee2e47465ab2481df5bd3af595642ab66f550c19bfc44fd"
ORIGINAL_COLLECTOR = "c59f7551abca31f105299241af24ac6d5084104e7f297526f5bc415ecbab8bd8"
SUITES = {
    "obsmore": ("morec", "obs"),
    "commonfull": ("commc", "common"),
    "uifull": ("uia", "ui"),
    "limitprobe": ("histscopeb", None),
}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authority(folder, execution, identity):
    stored = read(folder / "stored-authority.json")
    require(
        stored["spent"] == 1
        and len(stored["members"]) == 1
        and stored["results"]
        == [{"execution_id": execution, "native_status": "FINISHED"}],
        "Authoritative terminal result differs",
    )
    member = stored["members"][0]
    require(
        member["execution_id"] == execution
        and all(
            member[k] == identity[k]
            for k in ("pid", "start_ticks", "executable_sha256")
        ),
        "Stored PID, process start time, or actual executable differs",
    )
    return stored["replies"]


def verify(suite, raw_root):
    name, original_report = SUITES[suite]
    home = raw_root / suite
    folder = home / name
    cfg, attempt = read(folder / "case.json"), read(folder / "attempt.json")
    require(
        cfg["worker_image"] == attempt["worker_image"] == WORKER
        and cfg["server_image"] == attempt["server_image"] == CORE
        and cfg["gateway_image"] == GATEWAY
        and cfg["context_image"] == cfg["simulator_image"] == OPTIONAL_CONTEXT
        and attempt["ide_client_sha256"] == CLIENT
        and attempt["authoritative_native_status"] == "FINISHED"
        and cfg["source_sha256"] == attempt["snapshot_sha256"]
        and cfg["revision"] == attempt["snapshot_git"],
        "Frozen deployment, session or source identity differs",
    )
    identity = read(folder / "raw/native-runtime.json")
    build = read(folder / "native-build.json")
    require(
        identity["suite"] == suite
        and identity["collector_sha256"] == ORIGINAL_COLLECTOR
        and identity["build_manifest"] == build
        and identity["build_manifest_sha256"] == sha(folder / "native-build.json")
        and identity["output_directory_identity"] == attempt["directory_identity"]
        and identity["cwd"] == "/workspace/native-language-results"
        and identity["executable_path"] == "/opt/v08-native-home/bin/SPELL-Executor"
        and identity["executable_sha256"] == build["candidate_executor_sha256"]
        and identity["mapped_private_shared_libraries"]
        == [
            {
                "path": "/opt/v08-native-home/bin/libspell_executor313.so",
                "sha256": build["candidate_shared_runtime_sha256"],
            }
        ]
        and identity["oracle_inputs"]
        == {n: sha(home / "input" / n) for n in identity["oracle_inputs"]},
        "Deployed native oracle writer differs",
    )
    execution = attempt["execution_id"]
    receipts = authority(folder, execution, identity)
    failures = (
        read(folder / "expected-read-failures.json") if suite == "obsmore" else []
    )
    require(
        len(failures) == (2 if suite == "obsmore" else 0),
        "Original no-feed read failure count differs",
    )
    simulation = verify_simulation(folder, execution, [], timed_out_reads=failures)
    simulation["expected_read_timeout_events"] = len(failures)
    selection = read(home / "original-selection.json")["checks"]
    target = (
        "checks.json"
        if suite in {"obsmore", "limitprobe"}
        else original_report + "-results.json"
    )
    rows = read(folder / "raw" / target)
    rows = rows.get("checks", rows)
    require(rows.keys() == selection.keys(), "Selected native assertion set differs")
    summary = {
        "case": name,
        "execution_id": execution,
        "snapshot_git": cfg["revision"],
        "snapshot_sha256": cfg["source_sha256"],
        "results_sha256": sha(folder / "raw" / target),
        "identity_sha256": sha(folder / "raw/native-runtime.json"),
        "authority_sha256": sha(folder / "stored-authority.json"),
        "pid_namespace": identity["pid_namespace"],
        "native_result": "FINISHED",
        "assertions": len(rows),
        "assertions_passed": sum(row["passed"] is True for row in rows.values()),
        "simulation": simulation,
    }
    if suite == "limitprobe":
        denials = Counter()
        for line in (folder / "worker.log").read_text().splitlines():
            if line.startswith("{"):
                event = json.loads(line)
                if event.get("event") == "native-driver-denied":
                    denials[f"{event['status']} {event['path']}"] += 1
        for key, ref in selection.items():
            require(
                rows[key]["source"] == ref["source"]
                and rows[key]["passed"] is False
                and sha(home / "original-inputs" / Path(ref["source_path"]).name)
                == ref["source_sha256"],
                "Historical diagnostic input differs",
            )
        summary.update(
            failed_originals={
                k: {
                    "error": v["error"],
                    "cause": v["traceback"].splitlines()[-1],
                    "report": selection[k]["archived_report"],
                    "check": selection[k]["archived_check"],
                }
                for k, v in rows.items()
            },
            denied_driver_methods=dict(denials),
        )
        return summary, set()
    report_path = ROOT / "conformance/evidence" / (original_report + ".json")
    original = read(report_path)
    contract_path = "conformance/" + original_report + "_contracts.py"
    require(
        sha(ROOT / contract_path)
        == original["inputs"][contract_path]
        == identity["oracle_inputs"][Path(contract_path).name]
        and all(selection[k] == original["checks"][k] for k in rows),
        "Original report or native assertion program differs",
    )
    qualified = set()
    observed = (
        read(folder / "controller-prompts.json")
        if suite in {"commonfull", "uifull"}
        else {}
    )
    receipt_ids = set()
    for k, row in rows.items():
        old = selection[k]
        require(
            row["passed"] is True and old["passed"] is True,
            "Native assertion failed: " + k,
        )
        if suite == "obsmore":
            require(
                row["source"] == old["source"]
                and old["expected_prompts"]
                == row["expected_prompts"]
                == old["prompts"]
                == [],
                "Original telemetry source differs",
            )
        else:
            require(
                all(
                    row[key] == old[key] for key in ("dimension", "contracts", "oracle")
                ),
                "Original operator contract differs",
            )
            historical = (
                old["controller_prompts"]
                if suite == "commonfull"
                else old["controller_answers"]
            )
            reviews = observed.get(k, [])
            require(
                len(reviews) == len(historical),
                "Original operator prompt count differs",
            )
            for i, (live, old_prompt) in enumerate(zip(reviews, historical)):
                require(
                    live["state"] == "QUEUED"
                    and live["source_action"] == "ANSWER"
                    and live["prompt_id"] not in receipt_ids,
                    "Owner reply identity or queue state differs",
                )
                receipt_ids.add(live["prompt_id"])
                if suite == "commonfull":
                    exp = old_prompt["expected"]
                    require(
                        live["expected"] == row["expected_prompts"][i] == exp
                        and sorted(live["choices"]) == sorted(exp["choices"])
                        and exp["answer"] in live["choices"],
                        "COMMON operator choice or repair differs",
                    )
                else:
                    exp = row["expected"]["prompts"][i]
                    require(
                        live["text"] == exp["text"] == old_prompt["fields"]["Text"]
                        and live["choices"] == exp["choices"]
                        and live["expected"]["answer"]
                        == exp["answer"]
                        == old_prompt["answer"],
                        "UI prompt text or typed answer differs",
                    )
            if suite == "uifull" and not k.startswith("prompt-"):
                continue  # Display/Notify need the original independent MSG_WRITE/ITEM observations.
        qualified.add(k)
    require(
        {r["prompt_id"] for r in receipts} == receipt_ids
        and len(receipts) == len(receipt_ids)
        and all(
            r["execution_id"] == execution
            and r["owner"] == "alice"
            and r["action"] == "ANSWER"
            and r["state"] == "CONSUMED_UNPROVEN"
            for r in receipts
        ),
        "Stored transient owner reply binding differs",
    )
    summary.update(
        original_report=original_report + ".json",
        original_report_sha256=sha(report_path),
        requirements_eligible_checks=len(qualified),
        actual_owner_replies=len(receipt_ids),
        stored_reply_states=dict(Counter(r["state"] for r in receipts)),
    )
    return summary, qualified


def reconcile(raw_root):
    baseline = read(BASE)
    prior = {
        r["id"]
        for r in baseline["rows"]
        if r["status"] == "FRESH_INHERITED_DIMENSIONS_PASSED"
    }
    require(
        len(prior) == 253 and len(baseline["rows"]) == 763, "Retained baseline changed"
    )
    credited, sources, suites = set(prior), {}, {}
    for name, (_, original) in SUITES.items():
        summary, checks = verify(name, raw_root)
        suites[name] = summary
        for row in baseline["rows"]:
            rc = row["historical_oracles"]
            if (
                original
                and len(rc) == 4
                and all(
                    v["report"] == "conformance/evidence/" + original + ".json"
                    and v["check"] in checks
                    for v in rc.values()
                )
            ):
                credited.add(row["id"])
                if row["id"] not in prior:
                    sources[row["id"]] = {"suite": name, "oracles": rc}
    require(
        len({r["pid_namespace"] for r in suites.values()}) == len(suites),
        "Native writer namespace reused",
    )
    return {
        "schema": "openbexi.v08.additional-native-compatibility/1",
        "spell": SPELL,
        "ide": IDE,
        "worker": WORKER,
        "native_parent": "sha256:c2e3a540225ffec2404a086f62d3669391e1baf6378a9a620c0ecc3b2ecf3886",
        "core": CORE,
        "gateway": GATEWAY,
        "context_with_simulation": OPTIONAL_CONTEXT,
        "baseline_source": BASE.name,
        "baseline_sha256": sha(BASE),
        "baseline_fresh": len(prior),
        "inherited_requirements": 763,
        "new_direct_requirements": len(sources),
        "fresh_requirements_across_captures": len(credited),
        "outstanding": 763 - len(credited),
        "additional_rows": sources,
        "runs": suites,
        "reported_limitations": [
            "The private original owner-reply ledger retains CONSUMED_UNPROVEN. Native assertion values and the separate FINISHED result were independently observed.",
            "The UI run emitted 56 embedded verdicts. Only the 48 prompt assertions meet their independent controller oracle. Display and Notify need separate MSG_WRITE/ITEM capture.",
            "The four diagnostic cases share no direct row credit. They preserve independent evidence for limits, ranging, memory and scheduling.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = reconcile(args.raw_root)
    args.output.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(report["fresh_requirements_across_captures"], report["outstanding"])


if __name__ == "__main__":
    main()
