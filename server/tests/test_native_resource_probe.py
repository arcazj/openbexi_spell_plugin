"""Host evidence separates resident, swapped and file-backed memory."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
from copy import deepcopy

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "resource_probe", ROOT / "scripts/v08_resource_probe.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def acceptance_evidence(tmp_path, mutate=None):
    records = []
    for second in range(0, 102, 2):
        records.append(
            dict(
                schema="openbexi.native-resources/1",
                container_id="original",
                pid=12,
                start_ticks=17,
                monotonic_ns=(second + 1) * 10**9,
                values={
                    "memory.max": 2 * 1024**3,
                    "memory.swap.max": 0,
                    "memory.current": 1200 * 1024**2,
                    "memory.peak": 1300 * 1024**2,
                    "memory.swap.current": 0,
                    "memory.events": {"max": 0, "oom": 0, "oom_kill": 0},
                },
            )
        )
    if mutate:
        mutate(records)
    (tmp_path / "native-resources.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (tmp_path / "native-resource-observer.json").write_text(
        json.dumps(dict(errors=[], container_id="original"))
    )
    (tmp_path / "native-recovery-soak.json").write_text(
        json.dumps(dict(start_ns=54 * 10**9, end_ns=99 * 10**9))
    )
    return records


def test_bounded_recovery_acceptance_requires_no_swap_and_stable_memory(tmp_path):
    acceptance_evidence(tmp_path)
    result = probe.assess_recovery_resources(tmp_path)
    assert result["passed"]
    assert result["duration_seconds"] == 45
    assert result["window_growth_bytes"] == 0
    assert result["full_v08_qualified"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("memory.max", 1024**3),
        ("memory.swap.max", 1024**3),
        ("memory.swap.current", 4096),
        ("memory.peak", 1800 * 1024**2),
        ("memory.current", "unknown"),
        ("memory.events", {"max": 1, "oom": 0, "oom_kill": 0}),
        ("memory.events", {"max": 0, "oom": 0, "oom_kill": 1}),
    ],
)
def test_recovery_rejects_pressure_swap_and_unverifiable_counters(tmp_path, field, value):
    acceptance_evidence(tmp_path, lambda rows: rows[5]["values"].update({field: value}))
    assert not probe.assess_recovery_resources(tmp_path)["passed"]


def test_recovery_rejects_growth_even_without_limit_or_oom_events(tmp_path):
    def grow(rows):
        for row in rows:
            row["values"]["memory.current"] += row["monotonic_ns"] // 10**9 * 3 * 1024**2

    acceptance_evidence(tmp_path, grow)
    result = probe.assess_recovery_resources(tmp_path)
    assert result["failures"] == ["native_recovery_memory_still_growing"]


@pytest.mark.parametrize(
    "fault", ["gap", "identity", "counter_missing", "end_missing", "bad_record"]
)
def test_recovery_rejects_incomplete_or_replaced_evidence(tmp_path, fault):
    def corrupt(rows):
        if fault == "gap":
            del rows[30:35]
        elif fault == "identity":
            rows[30]["start_ticks"] += 1
        elif fault == "counter_missing":
            del rows[30]["values"]["memory.swap.current"]
        elif fault == "end_missing":
            del rows[40:]
        else:
            rows.append({"observation_error": "OSError"})

    acceptance_evidence(tmp_path, corrupt)
    assert not probe.assess_recovery_resources(tmp_path)["passed"]


def test_recovery_verifier_does_not_mutate_sampled_values(tmp_path):
    records = acceptance_evidence(tmp_path)
    original = deepcopy(records)
    probe.assess_recovery_resources(tmp_path)
    assert records == original
    assert [
        json.loads(line) for line in (tmp_path / "native-resources.jsonl").read_text().splitlines()
    ] == original


def fixture(tmp_path):
    proc, group = tmp_path / "proc", tmp_path / "groups" / "worker"
    group.mkdir(parents=True)
    process = proc / "123"
    process.mkdir(parents=True)
    (process / "stat").write_text(
        "123 (name with ) brackets) " + " ".join(["S"] + ["1"] * 18 + ["42"])
    )
    (process / "cgroup").write_text("0::/worker\n")
    executable = tmp_path / "SPELL-Executor_v3"
    executable.touch()
    (process / "exe").symlink_to(executable)
    (process / "status").write_text(
        "VmRSS:\t256 kB\nRssAnon:\t200 kB\nVmSwap:\t128 kB\nThreads:\t3\nName:\tSECRET\n"
    )
    (process / "smaps_rollup").write_text(
        "Rss: 256 kB\nPss: 224 kB\nPss_Anon: 200 kB\nSwap: 128 kB\n"
    )
    (group / "cgroup.procs").write_text("123\n")
    for name, value in {
        "memory.current": "1048576",
        "memory.peak": "2097152",
        "memory.max": "4194304",
        "memory.swap.current": "131072",
        "memory.swap.max": "max",
        "memory.stat": "anon 204800\nfile 819200\nshmem 1024\n",
        "memory.events": "max 7\noom 0\noom_kill 0\n",
        "cpu.stat": "usage_usec 250\nthrottled_usec 100\n",
        "memory.pressure": "some avg10=0.02 avg60=0.01 avg300=0.00 total=100\nfull avg10=0.00 total=30\n",
    }.items():
        (group / name).write_text(value)
    return proc, group.parent


def test_snapshot_separates_rss_swap_file_and_pressure_without_reading_private_data(tmp_path):
    proc, groups = fixture(tmp_path)
    result = probe.snapshot(123, proc=proc, groups=groups)
    assert result["start_ticks"] == 42
    assert result["values"]["memory.current"] == 1048576
    assert result["values"]["memory.swap.max"] == "max"
    assert result["values"]["memory.stat"] == {"anon": 204800, "file": 819200, "shmem": 1024}
    assert result["values"]["memory.pressure"] == {"some": 100, "full": 30}
    row = result["processes"][0]
    assert row["status"]["VmRSS_bytes"] == 262144
    assert row["status"]["VmSwap_bytes"] == 131072
    assert row["smaps"]["Pss_bytes"] == 229376
    assert "memory.swap.peak" in result["unavailable"]
    assert "SECRET" not in json.dumps(result)


def test_exited_member_and_missing_smaps_are_explicit(tmp_path):
    proc, groups = fixture(tmp_path)
    (groups / "worker/cgroup.procs").write_text("123\n456\n")
    (proc / "123/smaps_rollup").unlink()
    result = probe.snapshot(123, proc=proc, groups=groups)
    assert result["processes"][0]["smaps_unavailable"] is True
    assert result["processes"][1] == dict(pid=456, exited_during_sample=True)


def test_container_executable_need_not_exist_in_host_mount_namespace(tmp_path):
    proc, groups = fixture(tmp_path)
    link = proc / "123/exe"
    link.unlink()
    link.symlink_to("/container-only/opt/runtime/SPELL-Executor_v3")
    result = probe.snapshot(123, proc=proc, groups=groups)
    assert result["processes"][0]["program"] == "SPELL-Executor_v3"
    assert result["processes"][0]["status"]["VmRSS_bytes"] == 262144


@pytest.mark.parametrize("cgroup", ["0::/../escape", "0::/worker\n1:cpu:/other"])
def test_cgroup_path_cannot_escape_bound_root(tmp_path, cgroup):
    proc, groups = fixture(tmp_path)
    (proc / "123/cgroup").write_text(cgroup)
    with pytest.raises(ValueError):
        probe.snapshot(123, proc=proc, groups=groups)


def test_recycled_pid_invalidates_observation(tmp_path, monkeypatch):
    proc, groups = fixture(tmp_path)
    calls = iter([42, 42, 43])
    monkeypatch.setattr(probe, "identity", lambda _: next(calls))
    with pytest.raises(ValueError, match="identity changed"):
        probe.snapshot(123, proc=proc, groups=groups)


def test_process_roster_is_bounded(tmp_path):
    proc, groups = fixture(tmp_path)
    (groups / "worker/cgroup.procs").write_text("123\n" * 257)
    with pytest.raises(ValueError, match="roster exceeds"):
        probe.snapshot(123, proc=proc, groups=groups)


def test_allocator_records_reject_non_numeric_or_extra_fields():
    record = dict(
        pid=7,
        role=1,
        monotonic_ns=10,
        allocated_bytes=1,
        heap_bytes=2,
        free_bytes=0,
        unmapped_bytes=0,
    )

    def line(value):
        return b"V08_MEMORY " + json.dumps(value).encode() + b"\n"

    assert probe.allocator_records(line(record)) == [record]
    for changed in [
        dict(record, secret="private"),
        dict(record, pid=True),
        dict(record, role=2),
        dict(record, heap_bytes=-1),
    ]:
        assert probe.allocator_records(line(changed)) == []
    newer = dict(record, monotonic_ns=20)
    assert probe.allocator_records(line(record) + line(newer)) == [newer]


def test_compiled_allocator_observation_preserves_live_and_freed_distinction(tmp_path):
    source, binary = tmp_path / "probe.cpp", tmp_path / "probe"
    source.write_text("""
#include "resource_trace.H"
#include "allocation_trace.H"
#include <thread>
#include <chrono>
int main() {
    if (!v08_allocation_profile_start()) return 3;
    v08_resource_trace(1);
    void* data = std::malloc(4*1024*1024);
    if (!data) return 2;
    std::memset(data, 1, 4*1024*1024);
    for (int n=0;n<100;n++) v08_resource_trace(1);
    std::this_thread::sleep_for(std::chrono::milliseconds(2100));
    v08_resource_trace(1);
    std::free(data);
    std::this_thread::sleep_for(std::chrono::milliseconds(2100));
    v08_resource_trace(1);
}
""")
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pthread",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=1")
    for enabled in (False, True):
        env["OPENBEXI_V08_RESOURCE_DIAGNOSTICS"] = "1" if enabled else "0"
        result = subprocess.run([str(binary)], env=env, capture_output=True, check=True, timeout=10)
        assert not result.stdout
        if not enabled:
            assert not result.stderr
            continue
        records = [
            json.loads(line[11:])
            for line in result.stderr.splitlines()
            if line.startswith(b"V08_MEMORY ")
        ]
        assert len(records) == 3
        baseline, live, freed = records
        assert live["allocated_bytes"] - baseline["allocated_bytes"] >= 4 * 1024 * 1024
        assert live["allocated_bytes"] - freed["allocated_bytes"] >= 4 * 1024 * 1024
        assert live["heap_bytes"] >= live["allocated_bytes"]
        assert freed["heap_bytes"] > freed["allocated_bytes"]


def allocation_sample(pid=7, tick=100):
    total = f"V08_ALLOC pid={pid} tick={tick} calls=80000 bytes=1234567 samples=300 skipped=2\n"
    sites = "".join(
        f"V08_ALLOC_SITE pid={pid} rank={rank} samples=20 bytes=2000"
        " | libasan.so.8+123:_Znwm | SPELL-Context+123abc:_ZN15SPELLipcMessage4dataEv\n"
        for rank in range(6)
    )
    return (total + sites).encode()


def test_allocation_profile_collector_keeps_only_latest_bounded_symbol_metadata():
    records = probe.allocation_profiles(allocation_sample() + allocation_sample(tick=200))
    assert len(records) == 1
    assert records[0]["monotonic_ns"] == 200
    assert records[0]["all_six_sites_observed"]
    assert len(records[0]["sites"]) == 6
    assert records[0]["sites"][0]["frames"][1]["offset"] == 0x123ABC
    assert probe.allocation_profiles(b"native user text, credentials and arguments") == []
    assert probe.allocation_profiles(allocation_sample(pid=2**31)) == []
    assert (
        len(probe.allocation_profiles(b"".join(allocation_sample(pid=n) for n in range(1, 40))))
        == 32
    )
    partial = allocation_sample().split(b"V08_ALLOC_SITE")[0]
    assert not probe.allocation_profiles(partial)[0]["all_six_sites_observed"]


@pytest.mark.parametrize(
    "invalid",
    [b"procedure secret", b"/private/path", b"bad\x00symbol", b"x" * 101],
)
def test_allocation_profile_rejects_arbitrary_log_payload(invalid):
    raw = allocation_sample().replace(b"_ZN15SPELLipcMessage4dataEv", invalid)
    assert probe.allocation_profiles(raw)[0]["sites"] == []


def test_snapshot_retains_allocation_sites_only_for_observed_original_process(tmp_path):
    proc, groups = fixture(tmp_path)
    status = proc / "123/status"
    status.write_text(status.read_text() + "NSpid:\t123\t7\n")
    log = proc / "123/root/tmp/spell-host-fixture/native.log"
    log.parent.mkdir(parents=True)
    log.write_bytes(allocation_sample() + allocation_sample(pid=999))
    records = probe.snapshot(123, proc=proc, groups=groups)["native_allocation_profiles"]
    assert len(records) == 1 and records[0]["pid"] == 7
    assert records[0]["all_six_sites_observed"]
