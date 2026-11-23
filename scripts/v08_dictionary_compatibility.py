"""Verify the original user-dictionary checks on twelve isolated, admitted native roots."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

from v08_additional_native_compatibility import (
    BASE,
    CLIENT,
    CORE,
    GATEWAY,
    IDE,
    ORIGINAL_COLLECTOR,
    ROOT,
    SPELL,
    WORKER,
    authority,
    read,
    require,
    sha,
)
from user_database_cases import EXAMPLE


def verify(raw_root):
    evidence = BASE.parent
    original_path = ROOT / "conformance/evidence/user_database.json"
    original = read(original_path)
    controller = ROOT / "conformance/user_database_controller.py"
    for path in (controller, ROOT / "conformance/user_database_cases.py"):
        require(
            sha(path) == original["inputs"][path.relative_to(ROOT).as_posix()],
            "Original dictionary source differs",
        )
    preludes = [
        n.value.value
        for n in ast.walk(ast.parse(controller.read_bytes()))
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Constant)
        and any(isinstance(t, ast.Name) and t.id == "prelude" for t in n.targets)
    ]
    require(len(preludes) == 1, "Original dictionary controller prelude differs")
    conditions = ("positive", "boundary", "failure", "recovery")
    cases, namespaces = {}, set()
    for group in ("load", "formats", "revert"):
        for dim in conditions:
            key = group + ":" + dim
            suite = "dict" + group + dim
            folder = raw_root / suite / ("db" + group + dim[0])
            old = original["checks"][key]
            expected = (
                preludes[0]
                + "EXAMPLE="
                + repr(EXAMPLE)
                + "\n"
                + old["source"]
                + "\nDisplay('USER_DATABASE_PASSED')\n"
            ).encode()
            code = raw_root / suite / "input/original_case.py"
            result = read(folder / "raw/dictionary-results.json")
            identity = read(folder / "raw/native-runtime.json")
            attempt, deployment = (
                read(folder / "attempt.json"),
                read(folder / "case.json"),
            )
            build = read(folder / "native-build.json")
            require(
                old["passed"] is True
                and code.read_bytes() == expected
                and hashlib.sha256(expected).hexdigest() == result["source_sha256"]
                and result["passed"] is True
                and attempt["passed"] is True
                and attempt["authoritative_native_status"] == "FINISHED",
                "Frozen dictionary assertion or terminal outcome differs: " + key,
            )
            require(
                deployment["worker_image"] == attempt["worker_image"] == WORKER
                and deployment["server_image"] == CORE
                and deployment["gateway_image"] == GATEWAY
                and attempt["ide_client_sha256"] == CLIENT
                and deployment["driver_binding"] == "context-audit"
                and deployment["source_sha256"] == attempt["snapshot_sha256"],
                "Dictionary execution used different deployed bytes or provider",
            )
            require(
                identity["suite"] == suite
                and identity["oracle_inputs"] == {"original_case.py": sha(code)}
                and identity["collector_sha256"] == ORIGINAL_COLLECTOR
                and identity["build_manifest"] == build
                and identity["build_manifest_sha256"]
                == sha(folder / "native-build.json")
                and identity["executable_path"]
                == "/opt/v08-native-home/bin/SPELL-Executor"
                and identity["executable_sha256"] == build["candidate_executor_sha256"]
                and identity["mapped_private_shared_libraries"]
                == [
                    {
                        "path": "/opt/v08-native-home/bin/libspell_executor313.so",
                        "sha256": build["candidate_shared_runtime_sha256"],
                    }
                ]
                and identity["output_directory_identity"]
                == attempt["directory_identity"]
                and not authority(folder, attempt["execution_id"], identity),
                "Dictionary case did not have its own admitted native result",
            )
            require(
                identity["pid_namespace"] not in namespaces,
                "A dictionary native namespace was reused",
            )
            namespaces.add(identity["pid_namespace"])
            cases[key] = {
                "execution_id": attempt["execution_id"],
                "snapshot_sha256": attempt["snapshot_sha256"],
                "native_status": "FINISHED",
                "pid_namespace": identity["pid_namespace"],
                "source_sha256": sha(code),
                "native_result_sha256": sha(folder / "raw/dictionary-results.json"),
                "resulting_file_sha256": result["file_sha256"],
                "resulting_directory": result["directory"],
                "authority_sha256": sha(folder / "stored-authority.json"),
            }
    baseline, previous = (
        read(BASE),
        read(evidence / "compatibility-additional-native.json"),
    )
    existing = {
        r["id"]
        for r in baseline["rows"]
        if r["status"] == "FRESH_INHERITED_DIMENSIONS_PASSED"
    } | set(previous["additional_rows"])
    additional = {}
    for row in baseline["rows"]:
        refs = row["historical_oracles"]
        if all(
            ref["report"] == "conformance/evidence/user_database.json"
            and ref["check"] in cases
            for ref in refs.values()
        ):
            require(
                row["id"] not in existing and len(refs) == 4,
                "Dictionary coverage overlaps a prior result",
            )
            additional[row["id"]] = refs
    return {
        "schema": "openbexi.v08.user-dictionary-compatibility/1",
        "spell": SPELL,
        "ide": IDE,
        "original_oracle_sha256": sha(original_path),
        "previous_direct": len(existing),
        "additional_rows": additional,
        "new_direct_requirements": len(additional),
        "fresh_requirements_across_captures": len(existing) + len(additional),
        "inherited_requirements": len(baseline["rows"]),
        "worker": WORKER,
        "simulation_effects": 0,
        "scope": "Twelve separate single-use native roots ran unmodified historical regular-file load, format and revert assertions in their own new user data directory.",
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.raw_root)
    args.output.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(report["fresh_requirements_across_captures"], len(report["cases"]))


if __name__ == "__main__":
    main()
