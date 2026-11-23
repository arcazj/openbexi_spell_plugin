"""Validate the original non-interactive DTA groups on an admitted native root."""

import hashlib
import json


DTA_SHA256 = "48ab24810e4281e3b17f0ea8402c1a969d94054fdffea633c1d720f28287a914"
GROUPS = ("mapping",)
DIMENSIONS = ("positive", "boundary", "failure", "recovery")


def mapping(root):
    report = json.loads((root / "conformance/evidence/dta.json").read_bytes())
    if (
        hashlib.sha256((root / "conformance/dta_contracts.py").read_bytes()).hexdigest()
        != DTA_SHA256
        or report["inputs"]["conformance/dta_contracts.py"] != DTA_SHA256
    ):
        raise ValueError("Historical DTA oracle source differs")
    rows = {
        key + ":" + dim: report["checks"][key + ":" + dim]
        for key in GROUPS
        for dim in DIMENSIONS
    }
    if any(
        r["controller_answers"] or r["items"] or r["passed"] is not True
        for r in rows.values()
    ):
        raise ValueError(
            "DTA group requires independently observed operator answers or item values"
        )
    return rows


def validate(root, raw, identity, build, collector_sha):
    expected = mapping(root)
    if set(expected) != set(raw["checks"]):
        raise ValueError("DTA assertion set differs")
    for key, old in expected.items():
        row = raw["checks"][key]
        if (
            row.get("passed") is not True
            or any(
                row[field] != old[field]
                for field in ("dimension", "contracts", "oracle")
            )
            or row["expected"]["prompts"]
            or row["expected"]["items"]
            or row["expected"]["rejections"] != old["rejections"]
        ):
            raise ValueError(
                "Native DTA value, rejection, or original assertion differs: " + key
            )
    home = "/opt/v08-native-home/bin/"
    if (
        identity["suite"] != "dta"
        or identity["executable_path"] != home + "SPELL-Executor"
        or identity["executable_sha256"] != build["candidate_executor_sha256"]
        or identity["mapped_private_shared_libraries"]
        != [
            dict(
                path=home + "libspell_executor313.so",
                sha256=build["candidate_shared_runtime_sha256"],
            )
        ]
        or identity["build_manifest"] != build
        or identity["build_manifest_sha256"]
        != hashlib.sha256((json.dumps(build, indent=2) + "\n").encode()).hexdigest()
        or identity["oracle_inputs"] != {"dta_contracts.py": DTA_SHA256}
        or identity["collector_sha256"] != collector_sha
        or identity["start_ticks"] <= 0
        or identity["pid"] <= 0
        or identity["cwd"] != "/workspace/native-language-results"
    ):
        raise ValueError("Native DTA writer or source identity differs")
    ids = sorted({i for r in expected.values() for i in r["contracts"]})
    return {
        "passed": True,
        "suite": "dta",
        "dimensional_checks": len(expected),
        "mapped_requirement_ids": ids,
        "distinct_mapped_requirements": len(ids),
        "not_original_spelling_qualification": {},
    }
