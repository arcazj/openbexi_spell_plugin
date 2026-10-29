"""Real files, process restart, concurrent writes and kernel I/O refusal."""

import hashlib
import importlib.util
import json
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
            "-Wl,--wrap=write,--wrap=fdatasync,--wrap=posix_fadvise,--wrap=flock",
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


def test_synced_audit_cache_is_bounded_without_losing_records(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, "cache-probe", path)
    assert result.returncode == 0, result.stderr
    marker, cached, pages = result.stdout.split()
    assert marker == b"CACHE" and int(pages) >= 1024
    assert int(cached) * os.sysconf("SC_PAGE_SIZE") <= 65536
    with path.open("rb") as stream:
        for _ in range(1024):
            assert stream.readline() == b"z" * 65535 + b"\n"
        assert stream.read(1) == b""


def test_refused_cache_policy_fails_without_ack_or_record_deletion(audit_binary, tmp_path):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, "cache-refusal", path)
    assert result.returncode == 74 and b"stage=cache_advice errno=95" in result.stderr
    assert not result.stdout
    assert path.read_bytes() == b"z" * 65535 + b"\n"


def test_successful_advisory_noop_is_revisited_with_all_audit_bytes_retained(
    audit_binary, tmp_path
):
    path = tmp_path / "execution.ASRUN"
    result = run(audit_binary, "cache-revisit", path)
    assert result.returncode == 0, result.stderr
    revisited, cached = result.stdout.splitlines()
    assert revisited == b"REVISITED 1"
    marker, resident, pages = cached.split()
    assert marker == b"CACHE" and int(pages) == 16384
    assert int(resident) * os.sysconf("SC_PAGE_SIZE") <= 65536
    with path.open("rb") as stream:
        for _ in range(1024):
            assert stream.readline() == b"z" * 65535 + b"\n"
        assert stream.read(1) == b""


def test_large_restore_keeps_bytes_and_bounds_output_cache(audit_binary, tmp_path):
    path, snapshot = tmp_path / "execution.ASRUN", tmp_path / "snapshot.ASRUN"
    with snapshot.open("wb") as stream:
        for _ in range(1024):
            stream.write(b"q" * 65535 + b"\n")
        stream.flush()
        os.fdatasync(stream.fileno())
    snapshot.chmod(0o600)
    result = run(audit_binary, "cache-restore", path, snapshot)
    assert result.returncode == 0, result.stderr
    marker, cached, pages = result.stdout.split()
    assert marker == b"CACHE" and int(pages) >= 1024
    assert int(cached) * os.sysconf("SC_PAGE_SIZE") <= 65536
    with path.open("rb") as restored, snapshot.open("rb") as original:
        for _ in range(1024):
            expected = b"q" * 65535 + b"\n"
            assert restored.readline() == expected and original.readline() == expected
        assert restored.read(1) == original.read(1) == b""


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


@pytest.mark.parametrize("mode", ["delayed-append", "delayed-new"])
def test_opened_old_inode_cannot_mutate_an_archived_generation(audit_binary, tmp_path, mode):
    path = tmp_path / "execution.ASRUN"
    assert run(audit_binary, "new", path).returncode == 0
    stale = subprocess.Popen(
        [str(audit_binary), mode, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment(),
    )
    current = None
    try:
        # Keep the real old fd open across another writer's complete generation
        # transition. The wrapper only delays flock; all filesystem calls run.
        assert stale.stdout.readline() == b"OPENED_BEFORE_LOCK\n"
        current = subprocess.Popen(
            [str(audit_binary), "hold-record", str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment(),
        )
        assert current.stdout.readline() == b"READY\n"
        output, diagnostic = stale.communicate(b"x", timeout=10)
        (tmp_path / "stale.stdout").write_bytes(output)
        (tmp_path / "stale.stderr").write_bytes(diagnostic)
        (tmp_path / "stale.exit").write_text(str(stale.returncode) + "\n")
        assert stale.returncode == 74 and b"stage=writer_identity" in diagnostic
        assert not output
        assert path.read_bytes() == b"CURRENT\n"
        assert (tmp_path / "execution.ASRUN.archive.0").read_bytes() == b"NEW\n"
        assert len(list(tmp_path.glob("*.archive.*"))) == 1
    finally:
        if stale.poll() is None:
            stale.kill()
            stale.communicate(timeout=10)
        if current is not None:
            current.communicate(b"x", timeout=10)
    assert current.returncode == 0


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
    baseline = source / "lib/SPELL_CIF/src/SPELLasRun.C"
    (folder / "asrun-before-line-reuse.C").write_bytes(baseline.read_bytes())
    builder.reuse_native_line_record(source)
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


def test_actual_line_methods_preserve_all_records_and_remove_payload_allocations(
    asrun_source, tmp_path
):
    source, _ = asrun_source
    before = (source.parent / "asrun-before-line-reuse.C").read_text()
    after = (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_text()
    results = {}
    for mode, text in (("before", before), ("after", after)):
        bodies = []
        for name in ("toAsRun", "writeLine"):
            start = text.index("void SPELLasRun::" + name + "(")
            body = text[start : text.index("\n}", start) + 2]
            bodies.append(body)
            if mode == "before" and name == "writeLine":
                assert hashlib.sha256(body.encode()).hexdigest() == (
                    "a20bb8483f77cd2b9b752ae9c52530954486b06a51ae7710b11bdd3bc662507b"
                )
        folder = tmp_path / mode
        folder.mkdir(mode=0o700)
        (folder / "asrun-line.inc").write_text("\n".join(bodies))
        binary = folder / "line"
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
                "-I" + str(ROOT / "host_runtime/native"),
                "-I" + str(folder),
                str(ROOT / "server/tests/native_asrun_line.cpp"),
                "-o",
                str(binary),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        output = folder / "all-records.ASRUN"
        completed = subprocess.run(
            [str(binary), str(output)], capture_output=True, timeout=60, env=environment()
        )
        assert completed.returncode == 0, completed.stderr
        results[mode] = json.loads(completed.stdout)
        (folder / "measurement.json").write_text(json.dumps(results[mode], indent=2) + "\n")
        assert results[mode]["acknowledged_records"] == 10004
        assert results[mode]["all_sequences_advanced"] is True
    original = (tmp_path / "before/all-records.ASRUN").read_bytes()
    assert (tmp_path / "after/all-records.ASRUN").read_bytes() == original
    lines = original.splitlines()
    assert len(lines) == 10005
    assert [int(line.split(b"\t")[1]) for line in lines] == list(range(10005))
    assert all(
        line.endswith(b"\tLINE\t\thandoff.py:44:original-progress") for line in lines[1:10001]
    )
    assert lines[10001].endswith(b"\tLINE\t\t")
    assert lines[10002].endswith(b"\tLINE\t\tUTF8-\xc3\xa9-\xe2\x98\x83")
    assert lines[10003].endswith(b"\tLINE\t\t" + b"x" * 8193)
    assert lines[10004].endswith(b"\tLINE\t\tAFTER_OVERSIZED")
    assert results["before"]["measured_allocations"] >= 10000
    assert results["after"]["measured_allocations"] <= 2
    assert results["after"]["retained_prefix_capacity"] <= 1024


@pytest.mark.parametrize("drift", [False, True])
def test_line_overlay_rejects_drift_or_reapplication_without_writes(asrun_source, tmp_path, drift):
    source, builder = asrun_source
    path = tmp_path / "lib/SPELL_CIF/src/SPELLasRun.C"
    path.parent.mkdir(parents=True)
    path.write_bytes((source / "lib/SPELL_CIF/src/SPELLasRun.C").read_bytes())
    if drift:
        original = (source.parent / "asrun-before-line-reuse.C").read_text()
        path.write_text(original.replace('STR("LINE")', 'STR("CHANGED")'))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="LINE audit preimage differs"):
        builder.reuse_native_line_record(tmp_path)
    assert path.read_bytes() == before
