"""Explicit complete-native build profiles; no runtime source-overlay generator.

Uses the same verified frozen composition as the mandatory admission builder.
The legacy builder remains the mandatory sanitizer/O1 default.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile

from build_admission_context import native_graph, patch_native_tree, sha

PROFILES = {
    "asan-o1": ("-O1", True),
    "asan-o2": ("-O2", True),
    "optimized": ("-O2", False),
}


def profile_flags(name):
    if name not in PROFILES:
        raise ValueError("Unknown native build profile")
    optimization, sanitized = PROFILES[name]
    sanitizer = (
        ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
        if sanitized
        else []
    )
    compile_flags = [
        optimization,
        *sanitizer,
        "-fno-omit-frame-pointer",
        "-DOPENBEXI_NATIVE_TRACE_LIMIT=2048",
    ]
    if not sanitized:
        compile_flags.append("-DOPENBEXI_NATIVE_NO_SANITIZERS=1")
    return compile_flags, sanitizer[:1]


LISTENER_LAUNCHER = """from pathlib import Path
import os
import sys
from spell_native.launcher import environment
if os.environ.get("LD_PRELOAD"):
    raise SystemExit("Unexpected native preload")
program = Path("/opt/v08-native-home/bin/SPELL-Listener")
os.execve(program, [str(program), *sys.argv[1:]], environment())
"""


def finalize_profile(home, programs, report, name):
    """Bind DTA/Listener to the same rebuilt family and verify actual ELF imports."""
    sanitized = PROFILES[name][1]
    shim = Path(sysconfig.get_path("purelib")) / "libSPELL_DTA_v3.py"
    before = shim.read_text()
    guard = "if 'libasan.so' not in Path('/proc/self/maps').read_text(encoding='utf-8'):\n    raise ImportError('This diagnostic native build requires spell-native-python or spell-native run.')\n"
    location = "_path = launcher.ROOT / 'bin/libspell_executor313.so'"
    if before.count(guard) != 1 or before.count(location) != 1:
        raise ValueError("Native profile DTA shim preimage differs")
    after = before.replace(
        location, "_path = Path('/opt/v08-native-home/bin/libspell_executor313.so')"
    )
    if not sanitized:
        after = after.replace(guard, "")
    shim.write_text(after)
    (home / "launch-listener.py").write_text(LISTENER_LAUNCHER)
    dependencies = {}
    binaries = home / "bin"
    artifacts = [binaries / "libspell_executor313.so", binaries / "spell-host-ipc"]
    artifacts += [binaries / ("SPELL-" + n) for n in programs]
    for artifact in artifacts:
        linked = subprocess.check_output(["readelf", "-d", str(artifact)], text=True)
        names = re.findall(r"Shared library: \[(.*?)\]", linked)
        for library in ("libasan", "libubsan"):
            if any(library in value for value in names) != sanitized:
                raise ValueError(
                    "Native artifact instrumentation differs: " + artifact.name
                )
        dependencies[artifact.name] = names
    report.update(
        native_build_profile=name,
        optimization=PROFILES[name][0],
        sanitizer_enabled=sanitized,
        sanitizer_allocator_metrics_available=sanitized,
        candidate_listener_sha256=programs["Listener"],
        profile_dependencies=dependencies,
        listener_launcher_sha256=sha(home / "launch-listener.py"),
        profile_dta_shim={
            "before": hashlib.sha256(before.encode()).hexdigest(),
            "after": sha(shim),
        },
        python=sys.version,
        source_date_epoch=os.environ.get("SOURCE_DATE_EPOCH"),
        reproducibility_scope="source and compiler configuration; bitwise rebuild not yet certified",
        profile_builder_sha256=sha(Path(__file__)),
        composition_builder_sha256=sha(
            Path(__file__).with_name("build_admission_context.py")
        ),
        eligible_for_publication=False,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-prompts",
        action="store_true",
        help="Build private owner-bound prompt hooks; needs matching agent",
    )
    parser.add_argument("--native-terminal", action="store_true")
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    args = parser.parse_args()
    if (
        sys.version_info[:2] != (3, 13)
        or sys.version_info[:3] < (3, 13, 15)
        or sysconfig.get_config_var("Py_GIL_DISABLED")
    ):
        raise RuntimeError("Native profiles require GIL-enabled CPython 3.13.15+")
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None and (not epoch.isdecimal() or len(epoch) > 12):
        raise ValueError("Invalid SOURCE_DATE_EPOCH")
    profile_compile, profile_link = profile_flags(args.profile)
    if args.native_terminal:
        args.native_prompts = True
    import spell_native

    runtime = Path(spell_native.__file__).parent
    recipe = runtime / "provenance/source_port"
    sys.path.insert(0, str(recipe))
    from native_patches import apply_tree
    from integrated_patches import apply_native_tree
    from native_manifest import libraries

    archive = runtime / "provenance/SPELL2.6.10-src.zip"
    manifest = json.loads((runtime / "manifest.json").read_text())
    if sha(archive) != manifest["archive_sha256"]:
        raise ValueError("Native source archive differs")
    source = Path("/tmp/v08-context-source")
    source.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = (source / member.filename).resolve()
            if not path.is_relative_to(source):
                raise ValueError("Source archive traversal")
            if not member.is_dir():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bundle.read(member))
    apply_tree(source)
    composition = apply_native_tree(
        source, archive, Path("/tmp/v08-context-composition")
    )
    expected = dict(manifest["composition"]["native"])
    expected.pop("manifest_sha256")
    if composition != expected:
        raise ValueError("Installed native source composition does not reproduce")
    before = patch_native_tree(
        source, prompts=args.native_prompts, terminal=args.native_terminal
    )
    build = Path("/tmp/v08-context-objects")
    build.mkdir()
    flags = [
        "c++",
        "-std=c++17",
        "-fPIC",
        "-g",
        "-pthread",
        "-fmax-errors=4",
        *profile_compile,
        "-fno-omit-frame-pointer",
        "-I" + str(source / "include"),
        "-I" + sysconfig.get_path("include"),
    ]
    if args.native_terminal:
        flags.append("-DOPENBEXI_V08_TERMINAL=1")
    graphs = {
        name: native_graph(source, libraries, name)
        for name in ("Context", "Executor", "Listener")
    }
    # Reproduce the frozen common runtime's 13-library graph, not only the
    # server executable's dependency subset. These two port support sources are
    # explicit supplemental units in the frozen native_build/executor_build.
    runtime_graph = native_graph(source, libraries, "ExecutorCmd_v3")[:-1]
    support = [
        recipe / "native" / name for name in ("ws_filter.cpp", "continuation.cpp")
    ]
    for path in support:
        if sha(path) != manifest["inputs"][path.relative_to(recipe).as_posix()]:
            raise ValueError("Frozen native support source differs")
    flags.append("-I" + str(recipe / "native"))
    units = sorted(
        set(
            [path for graph in graphs.values() for path in graph]
            + runtime_graph
            + support
        )
    )

    def compile_unit(path):
        name = (
            path.relative_to(source).as_posix()
            if path.is_relative_to(source)
            else "support/" + path.name
        )
        obj = build / (name.replace("/", "_") + ".o")
        result = subprocess.run(
            flags + ["-c", str(path), "-o", str(obj)], capture_output=True, timeout=180
        )
        obj.with_suffix(".log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            print((result.stdout + result.stderr).decode(), file=sys.stderr)
            raise RuntimeError("Native compilation failed: " + name)
        return dict(unit=name, sha256=sha(path), object=str(obj))

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(compile_unit, units))
    home = Path("/opt/v08-native-home")
    home.mkdir()
    for child in runtime.iterdir():
        if child.name != "bin":
            (home / child.name).symlink_to(child, target_is_directory=child.is_dir())
    binaries = home / "bin"
    binaries.mkdir()
    for child in (runtime / "bin").iterdir():
        if child.name not in {
            "SPELL-Listener",
            "SPELL-Context",
            "SPELL-Executor",
            "SPELL-Executor_v3",
            "libspell_executor313.so",
        }:
            (binaries / child.name).symlink_to(child)
    indexed = {row["unit"]: row["object"] for row in records}
    shared = binaries / "libspell_executor313.so"
    shared_objects = [
        indexed[path.relative_to(source).as_posix()] for path in runtime_graph
    ]
    shared_objects += [indexed["support/" + path.name] for path in support]
    subprocess.run(
        [
            "c++",
            "-shared",
            "-pthread",
            *profile_link,
            "-Wl,--no-undefined",
            *shared_objects,
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-llog4cplus",
            "-lxerces-c",
            "-lz",
            "-lmenu",
            "-lncurses",
            "-o",
            str(shared),
        ],
        check=True,
        timeout=120,
    )
    programs = {}
    for name, graph in graphs.items():
        program = binaries / ("SPELL-" + name)
        objects = [indexed[path.relative_to(source).as_posix()] for path in graph]
        if name == "Executor":
            objects = [
                indexed[graph[-1].relative_to(source).as_posix()],
                "-L" + str(binaries),
                "-lspell_executor313",
                "-Wl,-rpath,$ORIGIN",
            ]
        subprocess.run(
            [
                "c++",
                "-pthread",
                *profile_link,
                "-Wl,--no-undefined",
                *objects,
                "-L" + sysconfig.get_config_var("LIBDIR"),
                "-lpython3.13",
                "-llog4cplus",
                "-lxerces-c",
                "-lz",
                "-lmenu",
                "-lncurses",
                "-o",
                str(program),
            ],
            check=True,
            timeout=120,
        )
        programs[name] = sha(program)
    (binaries / "SPELL-Executor_v3").symlink_to("SPELL-Executor")
    # The opt-in session must use the same candidate IPC codec as its native
    # peers. The frozen host bridge and default session remain separate.
    bridge_source = Path("/candidate/private_bridge.cpp")
    fields = set()
    for header in (source / "include/SPELL_IPC").glob("*.H"):
        fields.update(
            re.findall(r'FIELD_\w+\s*\(\s*"([^"]+)"\s*\)', header.read_text())
        )
    if not {"Csp", "ExecutorStatus", "VarName", "VarValue", "ContextPort"} <= fields:
        raise ValueError("Native bridge field inventory differs")
    fields.update({"DefaultProvided", "TimeoutMicroseconds"})
    fields_path = Path("/candidate/fields.inc")
    fields_path.write_text(
        "static const char* fieldNames[] = {\n"
        + ",\n".join(json.dumps(field) for field in sorted(fields))
        + "\n};\n"
    )
    bridge_binary = binaries / "spell-host-ipc"
    subprocess.run(
        flags
        + [
            str(bridge_source),
            "-L" + str(binaries),
            "-lspell_executor313",
            "-Wl,-rpath,$ORIGIN",
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-o",
            str(bridge_binary),
        ],
        check=True,
        timeout=120,
    )
    # Symbolize private executable offsets offline without changing dynamic
    # symbol interposition. Shared-library symbols are already discoverable.
    context_symbols = []
    for line in subprocess.check_output(
        ["nm", "-n", "-S", "--defined-only", str(binaries / "SPELL-Context")],
        text=True,
    ).splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] in {"T", "t", "W", "w"}:
            context_symbols.append([int(fields[0], 16), int(fields[1], 16), fields[3]])
    if len(context_symbols) > 20000:
        raise ValueError("Native diagnostic symbol inventory exceeds bound")
    report = dict(
        schema=1,
        native_start_qualified=False,
        native_prompt_hooks=args.native_prompts,
        native_terminal_hooks=args.native_terminal,
        full_v08_qualified=False,
        original_context_sha256=sha(runtime / "bin/SPELL-Context"),
        archive_sha256=sha(archive),
        original_unit_sha256=before,
        gate_sha256=sha(Path("/candidate/admission_gate.H")),
        candidate_context_sha256=programs["Context"],
        context_function_symbols=context_symbols,
        stream_header_sha256={
            name: sha(source / name)
            for name in (
                "include/SPELL_IPC/SPELLipcMessage.H",
                "include/SPELL_IPC/SPELLipcOutput.H",
                "include/SPELL_CTX/SPELLexecutorListener.H",
                "include/SPELL_CTX/SPELLexecutor.H",
                "include/SPELL_CTX/SPELLclientNotifier.H",
                "include/SPELL_CIFS/SPELLserverCif.H",
            )
        },
        candidate_executor_sha256=programs["Executor"],
        original_executor_sha256=sha(runtime / "bin/SPELL-Executor_v3"),
        candidate_shared_runtime_sha256=sha(shared),
        candidate_bridge_sha256=sha(bridge_binary),
        candidate_bridge_source_sha256=sha(bridge_source),
        candidate_bridge_fields_sha256=sha(fields_path),
        epoch_bootstrap_sha256=sha(Path("/candidate/epoch_connection.py")),
        original_shared_runtime_sha256=sha(runtime / "bin/libspell_executor313.so"),
        shared_runtime_library_units=len(runtime_graph),
        supplemental_units={path.name: sha(path) for path in support},
        graph_units={name: len(graph) for name, graph in graphs.items()},
        admission_headers={
            path.name: sha(path) for path in Path("/candidate").glob("*.H")
        },
        units=records,
        compiler=subprocess.check_output(["c++", "--version"], text=True).splitlines()[
            0
        ],
    )
    finalize_profile(home, programs, report, args.profile)
    (home / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.rmtree(source)


if __name__ == "__main__":
    main()
