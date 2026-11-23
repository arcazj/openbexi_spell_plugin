"""Reconcile the inherited inventory and the stored deployed native language results."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/v0.8/evidence"
CURRENT = EVIDENCE / "qualification-20261122"
ADAPTER_SHA256 = "c59f7551abca31f105299241af24ac6d5084104e7f297526f5bc415ecbab8bd8"
SPELL_COMMIT = "c7292d39f6f40eb98d4edb5304f4a49a0dd50307"
WORKER_IMAGE = "sha256:de617ca4c3e0d2550bd639c201182f3f36ee21de6d7fd232e17fead8a47e47f3"
SERVICE_IMAGE = (
    "sha256:6189fc60d20bcfd14ae40f10010fcd2cc0c79a9ac70da3118c05c8e2c5dd6583"
)
sys.path.insert(0, str(ROOT / "conformance"))
sys.path.insert(0, str(ROOT / "src"))
import deployed_dta_cases as dta  # noqa: E402
import deployed_generic_cases as generic  # noqa: E402
import deployed_language_cases as extended  # noqa: E402

EXPECTED_RUNS = {
    "time": "timea",
    "python": "pythona",
    "data": "dataa",
    "files": "filesa",
    "common": "commona",
    "dta": "dtaa",
    "obs": "obsf",
    "cmd": "cmdb",
}
ARCHIVE_REPORT = {name: name + ".json" for name in EXPECTED_RUNS}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def archive_adapter():
    path = CURRENT / "compatibility-admitted-oracle.py"
    require(sha(path) == ADAPTER_SHA256, "Recovered oracle adapter differs")
    spec = importlib.util.spec_from_file_location(
        "archived_native_language_batch", path
    )
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    adapter.protected_inputs(ROOT)
    return adapter


def verify_run(raw_root, adapter, suite):
    name = suite["name"]
    folder = raw_root / name / EXPECTED_RUNS[name]
    attempt_path = folder / "attempt.json"
    if not attempt_path.is_file():
        return {"status": "MISSING"}, {}
    attempt = read(attempt_path)
    result_path = folder / "raw" / suite["result"]
    result = read(result_path) if result_path.is_file() else {}
    rows = result if name in generic.GROUPS else result.get("checks", {})
    record = {
        k: attempt.get(k)
        for k in (
            "case",
            "suite",
            "started",
            "finished",
            "execution_id",
            "snapshot_git",
            "snapshot_sha256",
            "worker_image",
            "server_image",
            "ide_version",
            "ide_client_sha256",
            "authoritative_native_status",
            "error",
            "collection_error",
        )
    }
    record["attempt_sha256"] = sha(attempt_path)
    record["observed_checks"] = len(rows)
    record["passing_checks"] = sum(r.get("passed") is True for r in rows.values())
    if attempt.get("passed") is not True:
        record["status"] = "FAILED_OR_INCOMPLETE"
        return record, rows
    identity_path = folder / "raw/native-runtime.json"
    build_path = folder / "native-build.json"
    identity = read(identity_path)
    build = read(build_path)
    if name in generic.GROUPS:
        require(
            attempt["worker_image"]
            == "sha256:deab534110c79036195aebe2cf30afb7f501bebe6dc6eac7fdc21c26c546e66b"
            and attempt["server_image"]
            == "sha256:6324fa788e5b2a28e3f89e8e499a13b711c2d7b3232db10ea6302ddb08e84e16"
            and read(folder / "case.json")["context_image"]
            == "sha256:da2607edf9eccfa915805c7b84054017b63616fc7222992b44ef2dd9d526b8e9",
            "GENERIC worker, service or optional Context image differs",
        )
    else:
        require(
            attempt["worker_image"] == WORKER_IMAGE
            and attempt["server_image"] == SERVICE_IMAGE,
            "Deployment bytes differ",
        )
    require(
        attempt["directory_identity"] == identity["output_directory_identity"],
        "Output mount differs",
    )
    require(
        attempt["identity_sha256"] == sha(identity_path)
        and attempt["output_sha256"] == sha(result_path)
        and attempt["build_sha256"] == sha(build_path),
        "Run artifact digest differs",
    )
    if name in extended.SUITES:
        verdict = extended.validate(ROOT, name, result, identity, build, ADAPTER_SHA256)
    elif name == "dta":
        verdict = dta.validate(ROOT, result, identity, build, ADAPTER_SHA256)
    elif name in generic.GROUPS:
        verdict = generic.validate(
            ROOT,
            name,
            result,
            identity,
            build,
            ADAPTER_SHA256,
            folder,
            attempt["execution_id"],
        )
        record["simulation"] = verdict["simulation"]
    else:
        verdict = adapter.validate_result(result, identity, build, ROOT, suite)
    audit = attempt["authority"]
    require(
        audit["spent"] == 1 and len(audit["members"]) == 1,
        "Admitted member count differs",
    )
    member = audit["members"][0]
    require(
        member["pid"] == identity["pid"]
        and member["executable_sha256"] == identity["executable_sha256"],
        "Recorded native member differs from the writer",
    )
    require(
        attempt["authoritative_native_status"] == "FINISHED"
        and audit["results"]
        == [{"execution_id": attempt["execution_id"], "native_status": "FINISHED"}],
        "Authoritative terminal result differs",
    )
    record.update(
        status="PASSED",
        output_sha256=sha(result_path),
        identity_sha256=sha(identity_path),
        build_sha256=sha(build_path),
        namespace=identity["pid_namespace"],
        start_ticks=identity["start_ticks"],
        executable_sha256=identity["executable_sha256"],
        shared_runtime_sha256=build["candidate_shared_runtime_sha256"],
        restrictions=verdict["not_original_spelling_qualification"],
    )
    return record, rows


def coverage_map(raw_root):
    matrix = read(EVIDENCE / "compatibility-matrix-20261027.json")
    inventory_path = ROOT / "conformance/inventory.json"
    coverage_path = ROOT / "conformance/coverage.json"
    require(
        sha(inventory_path) == matrix["inventory_sha256"]
        and sha(coverage_path) == matrix["coverage_sha256"],
        "Original inventory or coverage changed",
    )
    inventory = read(inventory_path)
    coverage = {r["id"]: r for r in read(coverage_path)["rows"]}
    require(
        len(inventory["rows"])
        == len(coverage)
        == len({r["id"] for r in inventory["rows"]})
        == 763,
        "Inherited inventory changed",
    )
    reports = {name: sha(ROOT / name) for name in matrix["historical_reports"]}
    require(
        all(
            reports[n] == binding["report_sha256"]
            for n, binding in matrix["historical_reports"].items()
        ),
        "Historical report bytes differ",
    )
    bindings = []
    for expected in matrix["source_bindings"]:
        path = ROOT / expected["path"]
        actual = sha(path) if path.is_file() else None
        bindings.append(
            {
                "path": expected["path"],
                "expected": expected["expected_sha256"],
                "actual": actual,
                "status": "MATCH"
                if actual == expected["expected_sha256"]
                else "SOURCE_DRIFT"
                if actual
                else "MISSING",
            }
        )
    adapter = archive_adapter()
    suites = {}
    mapped = {}
    for spec in (
        *adapter.SPECS,
        *({"name": n, "result": n + "-results.json"} for n in extended.SUITES),
        {"name": "dta", "result": "dta-results.json"},
        *({"name": n, "result": "checks.json"} for n in generic.GROUPS),
    ):
        suite = spec["name"]
        verdict, values = verify_run(raw_root, adapter, spec)
        suites[suite] = verdict
        if suite in extended.SUITES:
            checks = {
                k: v["contracts"] for k, v in extended.mapping(ROOT, suite).items()
            }
        elif suite == "dta":
            checks = {k: v["contracts"] for k, v in dta.mapping(ROOT).items()}
        elif suite in generic.GROUPS:
            checks = {
                k: v["contracts"] for k, v in generic.mapping(ROOT, suite).items()
            }
        else:
            checks = adapter.check_mapping(ROOT, spec)
        for check, ids in checks.items():
            dimension = check.rsplit(":", 1)[1]
            for identifier in ids:
                entry = mapped.setdefault(
                    identifier, {"suite": suite, "check_names": {}, "observed_pass": {}}
                )
                require(entry["suite"] == suite, "Suite membership overlaps")
                original = coverage[identifier]["evidence"][dimension]
                if dimension not in entry["check_names"] or (
                    original["report"]
                    == "conformance/evidence/" + ARCHIVE_REPORT[suite]
                    and original["check"] == check
                ):
                    entry["check_names"][dimension] = check
                    entry["observed_pass"][dimension] = values.get(check, {}).get(
                        "passed"
                    )
    require(len(mapped) == 272, "Archived admitted suite mapping differs")
    rows = []
    for requirement in inventory["rows"]:
        identifier = requirement["id"]
        old = coverage[identifier]
        historical = old["evidence"]
        require(
            old["package"] == requirement["package"]
            and set(historical) == set(adapter.DIMENSIONS),
            "Historical row identity or dimensions differ",
        )
        require(
            all(reports[r["report"]] == r["sha256"] for r in historical.values()),
            "Historical row reference differs",
        )
        row = dict(
            id=identifier,
            package=requirement["package"],
            manual_pages=requirement["pages"],
            historical_oracles={
                d: {"report": v["report"], "check": v["check"]}
                for d, v in historical.items()
            },
        )
        live = mapped.get(identifier)
        if not live:
            status = "NO_CURRENT_DEPLOYED_CHECK"
        else:
            row["current_suite"] = live["suite"]
            row["current_dimensional_checks"] = live["check_names"]
            row["observed_dimensions"] = live["observed_pass"]
            verdict = suites[live["suite"]]
            exact = set(live["check_names"]) == set(adapter.DIMENSIONS) and all(
                historical[d]["report"]
                == "conformance/evidence/" + ARCHIVE_REPORT[live["suite"]]
                and historical[d]["check"] == check
                and live["observed_pass"][d] is True
                for d, check in live["check_names"].items()
            )
            restriction = verdict.get("restrictions", {}).get(identifier)
            if verdict["status"] != "PASSED":
                status = "SUITE_FAILED_OR_INCOMPLETE"
            elif restriction:
                status = (
                    "MIGRATION_ONLY"
                    if identifier in adapter.LEGACY
                    else "BROADER_SECTION_OPEN"
                )
                row["restriction"] = restriction
            elif not exact:
                status = "ADDITIONAL_INHERITED_ORACLE_REQUIRED"
            else:
                status = "FRESH_INHERITED_DIMENSIONS_PASSED"
        row["status"] = status
        rows.append(row)
    namespaces = [v["namespace"] for v in suites.values() if v["status"] == "PASSED"]
    require(len(namespaces) == len(set(namespaces)), "Reused native PID namespace")
    recovery_path = CURRENT / "compatibility-capture-recovery.json"
    recovery = read(recovery_path)
    for key, record in recovery["recovered"].items():
        path = raw_root / recovery["copied_directory"] / key
        require(
            path.stat().st_size == record["bytes"] and sha(path) == key,
            "Archived capture differs",
        )
    original = read(EVIDENCE / "compatibility-archive/v06-recovery.json")
    intervening = read(EVIDENCE / "qualification-dev81-local-20261028.json")[
        "compatibility"
    ]
    remaining = set(original["missing_referenced_hashes"]) - {
        v["sha256"] for v in intervening["recovered_byte_bindings"]
    }
    require(
        remaining == set(recovery["recovered"]) and len(remaining) == 46,
        "Recovered identities differ",
    )
    counts = dict(Counter(r["status"] for r in rows))
    return {
        "schema": "openbexi.v08.deployed-compatibility-inventory/1",
        "spell_product_commit": SPELL_COMMIT,
        "generic_product_base_commit": "99686362f93fa1bbbadd70e7b74d52ed3b5da469",
        "generic_assigned_native_session_source_sha256": "90bbfa4c2e3ee135a5b0afe94d71246427c88bbd41b69231ea000c5c06f829a6",
        "generic_profile_preimage_sha256": "5a7742dc8b08d56a84616a81ae1dce7cbb23e0004e46a9e0e3dea216e8e2d82b",
        "native_base": "sha256:b971df8f0ea0fc1fa40ba04adbd735534d797463310d574b987c02c2070681a0",
        "ide_commit": "3ec9d4d998afa77f8590cd1e48c10b1a38561dca",
        "run_storage": raw_root.as_posix(),
        "archived_adapter_source": "9080cde64b87a43758255d94fd43a9c7c602da4a:scripts/v08_native_language_batch.py",
        "archived_adapter_sha256": ADAPTER_SHA256,
        "extended_dispatch_source_sha256": sha(
            ROOT / "conformance/deployed_language_cases.py"
        ),
        "extended_oracle_sources": extended.SUITES,
        "frozen_oracle_inputs": adapter.PREIMAGES,
        "inventory_sha256": sha(inventory_path),
        "coverage_sha256": sha(coverage_path),
        "manual_sha256": sha(ROOT / inventory["manual"]),
        "manual": inventory["manual"],
        "upstream_sha256": sha(ROOT / inventory["archive"]),
        "upstream": inventory["archive"],
        "historical_reports": reports,
        "historical_binding_counts": dict(Counter(x["status"] for x in bindings)),
        "historical_bindings_with_drift": [
            v for v in bindings if v["status"] != "MATCH"
        ],
        "historical_capture_recovery": {
            "verified_v06": 245,
            "intervening": 11,
            "verified_here": 46,
            "remaining": 0,
            "receipt": recovery_path.name,
            "sha256": sha(recovery_path),
        },
        "deployed_suites": suites,
        "mapped_suite_ids": len(mapped),
        "scope": "Direct credit requires four exact historical dimensional oracles with passing results on an admitted native process. The GENERIC tests used the deployed three-second profile, private synthetic TCP/HTTP services and independently decoded real packets. Legacy migration, broad Python sections and composed or concurrent DATA carry separate qualifications.",
        "total_inherited": len(rows),
        "status_counts": counts,
        "all763_fresh": counts.get("FRESH_INHERITED_DIMENSIONS_PASSED", 0) == 763,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = coverage_map(args.raw_root)
    args.output.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report["status_counts"]))


if __name__ == "__main__":
    main()
