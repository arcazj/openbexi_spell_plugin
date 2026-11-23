"""Reconcile the native qualification evidence into one verdict per inherited requirement."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def summarize(directory, final_subject=False):
    names = (
        "compatibility-native-inventory.json",
        "compatibility-additional-native.json",
        "compatibility-user-dictionary.json",
        "compatibility-negative-rows.json",
    )
    inputs = {name: (directory / name).read_bytes() for name in names}
    base, extra, dictionary, negative = (json.loads(blob) for blob in inputs.values())
    rows = {}
    for original in base["rows"]:
        key = original["id"]
        if key in rows:
            raise ValueError(f"Duplicate inherited requirement {key}")
        passed = original["status"] == "FRESH_INHERITED_DIMENSIONS_PASSED"
        rows[key] = dict(
            id=key,
            package=original["package"],
            manual_pages=original["manual_pages"],
            verdict="PASS" if passed else "NOT RUN",
            evidence=names[0],
            detail=original["status"],
        )
    for name, group in ((names[1], extra), (names[2], dictionary)):
        if len(group["additional_rows"]) != group["new_direct_requirements"]:
            raise ValueError(f"Inconsistent direct coverage in {name}")
        for key in group["additional_rows"]:
            if rows[key]["verdict"] != "NOT RUN":
                raise ValueError(f"Conflicting direct qualification for {key}")
            rows[key].update(
                verdict="PASS",
                evidence=name,
                detail="All four inherited dimensions passed",
            )
    failed = set()
    for case, finding in negative["rows"].items():
        for requirement in finding["affected_inherited_ids"]:
            key = requirement["id"]
            if rows[key]["verdict"] == "PASS":
                raise ValueError(f"Conflicting positive evidence for {key}")
            failed.add(key)
            rows[key].update(
                verdict="FAIL",
                evidence=names[3],
                detail=case + " / " + requirement["dimension"],
            )
    counts = dict(Counter(row["verdict"] for row in rows.values()))
    if (
        len(rows) != base["total_inherited"]
        or len(failed) != negative["affected_unique_ids"]
        or counts["PASS"] != dictionary["fresh_requirements_across_captures"]
    ):
        raise ValueError("Native requirement totals disagree")
    if final_subject:
        name = "compatibility-final-rollup.json"
        inputs[name] = (directory / name).read_bytes()
        final = json.loads(inputs[name])
        language = final["47e_python"]
        files = final["47e_files"]
        groups = (
            (
                language["new_parent_ids"],
                "All original child oracles in four dimensions passed on the frozen worker",
            ),
            (
                files["new_direct_ids"],
                "The original FILES cases, independent file repairs and ordered owner replies passed on the frozen worker",
            ),
        )
        fresh = set()
        for members, detail in groups:
            for key, dimensions in members.items():
                if rows[key]["verdict"] != "NOT RUN" or set(dimensions) != {
                    "positive",
                    "boundary",
                    "failure",
                    "recovery",
                }:
                    raise ValueError(f"Unexpected requirement coverage for {key}")
                rows[key].update(verdict="PASS", evidence=name, detail=detail)
                fresh.add(key)
        repeated = (
            set(language["existing_supported_ids"])
            | set(final["47e_dictionary_load"]["repeated_ids"])
            | set(files["existing_supported_ids"])
        )
        direct = fresh | repeated
        if len(direct) != final["47e_direct_distinct"] or not all(
            rows[key]["verdict"] == "PASS" for key in direct
        ):
            raise ValueError("Frozen worker coverage does not reconcile")
        for key in direct:
            rows[key]["final_subject_evidence"] = name
        counts = dict(Counter(row["verdict"] for row in rows.values()))
        if final["across_tested_subjects"] != {
            "pass": counts["PASS"],
            "fail": counts["FAIL"],
            "incomplete": counts["NOT RUN"],
        }:
            raise ValueError("Final native requirement totals disagree")
    return dict(
        scope="Source-scoped union of original native runs. Each row cites its tested build and raw capture through the named evidence. NOT RUN indicates that one or more mandatory dimensions lack a complete native verdict.",
        status_counts=counts,
        total=len(rows),
        inputs_sha256={n: sha256(b).hexdigest() for n, b in inputs.items()},
        rows=[rows[key] for key in sorted(rows)],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--final-subject",
        action="store_true",
        help="Include native cases on the frozen delivery worker",
    )
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(summarize(args.evidence_directory, args.final_subject), indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
