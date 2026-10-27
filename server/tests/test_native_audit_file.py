"""Real files, process restart, concurrent writes and kernel I/O refusal."""

import importlib.util
import os
import signal
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def audit_binary(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-audit")
    binary = folder / "audit"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-DV08_AUDIT_FAULT_WRAPPERS=1",
            "-Wl,--wrap=write,--wrap=fdatasync",
            "-I" + str(ROOT / "host_runtime/native"),
            str(ROOT / "server/tests/native_audit_file.cpp"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return binary


def environment():
    return dict(
        os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=1", UBSAN_OPTIONS="halt_on_error=1"
    )


def run(binary, *args):
    return subprocess.run(
        [str(binary), *map(str, args)], capture_output=True, timeout=30, env=environment()
    )


def test_concurrent_completeness_ordering_and_process_restart(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, "normal", path)
    assert result.returncode == 0, result.stderr
    lines = path.read_text().splitlines()
    assert len(lines) == 400 and len(set(lines)) == 400
    for thread in range(4):
        assert [int(line.split(":")[1]) for line in lines if line.startswith(f"{thread}:")] == list(
            range(100)
        )
    before = path.read_bytes()
    result = run(audit_binary, "append", path)
    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == before + b"RESTART\n"


def test_reset_and_restore_preserve_original_generations(audit_binary, tmp_path):
    path, snapshot = tmp_path / "execution.ASRUN", tmp_path / "snapshot"
    assert run(audit_binary, "normal", path).returncode == 0
    original = path.read_bytes()
    assert run(audit_binary, "new", path).returncode == 0
    assert path.read_bytes() == b"NEW\n"
    assert (tmp_path / "execution.ASRUN.archive.0").read_bytes() == original
    snapshot.write_bytes(b"SNAPSHOT\n")
    assert run(audit_binary, "restore", path, snapshot).returncode == 0
    assert path.read_bytes() == b"SNAPSHOT\n"
    assert (tmp_path / "execution.ASRUN.archive.1").read_bytes() == b"NEW\n"
    assert (tmp_path / "execution.ASRUN.archive.0").read_bytes() == original


@pytest.mark.parametrize("partial", [False, True])
def test_sigkill_preserves_acknowledgements_and_uncertain_tail(audit_binary, tmp_path, partial):
    path = tmp_path / "execution.ASRUN"
    process = subprocess.Popen(
        [str(audit_binary), "partial-crash" if partial else "acknowledged-crash", str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment(),
    )
    try:
        assert process.stdout.readline() == (b"PARTIAL\n" if partial else b"ACK 128\n")
        process.kill()
        _, diagnostic = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert process.returncode == -signal.SIGKILL and not diagnostic
    original = (
        b"BASE\nUNCERTAI" if partial else b"".join(f"COMMITTED:{i}\n".encode() for i in range(128))
    )
    assert path.read_bytes() == original
    result = run(audit_binary, "append", path)
    if partial:
        assert result.returncode == 74 and b"stage=incomplete_tail" in result.stderr
        assert path.read_bytes() == original
        assert run(audit_binary, "new", path).returncode == 0
        assert (tmp_path / "execution.ASRUN.archive.0").read_bytes() == original
    else:
        assert result.returncode == 0
        assert path.read_bytes() == original + b"RESTART\n"


def test_incomplete_tail_is_preserved_and_rejected_on_append(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    path.write_bytes(b"COMMITTED\nUNCERTAIN")
    path.chmod(0o600)
    result = run(audit_binary, "append", path)
    assert result.returncode == 74 and b"stage=incomplete_tail" in result.stderr
    assert path.read_bytes() == b"COMMITTED\nUNCERTAIN"


def test_kernel_file_limit_refuses_writes_without_false_ack(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, "quota", path)
    assert result.returncode == 74 and b"stage=write" in result.stderr
    accepted = len(result.stdout.splitlines())
    assert accepted == 16
    assert path.read_bytes() == b"".join(
        f"{i:016d}".encode() + b"x" * (4095 - 16) + b"\n" for i in range(accepted)
    )


@pytest.mark.parametrize(
    "mode,stage",
    [("interrupted", None), ("partial-failure", b"write"), ("sync-failure", b"record_sync")],
)
def test_interrupted_partial_and_uncertain_sync_behavior(audit_binary, tmp_path, mode, stage):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, mode, path)
    if stage is None:
        assert result.returncode == 0 and result.stdout == b"ACK\n"
        assert path.read_bytes() == b"BASE\nUNCERTAIN-RECORD\n"
    else:
        assert result.returncode == 74 and b"stage=" + stage in result.stderr
        assert not result.stdout
        contents = path.read_bytes()
        assert contents.startswith(b"BASE\n")
        if mode == "partial-failure":
            assert contents == b"BASE\nUNCERTAI"
        else:
            assert contents == b"BASE\nUNCERTAIN-RECORD\n"


def test_other_process_cannot_replace_an_active_writer(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    holder = subprocess.Popen(
        [str(audit_binary), "hold", str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment(),
    )
    try:
        assert holder.stdout.readline() == b"READY\n"
        for mode in ["new", "append"]:
            result = run(audit_binary, mode, path)
            assert result.returncode == 74 and b"stage=writer_lock" in result.stderr
        assert not list(tmp_path.glob("*.archive.*"))
    finally:
        holder.communicate(b"x", timeout=10)
    assert holder.returncode == 0


@pytest.mark.parametrize("symlink", [False, True])
def test_directory_and_symlink_policy_fails_closed(audit_binary, tmp_path, symlink):
    path = tmp_path / "execution.ASRUN"
    if symlink:
        target = tmp_path / "target"
        target.write_bytes(b"ORIGINAL\n")
        path.symlink_to(target)
    else:
        tmp_path.chmod(0o755)
    result = run(audit_binary, "new", path)
    assert result.returncode == 74
    if symlink:
        assert target.read_bytes() == b"ORIGINAL\n"


@pytest.fixture(scope="module")
def asrun_source(tmp_path_factory):
    folder = tmp_path_factory.mktemp("asrun-composition")
    source = folder / "source"
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(source)
    saved = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, archive, folder / "composition")
    finally:
        sys.path[:] = saved
    spec = importlib.util.spec_from_file_location(
        "asrun_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.reuse_native_timestamp_and_asrun(source)
    builder.durable_native_asrun(source)
    return source, builder


def test_exact_asrun_sequence_format_and_concurrent_reset_history(asrun_source, tmp_path):
    source, _ = asrun_source
    text = (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_text()
    bodies = []
    for method in ["toAsRun", "writeLine", "clear"]:
        start = text.index("void SPELLasRun::" + method + "(")
        bodies.append(text[start : text.index("\n}", start) + 2])
    (tmp_path / "asrun.inc").write_text("\n".join(bodies))
    (tmp_path / "main.cpp").write_text("""
#include "audit_file.H"
#include <thread>
#include <vector>
#define STR(x) std::string(x)
#define ISTR(x) std::to_string(x)
struct SPELLutils {static void timestamp(std::string& output){output="STAMP";}};
class SPELLasRun {
    V08AuditFile m_file;std::recursive_mutex m_v08RecordMutex;std::string m_v08Record;
    std::string m_fileName;unsigned long m_sequence=0;
public:
    explicit SPELLasRun(const std::string& path):m_fileName(path){m_file.open(path);toAsRun("INIT",true);}
    void toAsRun(const std::string&,bool);
    void writeLine(const std::string&);
    void clear();
};
#include "asrun.inc"
int main(int argc,char** argv){
    if(argc!=2)return 2;
    SPELLasRun output(argv[1]);std::vector<std::thread> threads;
    for(int t=0;t<4;++t)threads.emplace_back([&,t]{
        for(int n=0;n<100;++n)output.writeLine(std::to_string(t)+":"+std::to_string(n));
    });
    for(auto& thread:threads)thread.join();
    output.clear();output.writeLine("AFTER_RESET");
}
""")
    binary = tmp_path / "asrun"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(ROOT / "host_runtime/native"),
            "-I" + str(tmp_path),
            str(tmp_path / "main.cpp"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    path = tmp_path / "execution.ASRUN"
    result = subprocess.run(
        [str(binary), str(path)], capture_output=True, timeout=30, env=environment()
    )
    assert result.returncode == 0, result.stderr
    before = (tmp_path / "execution.ASRUN.archive.0").read_text().splitlines()
    assert before[0] == "STAMP\t0\tINIT"
    assert [int(line.split("\t")[1]) for line in before] == list(range(401))
    assert all(line.split("\t")[2:4] == ["LINE", ""] for line in before[1:])
    assert len({line.split("\t")[-1] for line in before[1:]}) == 400
    assert path.read_text() == "STAMP\t0\tINIT\nSTAMP\t1\tLINE\t\tAFTER_RESET\n"


def test_durable_overlay_rejects_duplicate_without_changing_files(asrun_source):
    source, builder = asrun_source
    header = (source / "include/SPELL_CIF/SPELLasRun.H").read_bytes()
    unit = (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_bytes()
    with pytest.raises(ValueError, match="preimage differs"):
        builder.durable_native_asrun(source)
    assert (source / "include/SPELL_CIF/SPELLasRun.H").read_bytes() == header
    assert (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_bytes() == unit
