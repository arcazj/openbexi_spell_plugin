"""TIME/PY/DATA original oracle bytes in separate admitted native roots.

This is additive diagnostic evidence. The enclosing cohort fixture and output
binds differ; no mandatory cohort resource acceptance or complete native
compatibility qualification follows from these results.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASELINE = "d057c5b741e96c8c423d90ee6c7c4e1eccfefe8e"
PRODUCT = "98ec37a820386e3e382d97fb8c2f75107ccb4370"
ALLOWED_CHANGES = {
    "scripts/qualify_v08_native_launch.py",
    "scripts/v08_native_language_batch.py",
    "server/tests/test_v08_native_language_batch.py",
    "server/tests/test_v08_native_time_compatibility.py",
    ".github/workflows/v08-native-language-batch.yml",
}
PREIMAGES = {
    "conformance/inventory.json": "18a022c53f36064d05f934adb1d1e2e2944eb6ce6560ae3973b5bacf3b4b62fa",
    "conformance/time_contracts.py": "3e0c5f543593b5d7c5ef6a452583cec19196c9eb2c190f31ce5c278c20f53f96",
    "conformance/python_contracts.py": "35c2d48a973139b123cb3fc8bf4d8c05d00a291d0c6c32760cae49792b7993fb",
    "conformance/python_fixture.py": "b251964282a2b9ee355a03ea4e5dc6bdf02aa548632c5a3b00f51b2379537fce",
    "conformance/data_contracts.py": "23a60a8730e0fb3ba52763acbcb95c19f7d984f374c1074beec5a6cc3154ab41",
}
SPECS = (
    dict(
        name="time",
        package="TIME",
        module="time_contracts",
        files=["time_contracts.py"],
        result="time-results.json",
        checks=168,
    ),
    dict(
        name="python",
        package="PY",
        module="python_contracts",
        files=["python_contracts.py", "python_fixture.py"],
        result="python-results.json",
        checks=488,
    ),
    dict(
        name="data",
        package="DATA",
        module="data_contracts",
        files=["data_contracts.py"],
        result="data-files-results.json",
        checks=24,
    ),
)
DIMENSIONS = ("positive", "boundary", "failure", "recovery")
LEGACY = {
    "CMP-LRM244-METHOD-DICTIONARY-HAS-KEY",
    "CMP-LRM244-OPERATOR-PYTHON-LEGACY-NOT-EQUAL",
    "CMP-LRM244-SYNTAX-INTEGER-OCTAL",
}
HOME = "/opt/v08-native-home/bin/"
OUTPUT_DIRECTORY = "/workspace/native-language-results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_inputs(root):
    for name, expected in PREIMAGES.items():
        if sha(root / name) != expected:
            raise ValueError("Original language input differs: " + name)


def check_mapping(root, spec):
    protected_inputs(root)
    if spec["name"] == "data":
        result = {}
        tree = ast.parse((root / "conformance/data_contracts.py").read_bytes())
        for node in tree.body:
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "case"
            ):
                case = ast.literal_eval(node.value.args[0])
                contracts = [
                    "CMP-LRM244-" + x for x in ast.literal_eval(node.value.args[1])
                ]
                for dimension in DIMENSIONS:
                    result[case + ":" + dimension] = contracts
        if len(result) != 24 or len({x for v in result.values() for x in v}) != 29:
            raise ValueError("Original DATA case mapping changed")
        return result
    rows = json.loads((root / "conformance/inventory.json").read_text())["rows"]
    identifiers = sorted(row["id"] for row in rows if row["package"] == spec["package"])
    if len(identifiers) != (42 if spec["name"] == "time" else 122):
        raise ValueError("Original language requirement inventory changed")
    return {
        name + ":" + dimension: [name]
        for name in identifiers
        for dimension in DIMENSIONS
    }


def source_identity(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Language batch requires clean tracked sources")
    if (
        git("merge-base", BASELINE, "HEAD") != BASELINE
        or git("merge-base", PRODUCT, BASELINE) != PRODUCT
    ):
        raise ValueError("Language batch immutable ancestry changed")
    changes = set(git("diff", "--name-only", BASELINE, "HEAD").splitlines())
    if not changes <= ALLOWED_CHANGES:
        raise ValueError("Language batch contains product/runtime changes")
    protected_inputs(root)
    for name, expected in PREIMAGES.items():
        raw = subprocess.check_output(["git", "show", PRODUCT + ":" + name], cwd=root)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Immutable product oracle input changed")
    return dict(
        commit=git("rev-parse", "HEAD"),
        tree=git("rev-parse", "HEAD^{tree}"),
        product_reference=PRODUCT,
        diagnostic_baseline=BASELINE,
        protected_inputs=PREIMAGES,
        changed_paths=sorted(changes),
        full_v08_qualified=False,
        all763_qualified=False,
    )


def suffix(spec):
    return (
        "\n# Additive isolated language diagnostic; original prefix retained.\nimport os as _oracle_os\n_oracle_cwd = _oracle_os.getcwd()\ntry:\n    _oracle_os.chdir("
        + repr(OUTPUT_DIRECTORY)
        + ")\n    import "
        + spec["module"]
        + "\n    from v08_native_language_batch import write_runtime_identity\n    write_runtime_identity("
        + repr(spec["name"])
        + ")\nfinally:\n    _oracle_os.chdir(_oracle_cwd)\n"
    )


def prepare_fixture(sources, root):
    protected_inputs(root)
    names = [p for spec in SPECS for p in spec["files"]] + [
        "v08_native_language_batch.py"
    ]
    if any((sources / name).exists() for name in names):
        raise ValueError("Language fixture target already exists")
    for spec in SPECS:
        for name in spec["files"]:
            (sources / name).write_bytes((root / "conformance" / name).read_bytes())
    (sources / "v08_native_language_batch.py").write_bytes(Path(__file__).read_bytes())
    records = []
    for index, spec in enumerate(SPECS):
        path = sources / ("procedure_" + str(index) + ".py")
        original = path.read_bytes()
        path.write_bytes(original + suffix(spec).encode())
        records.append(
            dict(
                root_index=index,
                suite=spec["name"],
                original_prefix_sha256=hashlib.sha256(original).hexdigest(),
                additive_fixture_sha256=sha(path),
                original_oracle_sha256={
                    name: sha(sources / name) for name in spec["files"]
                },
                requirement_ids=sorted(
                    {x for v in check_mapping(root, spec).values() for x in v}
                ),
            )
        )
    return dict(
        suites=records,
        independent_native_roots=True,
        enclosing_cohort_fixture_changed=True,
        original_cohort_resource_acceptance=False,
    )


def write_runtime_identity(name):
    spec = next(x for x in SPECS if x["name"] == name)
    stat = Path("/proc/self/stat").read_text()
    start = int(stat.rsplit(")", 1)[1].split()[19])
    exe = Path("/proc/self/exe")
    maps = Path("/proc/self/maps").read_text()
    shared = sorted(
        {
            line.split()[-1]
            for line in maps.splitlines()
            if line.split()[-1] == HOME + "libspell_executor313.so"
        }
    )
    build = Path("/opt/v08-native-home/build.json")
    directory = Path(OUTPUT_DIRECTORY).stat()
    record = dict(
        suite=name,
        pid=os.getpid(),
        start_ticks=start,
        pid_namespace=os.readlink("/proc/self/ns/pid"),
        executable_path=os.readlink(exe),
        executable_sha256=sha(exe),
        mapped_private_shared_libraries=[dict(path=p, sha256=sha(p)) for p in shared],
        build_manifest=json.loads(build.read_text()),
        build_manifest_sha256=sha(build),
        oracle_inputs={p: sha(Path(__file__).with_name(p)) for p in spec["files"]},
        collector_sha256=sha(__file__),
        proc_stat=stat,
        maps=maps,
        cwd=os.getcwd(),
        output_directory_identity=dict(device=directory.st_dev, inode=directory.st_ino),
    )
    if (
        int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]) != start
        or sha(exe) != record["executable_sha256"]
    ):
        raise ValueError("Actual native language process identity changed")
    Path("native-runtime.json").write_text(json.dumps(record, indent=2) + "\n")


def validate_result(raw, identity, build, root, spec):
    expected = check_mapping(root, spec)
    checks = raw.get("checks")
    if (
        type(checks) is not dict
        or set(checks) != set(expected)
        or len(checks) != spec["checks"]
    ):
        raise ValueError("Original language check identities changed/incomplete")
    for name, contracts in expected.items():
        row = checks[name]
        if (
            row.get("passed") is not True
            or row.get("contracts") != contracts
            or row.get("dimension") != name.rsplit(":", 1)[1]
        ):
            raise ValueError("Original language assertion failed/changed: " + name)
        if spec["name"] == "data" and row.get("expected_prompts") != []:
            raise ValueError(
                "DATA oracle unexpectedly requires an external prompt controller"
            )
    if any(
        type(build.get(k)) is not str or re.fullmatch(r"[0-9a-f]{64}", build[k]) is None
        for k in ("candidate_executor_sha256", "candidate_shared_runtime_sha256")
    ):
        raise ValueError("Actual native artifact hashes absent")
    if (
        identity.get("suite") != spec["name"]
        or type(identity.get("pid")) is not int
        or identity["pid"] <= 0
        or type(identity.get("start_ticks")) is not int
        or identity["start_ticks"] <= 0
        or not re.fullmatch(r"pid:\[\d+\]", identity.get("pid_namespace", ""))
        or identity.get("executable_path") != HOME + "SPELL-Executor"
        or identity.get("executable_sha256") != build["candidate_executor_sha256"]
        or identity.get("mapped_private_shared_libraries")
        != [
            dict(
                path=HOME + "libspell_executor313.so",
                sha256=build["candidate_shared_runtime_sha256"],
            )
        ]
        or identity.get("build_manifest") != build
        or identity.get("build_manifest_sha256")
        != hashlib.sha256((json.dumps(build, indent=2) + "\n").encode()).hexdigest()
        or identity.get("oracle_inputs")
        != {p: PREIMAGES["conformance/" + p] for p in spec["files"]}
        or identity.get("collector_sha256") != sha(__file__)
        or identity.get("cwd") != OUTPUT_DIRECTORY
    ):
        raise ValueError("Actual native language process/source binding failed")
    ids = sorted({x for v in expected.values() for x in v})
    not_original = {}
    if spec["name"] == "python":
        if (
            set(raw.get("legacy_contracts", {})) != LEGACY
            or raw.get("semantics") != "CPython 3.13"
            or raw.get("checkpoint_claim") is not False
        ):
            raise ValueError("Python migration/source semantics changed")
        for identifier in ids:
            if identifier in LEGACY:
                for dimension in DIMENSIONS:
                    row = checks[identifier + ":" + dimension]
                    if (
                        row.get("legacy_spelling_supported") is not False
                        or row.get("evidence_kind") != "migration-and-rejection"
                    ):
                        raise ValueError(
                            "Python migration/rejection was relabeled as original support"
                        )
                not_original[identifier] = (
                    "migration-and-rejection; original spelling unqualified"
                )
            elif "-SECTION-" in identifier:
                not_original[identifier] = (
                    "broader parent section unqualified by this diagnostic"
                )
    return dict(
        passed=True,
        suite=spec["name"],
        dimensional_checks=len(checks),
        mapped_requirement_ids=ids,
        distinct_mapped_requirements=len(ids),
        not_original_spelling_qualification=not_original,
        actual_native_executor_verified=True,
        original_oracle_unchanged=True,
        enclosing_cohort_fixture_changed=True,
        original_cohort_resource_acceptance=False,
        all763_qualified=False,
        full_v08_qualified=False,
        historical_recovery=False,
        companion_ide_executed=False,
    )


def prepare_output(output, index):
    spec = SPECS[index]
    directory = output / "native-language-batch" / spec["name"] / "raw"
    directory.mkdir(parents=True, exist_ok=False)
    directory.chmod(0o777)
    return ["--mount", f"type=bind,src={directory},dst={OUTPUT_DIRECTORY}"]


def collect_result(output, build, root, *, cohort_passed):
    destination = output / "native-language-batch"
    destination.mkdir(parents=True, exist_ok=True)
    suites = []
    for spec in SPECS:
        directory = destination / spec["name"] / "raw"
        attempts = []
        result = dict(suite=spec["name"], passed=False)
        for name in (spec["result"], "native-runtime.json"):
            entry = dict(file=name, retained=False)
            try:
                path = directory / name
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Missing/nonregular native language output")
                before = path.stat()
                digest = sha(path)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise ValueError("Native output changed during collection")
                entry.update(retained=True, sha256=digest, bytes=after.st_size)
            except Exception as error:
                entry["error"] = type(error).__name__ + ": " + str(error)
            attempts.append(entry)
        result["retention"] = attempts
        try:
            if not all(row["retained"] for row in attempts):
                raise ValueError("Native language raw retention incomplete")
            raw = json.loads((directory / spec["result"]).read_text())
            identity = json.loads((directory / "native-runtime.json").read_text())
            stat = directory.stat()
            if identity.get("output_directory_identity") != dict(
                device=stat.st_dev, inode=stat.st_ino
            ):
                raise ValueError("Native output is not actual writer's bind")
            if cohort_passed is not True:
                raise ValueError("Original native authority/cohort controls failed")
            result.update(validate_result(raw, identity, build, root, spec))
            result["pid_namespace"] = identity["pid_namespace"]
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        suites.append(result)
    namespaces = [row.get("pid_namespace") for row in suites if row["passed"]]
    record = dict(
        passed=all(row["passed"] for row in suites) and len(set(namespaces)) == 3,
        suites=suites,
        independent_native_pid_namespaces=len(set(namespaces)) == 3,
        all763_qualified=False,
        full_v08_qualified=False,
        original_cohort_resource_acceptance=False,
    )
    (destination / "verified-result.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    if not record["passed"]:
        raise ValueError(
            "Native language diagnostic batch failed; all outcomes retained"
        )
    return record
