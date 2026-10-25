"""Build both complete original native graphs with prompt and terminal hooks.

This qualifies compilation/linking only. Actual procedure termination, prompt
scheduler behavior, whole-family cleanup and public runtime remain unqualified.
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from qualify_v08_native_launch import IMAGE, ROOT, command, load_runtime


def main():
    output = (
        ROOT / ".qualification/v08-native-terminal-build" / ("run-" + uuid.uuid4().hex)
    )
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="openbexi.native-terminal-build/1",
        passed=False,
        scope="full original native Context and Executor graphs; compilation and linkage only",
        candidate_commit=command("git", "rev-parse", "HEAD"),
        runtime_enabled=False,
        native_terminal_lifecycle_qualified=False,
        full_v08_qualified=False,
        source_sha256={},
    )
    tag = "v08-terminal-build-" + uuid.uuid4().hex[:12]
    base = tag + "-frozen"
    try:
        with tempfile.TemporaryDirectory(prefix="v08-terminal-build-") as directory:
            directory = Path(directory)
            load_runtime(directory, output)
            command("docker", "tag", IMAGE, base)
            build = directory / "build"
            build.mkdir()
            inputs = [*sorted((ROOT / "host_runtime/native").glob("*.H"))]
            inputs += [
                ROOT / "host_runtime" / p
                for p in (
                    "build_admission_context.py",
                    "native_prompt_patch.py",
                    "native_terminal_patch.py",
                )
            ]
            for path in inputs:
                destination = (
                    "build.py"
                    if path.name == "build_admission_context.py"
                    else path.name
                )
                shutil.copyfile(path, build / destination)
                report["source_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
            (build / "Dockerfile").write_text(
                "FROM " + base + "\nUSER root\n"
                "RUN apt-get update && apt-get install -y --no-install-recommends "
                "g++ nlohmann-json3-dev libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev\n"
                "COPY *.H build.py native_prompt_patch.py native_terminal_patch.py /candidate/\n"
                "RUN python /candidate/build.py --native-prompts --native-terminals\n"
                "USER 10003:10003\n"
            )
            result = subprocess.run(
                ["docker", "build", "-t", tag, str(build)],
                capture_output=True,
                timeout=1000,
            )
            (output / "build.log").write_bytes(result.stdout + result.stderr)
            result.check_returncode()
            report["image"] = command(
                "docker", "image", "inspect", "--format", "{{.Id}}", tag
            )
            native = json.loads(
                command(
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--entrypoint",
                    "cat",
                    tag,
                    "/opt/v08-native-home/build.json",
                )
            )
            if (
                native.get("native_prompt_hooks") is not True
                or native.get("native_terminal_hooks") is not True
            ):
                raise ValueError("Native opt-in hook flags missing")
            if native.get("full_v08_qualified") is not False or not native.get("units"):
                raise ValueError("Native build receipt identity differs")
            if set(native.get("graph_units", {})) != {"Context", "Executor"}:
                raise ValueError("Both original native graphs must be linked")
            for path in inputs:
                if (
                    path.suffix == ".H"
                    and native["admission_headers"].get(path.name)
                    != hashlib.sha256(path.read_bytes()).hexdigest()
                ):
                    raise ValueError("Compiled admission header digest differs")
            (output / "native-build.json").write_text(
                json.dumps(native, indent=2) + "\n"
            )
            report.update(
                passed=True,
                compiled_units=len(native["units"]),
                graphs=native["graph_units"],
            )
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        subprocess.run(
            ["docker", "image", "rm", tag, base], capture_output=True, timeout=30
        )
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
