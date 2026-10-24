"""Reproduce the installed Context/Executor graphs, then add native admission.

Uses the frozen runtime's own complete source/recipe provenance. No old binary
is edited or interposed, and both new programs require independent qualification.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_native_tree(source):
    """Apply only to the independently reproduced frozen composition."""
    unit = source / "lib/SPELL_CTX/src/SPELLexecutor.C"
    before = sha(unit)
    if before != "e8d1c0ed2ee9b66894add739f3b0a0f880a1a2f59bc50034dde5050117fec598":
        raise ValueError("Before-spawn native preimage differs")
    text = unit.read_text()
    anchor = "void SPELLexecutor::start()\n{\n"
    if text.count(anchor) != 1:
        raise ValueError("Ambiguous native start boundary")
    # Exceptions must cross the legacy Context's original SPELLcoreException
    # handler, rather than terminate an IPC thread with std::runtime_error.
    text = text.replace(
        anchor,
        anchor
        + """    try { v08_admit_native_start(m_model, m_reconnecting); }
    catch (const std::exception&) {
        THROW_EXCEPTION("Native start denied", "Context admission unavailable or rejected", SPELL_ERROR_PROCESS);
    }
""",
    )
    include = '#include "SPELL_CTX/SPELLexecutor.H"'
    text = text.replace(include, include + '\n#include "/candidate/admission_gate.H"')
    forward_anchor = (
        "void SPELLexecutor::sendMessageToExecutor( const SPELLipcMessage& msg )\n{\n"
    )
    if text.count(forward_anchor) != 1:
        raise ValueError("Ambiguous native Executor forwarding boundary")
    text = text.replace(
        forward_anchor,
        forward_anchor
        + """    try { v08_admit_native_run(m_model, msg); }
    catch (const std::exception&) {
        LOG_ERROR("Native RUN forwarding denied by Context admission");
        return;
    }
""",
    )
    bind_anchor = "\t\t\tm_model.setPID( SPELLprocessManager::instance().getProcessId( m_model.getInstanceId() ));"
    if text.count(bind_anchor) != 1:
        raise ValueError("Ambiguous native Executor PID binding")
    text = text.replace(
        bind_anchor,
        bind_anchor
        + """
            try { v08_bind_native_executor(m_model); }
            catch (const std::exception&) {
                THROW_EXCEPTION("Native Executor denied", "Executor identity binding unavailable or rejected", SPELL_ERROR_PROCESS);
            }
""",
    )
    unit.write_text(text)
    # Carry the immutable request through value copies in both the mailbox and
    # trace-deferred commands, then check at executeCommand before RUN effects.
    command = source / "include/SPELL_EXC/SPELLcommand.H"
    command_text = command.read_text()
    if command_text.count("    std::string earg;") != 1:
        raise ValueError("Ambiguous native command representation")
    command.write_text(
        command_text.replace(
            "    std::string earg;",
            "    std::string earg;\n    std::string v08Request;",
        )
    )
    cif = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    cif_text = cif.read_text()
    marker = "    cmd.id = msgId;"
    if cif_text.count(marker) != 1:
        raise ValueError("Ambiguous native command decoding")
    cif.write_text(
        cif_text.replace(
            marker,
            marker
            + '\n    if (msg.hasField("V08ControlRequest")) cmd.v08Request = msg.get("V08ControlRequest");',
        )
    )
    controller = source / "lib/SPELL_EXC/src/SPELLcontroller.C"
    controller_text = controller.read_text()
    controller_text = controller_text.replace(
        '#include "SPELL_EXC/SPELLcommand.H"',
        '#include "SPELL_EXC/SPELLcommand.H"\n#include "/candidate/execution_gate.H"',
    )
    execute = "void SPELLcontroller::executeCommand( const ExecutorCommand& cmd )\n{\n"
    autorun = "void SPELLcontroller::setAutoRun()\n{\n"
    if controller_text.count(execute) != 1 or controller_text.count(autorun) != 1:
        raise ValueError("Ambiguous native command consumption boundary")
    controller_text = controller_text.replace(
        execute,
        execute
        + """    try { v08_consume_native_run(m_procId, cmd); }
    catch (const std::exception&) {
        LOG_ERROR("Native RUN consumption denied by Context admission");
        return;
    }
""",
    )
    # Hidden automatic children use the same admitted initial RUN as visible
    # children. They must reach the normal initial pause before executing code.
    controller.write_text(
        controller_text.replace(
            autorun,
            autorun
            + '    LOG_INFO("Native automatic RUN deferred to admitted command");\n    return;\n',
        )
    )
    service = source / "lib/SPELL_CTX/src/SPELLservice.C"
    if (
        sha(service)
        != "37e4c2b4df2ba39f7da81c21b25d10913e44ba8bac88fca1a3839e7d1e3bb2a3"
    ):
        raise ValueError("Native service-start preimage differs")
    service_anchor = "void SPELLservice::start()\n{\n"
    service_text = service.read_text()
    if service_text.count(service_anchor) != 1:
        raise ValueError("Ambiguous native service-start boundary")
    service.write_text(
        service_text.replace(
            service_anchor,
            service_anchor
            + """    THROW_EXCEPTION("Native service start denied", "Services are unqualified in the child admission profile", SPELL_ERROR_PROCESS);
""",
        )
    )
    return before


def native_graph(source, libraries, program):
    makefile = source / ("src/" + program.lower() + "/Makefile.am")
    logical = makefile.read_text().replace("\\\n", " ")
    name = "SPELL_" + program
    dependencies = re.findall(r"^" + name + r"_LDADD\s*=\s*([^\n]+)", logical, re.M)
    mains = re.findall(r"^" + name + r"_SOURCES\s*=\s*([^\n]+)", logical, re.M)
    if len(dependencies) != 1 or len(mains) != 1:
        raise ValueError("Ambiguous original native manifest")
    names = re.findall(r"/lib/(SPELL_\w+)/lib\1_v[23]\.la", dependencies[0])
    library = libraries(source)
    units = [source / p for name in names for p in library[name]["units"]]
    units += [makefile.parent / name for name in mains[0].split()]
    if not units or len(units) != len(set(units)):
        raise ValueError("Invalid native source graph")
    return units


def main():
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
    before = patch_native_tree(source)
    build = Path("/tmp/v08-context-objects")
    build.mkdir()
    flags = [
        "c++",
        "-std=c++17",
        "-fPIC",
        "-g",
        "-O1",
        "-pthread",
        "-fmax-errors=4",
        "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all",
        "-fno-omit-frame-pointer",
        "-I" + str(source / "include"),
        "-I" + sysconfig.get_path("include"),
    ]
    graphs = {
        name: native_graph(source, libraries, name) for name in ("Context", "Executor")
    }
    units = sorted(set(path for graph in graphs.values() for path in graph))

    def compile_unit(path):
        name = path.relative_to(source).as_posix()
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
        if child.name not in {"SPELL-Context", "SPELL-Executor", "SPELL-Executor_v3"}:
            (binaries / child.name).symlink_to(child)
    indexed = {row["unit"]: row["object"] for row in records}
    programs = {}
    for name, graph in graphs.items():
        program = binaries / ("SPELL-" + name)
        subprocess.run(
            [
                "c++",
                "-pthread",
                "-fsanitize=address,undefined",
                "-Wl,--no-undefined",
                *[indexed[path.relative_to(source).as_posix()] for path in graph],
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
    report = dict(
        schema=1,
        native_start_qualified=False,
        full_v08_qualified=False,
        original_context_sha256=sha(runtime / "bin/SPELL-Context"),
        archive_sha256=sha(archive),
        original_unit_sha256=before,
        gate_sha256=sha(Path("/candidate/admission_gate.H")),
        candidate_context_sha256=programs["Context"],
        candidate_executor_sha256=programs["Executor"],
        original_executor_sha256=sha(runtime / "bin/SPELL-Executor"),
        graph_units={name: len(graph) for name, graph in graphs.items()},
        admission_headers={
            path.name: sha(path) for path in Path("/candidate").glob("*.H")
        },
        units=records,
        compiler=subprocess.check_output(["c++", "--version"], text=True).splitlines()[
            0
        ],
    )
    (home / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.rmtree(source)


if __name__ == "__main__":
    main()
