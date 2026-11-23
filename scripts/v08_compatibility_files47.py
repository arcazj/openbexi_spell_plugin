"""Verify the complete original FILES chapter, its real owner replies and its two additional IDs."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from v08_compatibility_final_rollup import (
    DIMENSIONS,
    EVIDENCE,
    NEW,
    ROOT,
    capture,
    native,
    products,
    read,
    require,
    sha,
    totals,
)


def verify():
    rows, earlier, failed, _, _ = totals()
    prior_path = EVIDENCE / "compatibility-330/compatibility-final-rollup.json"
    previous = read(prior_path)
    earlier |= previous["47e_python"]["new_parent_ids"].keys()
    previous_47 = (
        set(previous["47e_python"]["existing_supported_ids"])
        | previous["47e_python"]["new_parent_ids"].keys()
        | set(previous["47e_dictionary_load"]["repeated_ids"])
    )
    require(
        len(earlier) == 330 and len(previous_47) == 119, "Previous source scope differs"
    )
    reference = "conformance/evidence/files.json"
    original = read(ROOT / reference)
    inventory = read(EVIDENCE / "compatibility-native-inventory.json")
    require(
        inventory["historical_reports"][reference] == sha(ROOT / reference),
        "Historical FILES report changed",
    )
    with (
        capture("compatibility-47e-continuity") as shared,
        capture("compatibility-47e-files") as archive,
    ):
        subjects, image_bytes, ide = products(shared)
        suite = archive / "fileswhole"
        folder = suite / "files47a"
        live, identity = native(
            folder, subjects["47e0"], image_bytes, "47e0", prompt_count=2
        )
        result_file = folder / "raw/data-files-results.json"
        observed = read(result_file)["checks"]
        owner = read(folder / "controller-prompts.json")
        authority = read(folder / "stored-authority.json")
        disk = read(folder / "stored-files.json")
        code = sha(suite / "input/files_contracts.py")
        require(
            identity["suite"] == "fileswhole"
            and identity["oracle_inputs"] == {"files_contracts.py": code}
            and code == original["inputs"]["conformance/files_contracts.py"]
            and sha(archive / "conformance/run_data_files.py")
            == original["inputs"]["conformance/run_data_files.py"]
            and sha(result_file) == live["output_sha256"]
            and set(observed) == set(original["checks"])
            and len(observed) == live["passing_checks"] == 36,
            "Frozen source, external controller, embedded checks or persisted run differs",
        )
        require(
            set(owner) == {"error-policy:positive", "error-policy:recovery"},
            "Original owner prompt set differs",
        )
        repaired = b"controller repaired\n"
        repair_hash = hashlib.sha256(repaired).hexdigest()
        receipts = []
        for key, original_row in original["checks"].items():
            row = observed[key]
            require(
                row["passed"] is original_row["passed"] is True
                and all(
                    row[field] == original_row[field]
                    for field in ("contracts", "dimension", "oracle")
                ),
                "Original assertion differs: " + key,
            )
            expected, actual, historically = (
                row["expected_prompts"],
                owner.get(key, []),
                original_row["controller_prompts"],
            )
            require(
                len(expected) == len(actual) == len(historically),
                "Prompt count differs: " + key,
            )
            for wanted, received, historical in zip(expected, actual, historically):
                target = wanted["repair"]
                original_target = re.search(
                    r"files-owned-[0-9a-f]{32}/repair", historical["text"]
                )
                require(
                    original_target
                    and re.fullmatch(r"files-owned-[0-9a-f]{32}/repair", target)
                    and received["text"]
                    == historical["text"].replace(original_target.group(), target)
                    and received["choices"]
                    == wanted["choices"]
                    == historical["choices"]
                    == ["REPEAT", "SKIP"]
                    and received["expected"] == wanted
                    and wanted["answer"] == "REPEAT"
                    and received["repair_receipt"]
                    == {"sha256": repair_hash, "bytes": len(repaired)}
                    and bytes.fromhex(disk[target]["hex"]) == repaired
                    and disk[target]["sha256"] == repair_hash
                    and received["source_action"] == "ANSWER"
                    and received["state"] == "QUEUED",
                    "Independent prompt, choice order, content or file repair differs",
                )
                receipts.append(
                    {
                        "original_check": key,
                        "prompt_id": received["prompt_id"],
                        "choices": received["choices"],
                        "answer": wanted["answer"],
                        "owned_relative_file": target,
                        "repair_sha256": repair_hash,
                    }
                )
        for receipt, reply in zip(receipts, authority["replies"]):
            require(
                reply["execution_id"] == live["execution_id"]
                and reply["prompt_id"] == receipt["prompt_id"]
                and reply["owner"] == "alice"
                and reply["action"] == "ANSWER"
                and reply["state"] == "CONSUMED_UNPROVEN",
                "Stored owner response differs",
            )
            receipt["stored_state"] = reply["state"]
        for dim in DIMENSIONS:
            components = [
                v
                for k, v in observed.items()
                if v["dimension"] == dim and not k.startswith("file-manipulation:")
            ]
            require(
                len(components) == 8
                and all(v["passed"] for v in components)
                and observed["file-manipulation:" + dim]["passed"],
                "Whole chapter dependency missing",
            )
        qualified = {
            identifier: row["historical_oracles"]
            for identifier, row in rows.items()
            if set(row["historical_oracles"]) == set(DIMENSIONS)
            and all(
                ref["report"] == reference
                and identifier in observed[ref["check"]]["contracts"]
                for ref in row["historical_oracles"].values()
            )
        }
        added = qualified.keys() - earlier
        require(
            len(qualified) == 40
            and not (qualified.keys() & (failed | previous_47))
            and added
            == {"CMP-LRM244-SECTION-4-17-115", "CMP-LRM244-SECTION-4-17-8-123"},
            "New or repeated inherited IDs differ",
        )
        remaining = set(rows) - earlier - failed - added
        return {
            "schema": "openbexi.v08.compatibility-47e-files/1",
            "spell": NEW,
            "ide": ide,
            "worker": subjects["47e0"]["worker"],
            "execution": live["execution_id"],
            "started": live["started"],
            "finished": live["finished"],
            "native_status": live["authoritative_native_status"],
            "pid_namespace": identity["pid_namespace"],
            "original_report_sha256": sha(ROOT / reference),
            "executed_original_sha256": code,
            "original_controller_sha256": original["inputs"][
                "conformance/run_data_files.py"
            ],
            "snapshot_sha256": live["snapshot_sha256"],
            "native_result_sha256": sha(result_file),
            "authority_sha256": sha(folder / "stored-authority.json"),
            "read_only_filesystem_capture_sha256": sha(folder / "stored-files.json"),
            "read_only_filesystem_entries": len(disk),
            "regular_files": sum(not item["directory"] for item in disk.values()),
            "embedded_pass": len(observed),
            "real_prompts": receipts,
            "fresh_47e_files_requirements": len(qualified),
            "new_direct_ids": {k: qualified[k] for k in sorted(added)},
            "previously_covered_ids": sorted(qualified.keys() & earlier),
            "previous_47e_direct": len(previous_47),
            "47e_direct_distinct": len(previous_47 | qualified.keys()),
            "across_tested_subjects": {
                "pass": len(earlier | added),
                "fail": len(failed),
                "incomplete": len(remaining),
            },
            "prior_330_report_sha256": sha(prior_path),
            "capture_archive_sha256": read(
                EVIDENCE / "compatibility-47e-files-captures.json"
            )["sha256"],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    result = verify()
    parser.parse_args().output.write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(result["across_tested_subjects"], result["47e_direct_distinct"])
