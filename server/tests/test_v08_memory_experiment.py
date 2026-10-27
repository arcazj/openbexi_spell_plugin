"""Independent comparison profiles cannot silently qualify the no-swap release gate."""

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/v08_memory_experiment.py"
spec = importlib.util.spec_from_file_location("memory_experiment", MODULE)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
MIB = 1024**2
GIB = 1024**3


def evidence(folder, profile="asan-noswap", seconds=300, mutate=None):
    rows = []
    for tick in range(0, seconds + 40, 2):
        processes = [
            {
                "pid": i + 1,
                "start_ticks": 77 + i,
                "program": name,
                "native_maps_observed": True,
                "sanitizer_mapped": profile != "optimized-noswap",
            }
            for i, name in enumerate(
                (
                    "docker-init",
                    "python",
                    "SPELL-Listener",
                    "SPELL-Context",
                    "spell-host-ipc",
                    "spell-host-ipc",
                    "SPELL-Executor",
                    "SPELL-Executor",
                )
            )
        ]
        rows.append(
            {
                "schema": "openbexi.native-resources/1",
                "container_id": "original",
                "pid": 11,
                "start_ticks": 99,
                "monotonic_ns": tick * 10**9,
                "processes": processes,
                "values": {
                    "memory.max": 2 * GIB,
                    "memory.peak": 1200 * MIB,
                    "memory.current": 1100 * MIB,
                    "memory.swap.max": 2 * GIB if profile == "asan-swap" else 0,
                    "memory.swap.current": 128 * MIB if profile == "asan-swap" else 0,
                    "memory.events": {"max": 0, "oom": 0, "oom_kill": 0},
                    "memory.swap.events": {"fail": 0},
                },
            }
        )
    if mutate:
        mutate(rows)
    folder.mkdir(exist_ok=True)
    (folder / "native-resources.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (folder / "native-resource-observer.json").write_text(
        json.dumps({"container_id": "original", "errors": []})
    )
    (folder / "native-recovery-soak.json").write_text(
        json.dumps(
            {
                "start_ns": 20 * 10**9,
                "end_ns": (20 + seconds) * 10**9,
                "original_processes": 8,
                "all_intervals_advanced": True,
            }
        )
    )
    return rows


@pytest.mark.parametrize("profile", experiment.PROFILES)
@pytest.mark.parametrize("seconds", [45, 60, 300])
def test_comparison_success_is_never_a_release_receipt(tmp_path, profile, seconds):
    evidence(tmp_path, profile, seconds)
    result = experiment.assess_experiment(tmp_path, profile, seconds)
    assert result["passed"]
    assert result["schema"] != "openbexi.native-recovery-resources/1"
    assert result["diagnostic_only"]
    assert not result["full_v08_qualified"]
    assert not result["eligible_for_publication"]
    assert result["swap_exercised"] == (profile == "asan-swap")
    assert result["duration_seconds"] == seconds


@pytest.mark.parametrize("profile", experiment.PROFILES)
@pytest.mark.parametrize(
    "fault",
    [
        "oom",
        "pressure",
        "identity",
        "roster",
        "map_missing",
        "wrong_instrumentation",
        "gap",
        "bad_counter",
        "bad_limit",
        "swap_failure",
        "missing_role",
        "swap_above_limit",
        "last_samples_missing",
    ],
)
def test_profile_rejects_corrupt_or_unsafe_evidence(tmp_path, profile, fault):
    def corrupt(rows):
        row = rows[50]
        if fault == "oom":
            row["values"]["memory.events"]["oom_kill"] = 1
        elif fault == "pressure":
            row["values"]["memory.events"]["oom"] = 1
        elif fault == "identity":
            row["start_ticks"] += 1
        elif fault == "roster":
            row["processes"][2]["start_ticks"] += 1
        elif fault == "map_missing":
            del row["processes"][3]["native_maps_observed"]
        elif fault == "wrong_instrumentation":
            row["processes"][3]["sanitizer_mapped"] = profile == "optimized-noswap"
        elif fault == "gap":
            del rows[30:35]
        elif fault == "bad_counter":
            row["values"]["memory.current"] = True
        elif fault == "bad_limit":
            row["values"]["memory.max"] = 3 * GIB
        elif fault == "swap_failure":
            row["values"]["memory.swap.events"]["fail"] = 1
        elif fault == "missing_role":
            for r in rows:
                r["processes"][3]["program"] = "other"
        elif fault == "swap_above_limit":
            row["values"]["memory.swap.current"] = 3 * GIB
        elif fault == "last_samples_missing":
            del rows[-20:]

    evidence(tmp_path, profile, mutate=corrupt)
    assert not experiment.assess_experiment(tmp_path, profile, 300)["passed"]


def test_swapping_out_memory_cannot_hide_combined_growth(tmp_path):
    def grow(rows):
        for i, row in enumerate(rows):
            row["values"]["memory.current"] -= i * MIB
            row["values"]["memory.swap.current"] += 3 * i * MIB

    evidence(tmp_path, "asan-swap", mutate=grow)
    result = experiment.assess_experiment(tmp_path, "asan-swap", 300)
    assert not result["passed"]
    assert "combined_memory_still_growing" in result["failures"]


def test_swap_capacity_without_use_is_not_evidence_of_benefit(tmp_path):
    evidence(
        tmp_path,
        "asan-swap",
        mutate=lambda rows: [r["values"].update({"memory.swap.current": 0}) for r in rows],
    )
    result = experiment.assess_experiment(tmp_path, "asan-swap", 300)
    assert result["passed"]
    assert not result["swap_exercised"]


def test_baseline_still_rejects_swap_and_keeps_original_thresholds(tmp_path):
    oldspec = importlib.util.spec_from_file_location(
        "unchanged_resource_probe", ROOT / "scripts/v08_resource_probe.py"
    )
    original = importlib.util.module_from_spec(oldspec)
    oldspec.loader.exec_module(original)
    evidence(tmp_path, "asan-swap", 45)
    result = original.assess_recovery_resources(tmp_path)
    assert not result["passed"]
    assert result["swap_limit_bytes"] == 0
    assert result["peak_budget_bytes"] == 1792 * MIB
    assert result["maximum_window_growth_bytes"] == 64 * MIB


def source_copy(folder):
    for relative in experiment.PREIMAGES:
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, path)


@pytest.mark.parametrize("profile", experiment.PROFILES)
@pytest.mark.parametrize("seconds", [45, 300])
def test_exact_overlay_compiles_and_only_changes_the_experiment(tmp_path, profile, seconds):
    source_copy(tmp_path)
    before = {p: (ROOT / p).read_bytes() for p in experiment.PREIMAGES}
    receipt = experiment.prepare_overlay(tmp_path, profile, seconds)
    assert receipt
    for relative, data in before.items():
        assert (ROOT / relative).read_bytes() == data
        modified = (tmp_path / relative).read_bytes()
        if relative in receipt:
            assert receipt[relative]["before_sha256"] == hashlib.sha256(data).hexdigest()
            assert receipt[relative]["after_sha256"] == hashlib.sha256(modified).hexdigest()
        if relative.endswith(".py"):
            compile(modified, relative, "exec")
    builder = (tmp_path / "host_runtime/build_admission_context.py").read_text()
    consume = (tmp_path / "scripts/v08_native_consumption.py").read_text()
    assert builder == before["host_runtime/build_admission_context.py"].decode()
    launch = (tmp_path / "scripts/qualify_v08_native_launch.py").read_text()
    if profile in {"optimized-noswap", "asan-o2-noswap"}:
        assert "build_native_profile.py" in launch
        assert "build.py --profile" in launch
        stable = (tmp_path / "host_runtime/build_native_profile.py").read_text()
        assert '"-O2"' in stable and "readelf" in stable
        assert 'for name in ("Context", "Executor", "Listener")' in stable
    if profile == "asan-swap":
        assert '"--memory-swap",\n            "4096m"' in consume
    else:
        assert '"--memory-swap",\n            "2048m"' in consume
    # No mutation of controller timeouts, capabilities or effect replay code.
    assert "expected_epoch" in consume


def test_source_drift_is_rejected_before_any_overlay_writes(tmp_path):
    source_copy(tmp_path)
    changed = tmp_path / "host_runtime/native/resource_trace.H"
    changed.write_text(changed.read_text() + "\n")
    before = {p: (tmp_path / p).read_bytes() for p in experiment.PREIMAGES}
    with pytest.raises(ValueError, match="source_changed"):
        experiment.prepare_overlay(tmp_path, "optimized-noswap", 300)
    assert before == {p: (tmp_path / p).read_bytes() for p in experiment.PREIMAGES}


def test_repeated_overlay_application_is_rejected(tmp_path):
    source_copy(tmp_path)
    experiment.prepare_overlay(tmp_path, "asan-swap", 300)
    with pytest.raises(ValueError, match="source_changed"):
        experiment.prepare_overlay(tmp_path, "asan-swap", 300)


@pytest.mark.parametrize(
    "profile,seconds",
    [
        ("unknown", 300),
        ("asan-noswap", 40),
        ("asan-noswap", 305),
        ("asan-noswap", 46),
        ("asan-noswap", True),
    ],
)
def test_invalid_profile_and_duration_are_rejected(profile, seconds):
    with pytest.raises(ValueError):
        experiment.validate_profile(profile, seconds)


def test_optimized_trace_stubs_link_without_sanitizer(tmp_path):
    source_copy(tmp_path)
    experiment.prepare_overlay(tmp_path, "optimized-noswap", 300)
    code = tmp_path / "probe.cpp"
    code.write_text(
        '#include "allocation_trace.H"\n#include "resource_trace.H"\nint main(){v08_resource_trace(1);v08_allocation_profile_dump(0);return v08_allocation_profile_start()?0:2;}\n'
    )
    binary = tmp_path / "probe"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O2",
            "-DOPENBEXI_NATIVE_NO_SANITIZERS=1",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I" + str(tmp_path / "host_runtime/native"),
            str(code),
            "-o",
            str(binary),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    env = dict(os.environ, OPENBEXI_V08_ALLOCATION_DIAGNOSTICS="0")
    result = subprocess.run([str(binary)], env=env, capture_output=True, check=True, timeout=10)
    assert not result.stdout and not result.stderr
    env["OPENBEXI_V08_ALLOCATION_DIAGNOSTICS"] = "1"
    assert subprocess.run([str(binary)], env=env, capture_output=True, timeout=10).returncode == 2
    dynamic = subprocess.check_output(["readelf", "-d", str(binary)], text=True)
    assert "libasan" not in dynamic and "libubsan" not in dynamic


def test_comparison_assessor_does_not_modify_raw_evidence(tmp_path):
    rows = evidence(tmp_path)
    saved = deepcopy(rows)
    raw = (tmp_path / "native-resources.jsonl").read_bytes()
    experiment.assess_experiment(tmp_path, "asan-noswap", 300)
    assert rows == saved
    assert (tmp_path / "native-resources.jsonl").read_bytes() == raw


def test_swap_setup_is_inert_outside_a_dedicated_hosted_runner():
    env = dict(os.environ, GITHUB_ACTIONS="false")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/v08_memory_swap_ci.sh"), "true"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Refusing swap setup" in result.stderr


def test_cli_help_does_not_create_containers():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/qualify_v08_memory_comparison.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--prepare-only" in result.stdout
