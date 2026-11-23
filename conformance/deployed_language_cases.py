"""Run complete unprompted FILES and COMMON cases from the frozen native oracles."""

import ast
import hashlib
import json
from pathlib import Path


SUITES = {
    "files": {
        "sha256": "91353511346c878064f7506b11a9022ef607581ee34ef6011a327ad6ba1accd3",
        "cases": ("modes", "close", "write", "read", "directory", "paths", "delete"),
    },
    "common": {
        "sha256": "345be8cfe4a0c9dc3a9d340dc6f5430e4585e9d0f7d5805e37426f2a9c55c37e",
        "cases": ("noaction", "configuration", "operation-success"),
    },
}
DIMENSIONS = ("positive", "boundary", "failure", "recovery")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def program(directory, name):
    source = (directory / (name + "_contracts.py")).read_bytes()
    if digest(source) != SUITES[name]["sha256"]:
        raise ValueError("Frozen oracle bytes differ")
    blocks = ast.parse(source).body
    (loop,) = [
        n
        for n in blocks
        if isinstance(n, ast.For)
        and isinstance(n.iter, ast.Call)
        and isinstance(n.iter.func, ast.Attribute)
        and isinstance(n.iter.func.value, ast.Name)
        and n.iter.func.value.id == "cases"
        and n.iter.func.attr == "items"
    ]
    lines = source.splitlines(keepends=True)
    return b"".join(lines[: loop.lineno - 1]), b"".join(
        lines[loop.lineno - 1 : loop.end_lineno]
    )


def run(name):
    directory = Path(__file__).parent
    setup, dispatch = program(directory, name)
    filename = str(directory / (name + "_contracts.py"))
    namespace = {"__name__": name + "_contracts", "__file__": filename}
    exec(compile(setup, filename, "exec"), namespace)
    registered = namespace["cases"]
    namespace["cases"] = {key: registered[key] for key in SUITES[name]["cases"]}
    exec(compile(dispatch, filename, "exec"), namespace)
    rows = namespace["checks"]
    selected = {key + ":" + dim for key in SUITES[name]["cases"] for dim in DIMENSIONS}
    if set(rows) != selected or any(row["expected_prompts"] for row in rows.values()):
        raise ValueError("Selected case scope or prompt policy changed")
    output = {
        "checks": rows,
        "original_setup_sha256": digest(setup),
        "original_dispatch_sha256": digest(dispatch),
    }
    Path(name + "-results.json").write_text(json.dumps(output, indent=2) + "\n")
    import v08_native_language_batch as collector

    collector.SPECS = (
        *collector.SPECS,
        {"name": name, "files": [name + "_contracts.py", Path(__file__).name]},
    )
    collector.write_runtime_identity(name)


def mapping(root, name):
    report = json.loads((root / "conformance/evidence" / (name + ".json")).read_bytes())
    if (
        report["inputs"]["conformance/" + name + "_contracts.py"]
        != SUITES[name]["sha256"]
    ):
        raise ValueError("Historical oracle input differs")
    rows = {}
    for key in SUITES[name]["cases"]:
        for dim in DIMENSIONS:
            check = key + ":" + dim
            old = report["checks"][check]
            if (
                old.get("passed") is not True
                or old["dimension"] != dim
                or old["controller_prompts"]
            ):
                raise ValueError("Inherited case needs an external controller")
            rows[check] = old
    return rows


def validate(root, name, raw, identity, build, collector_sha):
    historical = mapping(root, name)
    checks = raw["checks"]
    if set(historical) != set(checks):
        raise ValueError("Missing or extra native dimensional check")
    setup, dispatch = program(root / "conformance", name)
    if (raw["original_setup_sha256"], raw["original_dispatch_sha256"]) != (
        digest(setup),
        digest(dispatch),
    ):
        raise ValueError("Executed oracle source differs")
    for key, expected in historical.items():
        result = checks[key]
        if (
            result.get("passed") is not True
            or result.get("expected_prompts") != []
            or any(
                result.get(field) != expected[field]
                for field in ("dimension", "contracts", "oracle")
            )
        ):
            raise ValueError("Native original assertion failed or changed: " + key)
    expected_sources = {
        name + "_contracts.py": SUITES[name]["sha256"],
        "deployed_language_cases.py": digest(Path(__file__).read_bytes()),
    }
    home = "/opt/v08-native-home/bin/"
    if (
        identity["suite"] != name
        or identity["executable_path"] != home + "SPELL-Executor"
        or identity["executable_sha256"] != build["candidate_executor_sha256"]
        or identity["mapped_private_shared_libraries"]
        != [
            {
                "path": home + "libspell_executor313.so",
                "sha256": build["candidate_shared_runtime_sha256"],
            }
        ]
        or identity["build_manifest"] != build
        or identity["build_manifest_sha256"]
        != digest((json.dumps(build, indent=2) + "\n").encode())
        or identity["oracle_inputs"] != expected_sources
        or identity["collector_sha256"] != collector_sha
        or identity["start_ticks"] <= 0
        or identity["pid"] <= 0
        or identity["cwd"] != "/workspace/native-language-results"
    ):
        raise ValueError("Native oracle source or process identity differs")
    ids = sorted(
        {identifier for old in historical.values() for identifier in old["contracts"]}
    )
    return {
        "passed": True,
        "suite": name,
        "dimensional_checks": len(historical),
        "mapped_requirement_ids": ids,
        "distinct_mapped_requirements": len(ids),
        "not_original_spelling_qualification": {},
    }
