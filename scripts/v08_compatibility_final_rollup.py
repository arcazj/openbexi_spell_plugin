"""Reconcile the original native evidence and every verified 47e compatibility suite."""

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import zipfile

from v08_additional_native_compatibility import (
    BASE,
    CLIENT,
    IDE,
    ORIGINAL_COLLECTOR,
    ROOT,
    SPELL,
    authority,
    read,
    require,
    sha,
)
from v08_dictionary_compatibility import verify as verify_original_dictionary
from check import supported_check

EVIDENCE = BASE.parent
NEW = "47e0cb376dac1e49e1f6745318c0eb3e43b2ec4d"
DIMENSIONS = ("positive", "boundary", "failure", "recovery")
ELF = {
    "SPELL-Listener": "listener",
    "SPELL-Context": "context",
    "SPELL-Executor": "executor",
    "spell-host-ipc": "bridge",
    "libspell_executor313.so": "shared_runtime",
}


@contextmanager
def capture(stem):
    manifest = read(EVIDENCE / (stem + "-captures.json"))
    archive = EVIDENCE / manifest["archive"]
    require(sha(archive) == manifest["sha256"], "Capture archive differs")
    with zipfile.ZipFile(archive) as files:
        require(
            set(files.namelist()) == set(manifest["files"]), "Capture members differ"
        )
        for name, record in manifest["files"].items():
            data = files.read(name)
            require(
                len(data) == record["bytes"]
                and hashlib.sha256(data).hexdigest() == record["sha256"],
                name,
            )
        yield zipfile.Path(files)


def totals():
    base, more, dictionaries, negative = [
        read(EVIDENCE / (name + ".json"))
        for name in (
            "compatibility-native-inventory",
            "compatibility-additional-native",
            "compatibility-user-dictionary",
            "compatibility-negative-rows",
        )
    ]
    rows = {row["id"]: row for row in base["rows"]}
    first = {
        k for k, v in rows.items() if v["status"] == "FRESH_INHERITED_DIMENSIONS_PASSED"
    }
    second, third = set(more["additional_rows"]), set(dictionaries["additional_rows"])
    passed = first | second | third
    failed = {
        item["id"]
        for case in negative["rows"].values()
        for item in case["affected_inherited_ids"]
    }
    require(
        tuple(map(len, (rows, first, second, third, passed, failed)))
        == (763, 253, 59, 6, 318, 27)
        and not passed & failed
        and (passed | failed) <= rows.keys(),
        "The frozen qualification sources disagree",
    )
    details = {
        "baseline_embedded_passes": {
            k: v["passing_checks"] for k, v in base["deployed_suites"].items()
        },
        "655f_additional": {
            k: {
                key: v[key]
                for key in (
                    "assertions",
                    "assertions_passed",
                    "requirements_eligible_checks",
                )
            }
            for k, v in more["runs"].items()
            if k != "limitprobe"
        },
        "655f_dictionary_originals": len(dictionaries["cases"]),
        "earlier_passes_by_stage": [len(first), len(second), len(third)],
        "earlier_pass": len(passed),
        "known_fail": len(failed),
        "earlier_incomplete": len(rows) - len(passed) - len(failed),
        "observed_failed_dependencies_by_case": {
            k: v["affected_count"] for k, v in negative["rows"].items()
        },
    }
    return rows, passed, failed, dictionaries, details


def products(archive):
    workers, subjects = {}, {}
    image_bytes = read(archive / "image-byte-comparison.json")
    for label, expected in (("655f", SPELL), ("47e0", NEW)):
        root = archive / "products" / label
        worker, build, packages = (
            read(root / n) for n in ("worker.json", "optimized.json", "packages.json")
        )
        require(
            build["source_commit"] == packages["commit"] == expected
            and build["profile"] == "optimized"
            and build["passed"] is True,
            "Product build provenance differs",
        )
        for name, value in worker["inputs_sha256"].items():
            if name.endswith(".whl"):
                require(packages["files"][name] == value, "Canonical package differs")
            else:
                require(
                    image_bytes["/v08/" + Path(name).name][label] == value,
                    "Installed module differs",
                )
        base = worker["native_base"]
        if label == "47e0":
            update = read(root / "runtime-update.json")
            require(
                update["passed"]
                and update["image"] == base
                and update["input_image"] == build["image"],
                "Patched runtime provenance differs",
            )
        else:
            require(base == build["image"], "Original runtime provenance differs")
        roles = {role: read(root / (role + ".json")) for role in ("core", "gateway")}
        require(
            all(record["passed"] for record in roles.values()),
            "Service receipt missing",
        )
        workers[label] = worker["worker_image"]
        subjects[label] = {
            "spell": expected,
            "source_tree": build["source_tree"],
            "optimized": build["image"],
            "runtime_parent": base,
            "worker": worker["worker_image"],
            "core": roles["core"]["image"],
            "gateway": roles["gateway"]["image"],
            "installed_wheels": {
                n: v for n, v in worker["inputs_sha256"].items() if n.endswith(".whl")
            },
        }
    require(workers["655f"] != workers["47e0"], "Independent workers required")
    ide = read(archive / "products/ide-packages.json")
    require(ide["commit"] == IDE, "Canonical IDE source differs")
    return (
        subjects,
        image_bytes,
        {
            "commit": IDE,
            "wheel": ide["files"]["openbexi_ide-1.2.2-py3-none-any.whl"],
            "installed_client": CLIENT,
        },
    )


def native(folder, subject, image_bytes, label, prompt_count=0):
    live, config, result, build = (
        read(folder / n)
        for n in (
            "attempt.json",
            "case.json",
            "raw/native-runtime.json",
            "native-build.json",
        )
    )
    require(
        live["passed"] is True
        and live["authoritative_native_status"] == "FINISHED"
        and live["ide_client_sha256"] == CLIENT
        and live["worker_image"] == config["worker_image"] == subject["worker"]
        and live["server_image"] == config["server_image"] == subject["core"]
        and config["gateway_image"] == subject["gateway"]
        and config["driver_binding"] == "context-audit"
        and config["source_sha256"] == live["snapshot_sha256"],
        "Native product identity or admitted result differs",
    )
    require(
        result["collector_sha256"] == ORIGINAL_COLLECTOR
        and result["build_manifest"] == build
        and result["build_manifest_sha256"] == sha(folder / "native-build.json")
        and result["executable_path"] == "/opt/v08-native-home/bin/SPELL-Executor"
        and result["executable_sha256"] == build["candidate_executor_sha256"]
        and result["mapped_private_shared_libraries"]
        == [
            {
                "path": "/opt/v08-native-home/bin/libspell_executor313.so",
                "sha256": build["candidate_shared_runtime_sha256"],
            }
        ]
        and result["output_directory_identity"] == live["directory_identity"]
        and len(authority(folder, live["execution_id"], result)) == prompt_count,
        "Independent native identity or authority differs",
    )
    for name, role in ELF.items():
        values = image_bytes["/opt/v08-native-home/bin/" + name]
        require(
            values["match"] and values[label] == build["candidate_" + role + "_sha256"],
            name,
        )
    return live, result


def run():
    rows, earlier, failed, dictionaries, details = totals()
    with ExitStack() as stack:
        old, new, language = (
            stack.enter_context(capture(n))
            for n in (
                "compatibility-dictionary",
                "compatibility-47e-continuity",
                "compatibility-47e-python",
            )
        )
        subjects, image_bytes, ide = products(new)
        source = read(new / "products/checkout-comparison.json")
        for path in (
            "conformance/check.py",
            "conformance/user_database_cases.py",
            "conformance/user_database_controller.py",
        ):
            require(
                source[path]["match"] and sha(ROOT / path) == source[path]["47e0"], path
            )
        require(
            verify_original_dictionary(old) == dictionaries,
            "The original 655f dictionary evidence differs",
        )
        namespaces, repeats = set(), {}
        for dim in DIMENSIONS:
            name = "dictload" + dim
            case = dictionaries["cases"]["load:" + dim]
            before, after = (
                old / name / ("dbload" + dim[0]),
                new / name / ("db47load" + dim[0]),
            )
            a, previous_identity = native(before, subjects["655f"], image_bytes, "655f")
            b, identity = native(after, subjects["47e0"], image_bytes, "47e0")
            for filename in (
                "original_case.py",
                "main.py",
                "v08_native_language_batch.py",
            ):
                require(
                    sha(old / name / "input" / filename)
                    == sha(new / name / "input" / filename),
                    filename,
                )
            result = "raw/dictionary-results.json"
            original = sha(new / name / "input/original_case.py")
            require(
                sha(before / result)
                == sha(after / result)
                == case["native_result_sha256"]
                and read(after / result)["passed"]
                and original == case["source_sha256"]
                and identity["oracle_inputs"] == {"original_case.py": original}
                and a["snapshot_sha256"]
                == b["snapshot_sha256"]
                == case["snapshot_sha256"]
                and a["execution_id"] == case["execution_id"]
                and b["execution_id"] != a["execution_id"],
                "Original procedure bytes, full observed output or snapshot differs",
            )
            namespaces.update(
                (previous_identity["pid_namespace"], identity["pid_namespace"])
            )
            repeats[dim] = {
                "snapshot_sha256": b["snapshot_sha256"],
                "original_sha256": original,
                "result_sha256": sha(after / result),
                "655f_execution": a["execution_id"],
                "47e0_execution": b["execution_id"],
                "resulting_file_sha256": read(after / result)["file_sha256"],
                "stored_authority_sha256": sha(after / "stored-authority.json"),
            }
        require(len(namespaces) == 8, "Cold dictionary process namespace reused")
        selected = {
            identifier
            for identifier, refs in dictionaries["additional_rows"].items()
            if all(v["check"] == "load:" + d for d, v in refs.items())
        }
        require(len(selected) == 2, "Expected two regular-file dictionary load IDs")
        folder = language / "python/py47dep"
        a, identity = native(folder, subjects["47e0"], image_bytes, "47e0")
        observed = read(folder / "raw/python-results.json")
        archived = read(ROOT / "conformance/evidence/python.json")
        require(
            sha(ROOT / "conformance/evidence/python.json")
            == source["conformance/evidence/python.json"]["47e0"]
            and identity["pid_namespace"] not in namespaces
            and len(observed["checks"]) == 488
            and observed["checks"] == archived["checks"]
            and all(c["passed"] for c in observed["checks"].values()),
            "Original 488 dimensional contracts or native process differs",
        )
        for file in ("python_contracts.py", "python_fixture.py"):
            digest = sha(language / "python/input" / file)
            require(
                identity["oracle_inputs"][file]
                == digest
                == source["conformance/" + file]["47e0"],
                file,
            )
        parents, leaves, used = {}, set(), set()
        for identifier, row in rows.items():
            refs = row["historical_oracles"]
            if row["package"] != "PY" or any(
                ref["report"] != "conformance/evidence/python.json"
                for ref in refs.values()
            ):
                continue
            if not all(
                supported_check(observed, ref["check"], d)
                and supported_check(archived, ref["check"], d)
                for d, ref in refs.items()
            ):
                continue
            if identifier in earlier:
                leaves.add(identifier)
                continue
            require(
                row["status"] == "BROADER_SECTION_OPEN"
                and identifier not in failed
                and set(refs) == set(DIMENSIONS),
                "Unexpected new row classification",
            )
            deps = {
                d: observed["checks"][ref["check"]]["dependencies"]
                for d, ref in refs.items()
            }
            require(
                all(
                    child.rsplit(":", 1)[0] in earlier
                    for names in deps.values()
                    for child in names
                ),
                "Parent requires an uncovered child",
            )
            used.update(child for names in deps.values() for child in names)
            parents[identifier] = deps
        require(
            (len(parents), len(used), len(leaves)) == (12, 372, 105),
            "Python qualification coverage changed",
        )
        areas = Counter(
            row["package"]
            for k, row in rows.items()
            if k not in earlier | failed | parents.keys()
        )
        output = {
            "schema": "openbexi.v08.native-compatibility-frozen-and-47e/1",
            "inherited": len(rows),
            "frozen_318": details,
            "across_tested_subjects": {
                "pass": len(earlier) + len(parents),
                "fail": len(failed),
                "incomplete": sum(areas.values()),
            },
            "incomplete_after_47e_by_inventory_package": dict(sorted(areas.items())),
            "47e_direct_distinct": len(parents) + len(leaves | selected),
            "ide": ide,
            "compared_spell_products": subjects,
            "checkout_sha256": source,
            "installed_worker_bytes": image_bytes,
            "47e_dictionary_load": {
                "fresh_runs": 4,
                "additional_ids": 0,
                "repeated_ids": sorted(selected),
                "cases": repeats,
            },
            "47e_python": {
                "execution": a["execution_id"],
                "native_status": a["authoritative_native_status"],
                "snapshot": a["snapshot_sha256"],
                "raw_sha256": sha(folder / "raw/python-results.json"),
                "stored_authority_sha256": sha(folder / "stored-authority.json"),
                "original_sha256": sha(ROOT / "conformance/evidence/python.json"),
                "whole_check_maps_equal": True,
                "embedded_pass": 488,
                "existing_supported_ids": sorted(leaves),
                "new_parent_ids": parents,
                "distinct_child_dimensions": len(used),
                "closure_rule": "Each parent and each declared descendant passes both versions of the original check contract in its exact dimension. Migration-only leaves and mixed-report parents remain open.",
            },
            "capture_archives": {},
        }
        for name in (
            "compatibility-native",
            "compatibility-additional",
            "compatibility-dictionary",
            "compatibility-47e-continuity",
            "compatibility-47e-python",
        ):
            manifest = read(EVIDENCE / (name + "-captures.json"))
            require(
                sha(EVIDENCE / manifest["archive"]) == manifest["sha256"],
                "Prior capture differs",
            )
            output["capture_archives"][name] = manifest["sha256"]
        historical = EVIDENCE / "compatibility-330/compatibility-final-rollup.json"
        require(
            output == read(historical),
            "Historical Python and dictionary scopes changed",
        )
        annex_name = "compatibility-47e-files.json"
        annex = read(EVIDENCE / annex_name)
        with capture("compatibility-47e-files") as files:
            folder = files / "fileswhole/files47a"
            files_attempt, files_identity = native(
                folder, subjects["47e0"], image_bytes, "47e0", prompt_count=2
            )
            raw_checks = read(folder / "raw/data-files-results.json")["checks"]
            require(
                annex["prior_330_report_sha256"] == sha(historical)
                and annex["spell"] == NEW
                and annex["worker"] == subjects["47e0"]["worker"]
                and annex["execution"] == files_attempt["execution_id"]
                and annex["native_result_sha256"]
                == sha(folder / "raw/data-files-results.json")
                and annex["authority_sha256"] == sha(folder / "stored-authority.json")
                and annex["read_only_filesystem_capture_sha256"]
                == sha(folder / "stored-files.json")
                and annex["embedded_pass"] == len(raw_checks) == 36
                and all(check["passed"] is True for check in raw_checks.values())
                and files_identity["pid_namespace"]
                not in namespaces | {identity["pid_namespace"]},
                "FILES source, isolated run or annex receipt differs",
            )
        new_files = set(annex["new_direct_ids"])
        repeated_files = set(annex["previously_covered_ids"])
        require(
            len(new_files) == 2
            and len(repeated_files) == 38
            and repeated_files <= earlier
            and not new_files & (parents.keys() | earlier | failed)
            and all(
                rows[key]["historical_oracles"] == refs
                for key, refs in annex["new_direct_ids"].items()
            ),
            "FILES inherited requirements differ from the starting matrix",
        )
        passed = earlier | parents.keys() | new_files
        direct = leaves | selected | parents.keys() | new_files | repeated_files
        remaining = {key for key in rows if key not in passed | failed}
        counts = {
            "pass": len(passed),
            "fail": len(failed),
            "incomplete": len(remaining),
        }
        manifest = read(EVIDENCE / "compatibility-47e-files-captures.json")
        require(
            annex["capture_archive_sha256"] == manifest["sha256"]
            and counts == annex["across_tested_subjects"]
            and len(direct) == annex["47e_direct_distinct"]
            and direct <= passed,
            "Combined FILES coverage disagrees",
        )
        output.update(
            schema="openbexi.v08.native-compatibility-frozen-and-47e/2",
            across_tested_subjects=counts,
            incomplete_after_47e_by_inventory_package=dict(
                sorted(Counter(rows[k]["package"] for k in remaining).items())
            ),
        )
        output["47e_direct_distinct"] = len(direct)
        output["47e_files"] = {
            "evidence": annex_name,
            "sha256": sha(EVIDENCE / annex_name),
            "execution": annex["execution"],
            "embedded_pass": annex["embedded_pass"],
            "new_direct_ids": annex["new_direct_ids"],
            "existing_supported_ids": annex["previously_covered_ids"],
        }
        output["capture_archives"]["compatibility-47e-files"] = manifest["sha256"]
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    path = parser.parse_args().output
    report = run()
    path.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(report["across_tested_subjects"], report["47e_direct_distinct"])
