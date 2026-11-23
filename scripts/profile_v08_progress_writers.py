"""Measure the recovery fixture's buffered writers in isolation on its frozen CPython.

The two child processes reproduce the file-write portion of the fixture. The
parent samples their cgroup and identities. This is a component comparison.
Run inside a fresh Linux container with the original /workspace tmpfs, zero
swap and two CPUs. Build the two embedded interpreters with --build first.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import sysconfig
import threading
import time


HERE = Path(__file__).resolve().parent
CGROUP = Path("/sys/fs/cgroup")
FINISH = Path("/control/handoff-finish")
COUNTERS = ("root", "background", "child")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(destination):
    source = destination / "embedded.cpp"
    source.write_text(
        "#include <Python.h>\nint main(int argc, char** argv) { return Py_BytesMain(argc, argv); }\n"
    )
    builds = {}
    for name, flags in (
        ("optimized", ["-O2"]),
        (
            "sanitized",
            [
                "-O1",
                "-g",
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer",
                "-no-pie",
            ],
        ),
    ):
        binary = destination / name
        command = [
            "c++",
            "-std=c++17",
            *flags,
            "-I" + sysconfig.get_path("include"),
            str(source),
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-o",
            str(binary),
        ]
        subprocess.run(command, check=True)
        builds[name] = {"command": command, "sha256": digest(binary)}
    return {
        "source_sha256": digest(source),
        "compiler": subprocess.check_output(
            ["c++", "--version"], text=True
        ).splitlines()[0],
        "builds": builds,
    }


def writer_source():
    module = ast.parse((HERE / "v08_handoff_cohort.py").read_text())
    fixture = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "handoff_fixture"
    )
    (definition,) = [
        node.value
        for node in fixture.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "progress"
    ]
    return ast.literal_eval(definition)


def run_writer(role):
    namespace = {"os": os, "time": time}
    exec(compile(writer_source(), "handoff_fixture:progress", "exec"), namespace)
    progress = namespace["progress"]
    if role == "child":
        progress("handoff-child")
    else:
        background = threading.Thread(target=progress, args=("handoff-background",))
        background.start()
        progress("handoff-root")
        background.join()


def counter_paths():
    return [Path("/workspace") / ("handoff-" + name) for name in COUNTERS]


def mapped_libraries(pid):
    paths = {
        line.split()[-1]
        for line in Path(f"/proc/{pid}/maps").read_text().splitlines()
        if any(
            name in line for name in ("libpython3.13.so", "libasan.so", "libubsan.so")
        )
    }
    return {name: digest(Path(name)) for name in sorted(paths)}


def sample(start):
    return {
        "seconds": round(time.monotonic() - start, 6),
        "resident": int((CGROUP / "memory.current").read_text()),
        "swap": int((CGROUP / "memory.swap.current").read_text()),
        "progress": [int(p.read_text()) for p in counter_paths()],
    }


def observe(binary, seconds):
    if FINISH.exists() or any(path.exists() for path in counter_paths()):
        raise ValueError(
            "This comparison requires an empty private workspace and control directory"
        )
    children = []
    try:
        for role in ("root", "child"):
            children.append(
                subprocess.Popen([str(binary), "-I", __file__, "--writer", role])
            )
        deadline = time.monotonic() + 20
        while not all(path.is_file() for path in counter_paths()):
            if (
                any(child.poll() is not None for child in children)
                or time.monotonic() >= deadline
            ):
                raise RuntimeError("Writer initialization failed")
            time.sleep(0.05)
        libraries = mapped_libraries(children[0].pid)
        if libraries != mapped_libraries(children[1].pid):
            raise RuntimeError(
                "The two writer processes have different mapped libraries"
            )
        profile = binary.name
        if profile not in ("optimized", "sanitized"):
            raise ValueError("Unknown comparison binary")
        for lib in ("libasan.so", "libubsan.so"):
            if any(lib in name for name in libraries) != (profile == "sanitized"):
                raise RuntimeError(
                    "Mapped instrumented dependency differs from the requested profile"
                )
        start = time.monotonic()
        rows = [sample(start)]
        while rows[-1]["seconds"] < seconds:
            time.sleep(min(2, seconds - rows[-1]["seconds"]))
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A writer exited during the observation window")
            rows.append(sample(start))
    finally:
        FINISH.touch()
        for child in children:
            child.wait(timeout=15)
    if any(child.returncode for child in children):
        raise RuntimeError("Writer failed during cleanup")
    if any(
        b <= a
        for x, y in zip(rows, rows[1:])
        if y["seconds"] - x["seconds"] >= 1
        for a, b in zip(x["progress"], y["progress"], strict=True)
    ):
        raise RuntimeError("Writer progress stalled")

    def usage(row):
        return row["resident"] + row["swap"]

    first = [usage(row) for row in rows if row["seconds"] <= 10]
    last = [usage(row) for row in rows if row["seconds"] >= rows[-1]["seconds"] - 10]
    return {
        "scope": "Isolated root/background/child file writers only",
        "profile": profile,
        "runtime": sys.version,
        "binary_sha256": digest(binary),
        "fixture_sha256": digest(HERE / "v08_handoff_cohort.py"),
        "writer_sha256": hashlib.sha256(writer_source().encode()).hexdigest(),
        "mapped_libraries": libraries,
        "original_writer_pids": [p.pid for p in children],
        "asan_options": os.getenv("ASAN_OPTIONS"),
        "ubsan_options": os.getenv("UBSAN_OPTIONS"),
        "pythonmalloc": os.getenv("PYTHONMALLOC"),
        "memory_limit": int((CGROUP / "memory.max").read_text()),
        "swap_limit": int((CGROUP / "memory.swap.max").read_text()),
        "memory_events": (CGROUP / "memory.events").read_text().splitlines(),
        "cgroup_peak_bytes": int((CGROUP / "memory.peak").read_text()),
        "swap_peak_bytes": int((CGROUP / "memory.swap.peak").read_text()),
        "first_median_bytes": statistics.median(first),
        "last_median_bytes": statistics.median(last),
        "window_growth_bytes": statistics.median(last) - statistics.median(first),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--build", type=Path)
    choice.add_argument("--binary", type=Path)
    choice.add_argument("--writer", choices=("root", "child"))
    parser.add_argument("--seconds", type=int, choices=(45, 300), default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.writer:
        run_writer(args.writer)
        return
    if not args.output:
        parser.error("--build and --binary require a new --output file")
    result = build(args.build) if args.build else observe(args.binary, args.seconds)
    if str(args.output) == "-":
        print(json.dumps(result, indent=2), flush=True)
        return
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)


if __name__ == "__main__":
    main()
