"""Reproduce the installed Context graph, then add the before-spawn gate.

Uses the frozen runtime's own complete source/recipe provenance. No old binary
is edited or interposed, and the new Context requires independent qualification.
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

import spell_native


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
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
    unit.write_text(text)
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
    makefile = source / "src/context/Makefile.am"
    logical = makefile.read_text().replace("\\\n", " ")
    dependencies = re.findall(r"^SPELL_Context_LDADD\s*=\s*([^\n]+)", logical, re.M)
    mains = re.findall(r"^SPELL_Context_SOURCES\s*=\s*([^\n]+)", logical, re.M)
    if len(dependencies) != 1 or len(mains) != 1:
        raise ValueError("Ambiguous original Context manifest")
    names = re.findall(r"/lib/(SPELL_\w+)/lib\1_v[23]\.la", dependencies[0])
    library = libraries(source)
    units = [source / p for name in names for p in library[name]["units"]]
    units += [makefile.parent / name for name in mains[0].split()]
    if not units or len(units) != len(set(units)):
        raise ValueError("Invalid Context source graph")

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
        if child.name != "SPELL-Context":
            (binaries / child.name).symlink_to(child)
    program = binaries / "SPELL-Context"
    subprocess.run(
        [
            "c++",
            "-pthread",
            "-fsanitize=address,undefined",
            "-Wl,--no-undefined",
            *[row["object"] for row in records],
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
    report = dict(
        schema=1,
        native_start_qualified=False,
        full_v08_qualified=False,
        original_context_sha256=sha(runtime / "bin/SPELL-Context"),
        archive_sha256=sha(archive),
        original_unit_sha256=before,
        gate_sha256=sha(Path("/candidate/admission_gate.H")),
        candidate_context_sha256=sha(program),
        units=records,
        compiler=subprocess.check_output(["c++", "--version"], text=True).splitlines()[
            0
        ],
    )
    (home / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.rmtree(source)


if __name__ == "__main__":
    main()
