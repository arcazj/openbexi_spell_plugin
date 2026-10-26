"""Isolated memory comparisons; never modify or promote mandatory release gates."""

import hashlib
import json
import math
from pathlib import Path
import statistics

MIB = 1024**2
GIB = 1024**3
PROFILES = ("asan-noswap", "optimized-noswap", "asan-swap")
# Fail closed when the source to be transformed changes. No fuzzy patches.
PREIMAGES = {
    "host_runtime/build_admission_context.py": "24669fce3330cb9c4959816f7d202f7e1ff547d6d0793bf00631330eabb0e208",
    "host_runtime/python/native.py": "4d8a1664622dddd5192451f230b3fbc4361d632ae23692aa1a989b62d92b3ff7",
    "scripts/qualify_v08_native_launch.py": "fc33b8358cf3ed019d84056c0b8e139688b6bc206cc3cc1784c14ac67fa43d29",
    "scripts/v08_native_consumption.py": "4ab366a3b03541ede860acb1e63b7d4952312b2af9150b61ca874ebef406a039",
    "scripts/v08_resource_probe.py": "c2f4ec84b35466058528b651bed72e8ef425aa40e25f044a0beca100c737358f",
    "scripts/v08_handoff_cohort.py": "d54ca70c8073f96445a30d57fd7fd5adc116e21b28657f508e07caeaea241117",
    "host_runtime/python/handoff_probe.py": "d2c2ee8d05bd6d4fc0e79d11387058c79508b2f346ae7d6710c5ebae48ff0023",
    "host_runtime/native/allocation_trace.H": "5a1b1600728d1e5abe7b211cd534a71da62fcd4b789774b1a0657c10ec7b4e5e",
    "host_runtime/native/resource_trace.H": "7529df0a9ee9923b750e47c583c4c7d5213f60b15bf6eeb502fcc569edf73a95",
}
NATIVE_PROGRAMS = {
    "SPELL-Context",
    "SPELL-Executor",
    "SPELL-Executor_v3",
    "SPELL-Listener",
    "spell-host-ipc",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_profile(profile, soak_seconds):
    if profile not in PROFILES:
        raise ValueError("unknown_memory_profile")
    if (
        type(soak_seconds) is not int
        or not 45 <= soak_seconds <= 300
        or soak_seconds % 5
    ):
        raise ValueError("soak_requires_45_to_300_seconds_in_five_second_steps")


def replace_exact(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError("memory_experiment_patch_anchor_changed")
    return text.replace(before, after)


# This generated launcher preserves the frozen launcher's Python/library policy,
# but executes the rebuilt Listener, not the frozen instrumented executable.
OPTIMIZED_LAUNCHER = """from pathlib import Path
import os
import sys
from spell_native.launcher import environment
if os.environ.get("LD_PRELOAD"):
    raise SystemExit("Unexpected preload in optimized memory experiment")
program = Path("/opt/v08-native-home/bin/SPELL-Listener")
os.execve(program, [str(program), *sys.argv[1:]], environment())
"""

OPTIMIZED_FINALIZE = """
    # Isolated experimental image only. The frozen package/baseline stay intact.
    shim = Path(sysconfig.get_path("purelib")) / "libSPELL_DTA_v3.py"
    shim_before = shim.read_text()
    guard = "if 'libasan.so' not in Path('/proc/self/maps').read_text(encoding='utf-8'):\\n    raise ImportError('This diagnostic native build requires spell-native-python or spell-native run.')\\n"
    location = "_path = launcher.ROOT / 'bin/libspell_executor313.so'"
    if shim_before.count(guard) != 1 or shim_before.count(location) != 1:
        raise ValueError("Optimized DTA shim preimage differs")
    shim_after = shim_before.replace(guard, "").replace(
        location, "_path = Path('/opt/v08-native-home/bin/libspell_executor313.so')"
    )
    shim.write_text(shim_after)
    (home / "launch-listener.py").write_text(OPTIMIZED_LAUNCHER_TEXT)
    dependencies = {}
    for artifact in [shared, bridge_binary, *(binaries / ("SPELL-" + n) for n in programs)]:
        linked = subprocess.check_output(["readelf", "-d", str(artifact)], text=True)
        names = re.findall(r"Shared library: \\[(.*?)\\]", linked)
        if any("libasan" in n or "libubsan" in n for n in names):
            raise ValueError("Optimized artifact still links sanitizer runtime")
        dependencies[artifact.name] = names
    report["memory_build_profile"] = "optimized-experiment"
    report["sanitizer_allocator_metrics_available"] = False
    report["optimized_listener_sha256"] = programs["Listener"]
    report["optimized_dependencies"] = dependencies
    report["optimized_launcher_sha256"] = sha(home / "launch-listener.py")
    report["optimized_dta_shim"] = {
        "before": hashlib.sha256(shim_before.encode()).hexdigest(),
        "after": sha(shim),
    }
"""


def optimized_builder(text):
    text = replace_exact(text, '        "-O1",', '        "-O2",')
    # Three compile/link sites. This is only an experimental copy of the builder.
    text = replace_exact(text, '"-fsanitize=address,undefined",', "", count=3)
    text = replace_exact(text, '        "-fno-sanitize-recover=all",\n', "")
    text = replace_exact(
        text,
        'for name in ("Context", "Executor")',
        'for name in ("Context", "Executor", "Listener")',
    )
    text = replace_exact(
        text,
        '            "SPELL-Context",\n',
        '            "SPELL-Listener",\n            "SPELL-Context",\n',
    )
    anchor = (
        '    (home / "build.json").write_text(json.dumps(report, indent=2) + "\\n")'
    )
    text = replace_exact(text, anchor, OPTIMIZED_FINALIZE + "\n" + anchor)
    return "OPTIMIZED_LAUNCHER_TEXT = " + repr(OPTIMIZED_LAUNCHER) + "\n" + text


def prepare_overlay(root, profile, soak_seconds):
    """Apply exact, recorded transformations to a disposable detached worktree."""
    validate_profile(profile, soak_seconds)
    root = Path(root)
    originals = {}
    for relative, expected in PREIMAGES.items():
        data = (root / relative).read_bytes()
        if digest(data) != expected:
            raise ValueError("memory_experiment_source_changed: " + relative)
        originals[relative] = data.decode()
    changed = dict(originals)
    probe = changed["scripts/v08_resource_probe.py"]
    start, end = (
        probe.index("def assess_recovery_resources(output):"),
        probe.index("\ndef read(path):"),
    )
    probe = (
        probe[:start]
        + (
            "def assess_recovery_resources(output):\n"
            "    from v08_memory_experiment import assess_experiment\n"
            f"    return assess_experiment(output, {profile!r}, {soak_seconds})\n\n"
        )
        + probe[end:]
    )
    # The observer must cover the longer experiment. Its interval is unchanged.
    probe = replace_exact(probe, "for _ in range(120):", "for _ in range(300):")
    probe = replace_exact(probe, "maximum_samples=120,", "maximum_samples=300,")
    mapping = """            if row["program"] in {"SPELL-Context", "SPELL-Executor", "SPELL-Executor_v3", "SPELL-Listener", "spell-host-ipc"}:
                with (path / "maps").open() as stream:
                    maps = stream.read(1048577)
                if not maps or len(maps) > 1048576:
                    raise ValueError("Native mapping observation incomplete")
                row["sanitizer_mapped"] = "libasan.so" in maps or "libubsan.so" in maps
                row["native_maps_observed"] = True
"""
    probe = replace_exact(
        probe,
        '            row["status"] = numbers(',
        mapping + '            row["status"] = numbers(',
    )
    changed["scripts/v08_resource_probe.py"] = probe
    # Only fixture duration changes. RPC, admission, lease and driver deadlines do not.
    cohort = changed["scripts/v08_handoff_cohort.py"]
    cohort = replace_exact(
        cohort, "for _ in range(9):", f"for _ in range({soak_seconds // 5}):"
    )
    cohort = replace_exact(
        cohort, "minimum_seconds=45,", f"minimum_seconds={soak_seconds},"
    )
    changed["scripts/v08_handoff_cohort.py"] = cohort
    changed["host_runtime/python/handoff_probe.py"] = replace_exact(
        changed["host_runtime/python/handoff_probe.py"],
        "deadline = time.monotonic() + 180",
        f"deadline = time.monotonic() + {180 + soak_seconds - 45}",
    )
    # The new assessor is imported by the host only; it never enters worker authority.
    launch = changed["scripts/qualify_v08_native_launch.py"]
    launch = replace_exact(
        launch,
        "        Path(__file__),",
        '        ROOT / "scripts/v08_memory_experiment.py",\n        Path(__file__),',
    )
    launch = replace_exact(
        launch,
        "        full_v08_qualified=False,\n        allocation_diagnostics_only=",
        "        full_v08_qualified=False,\n        memory_comparison_only=True,\n        allocation_diagnostics_only=",
    )
    changed["scripts/qualify_v08_native_launch.py"] = launch
    if profile == "asan-swap":
        consumption = changed["scripts/v08_native_consumption.py"]
        consumption = replace_exact(
            consumption,
            '            "--memory-swap",\n            "2048m",',
            '            "--memory-swap",\n            "4096m",',
        )
        changed["scripts/v08_native_consumption.py"] = consumption
    if profile == "optimized-noswap":
        changed["host_runtime/build_admission_context.py"] = optimized_builder(
            changed["host_runtime/build_admission_context.py"]
        )
        changed[
            "host_runtime/native/allocation_trace.H"
        ] = """// Experimental non-sanitized build: no invented allocator samples.
#include <cstdint>
#include <cstdlib>
extern "C" bool v08_allocation_profile_start() noexcept {
    const char* p = std::getenv("OPENBEXI_V08_ALLOCATION_DIAGNOSTICS");
    return !p || p[0] != '1';
}
extern "C" void v08_allocation_profile_dump(uint64_t) noexcept {}
"""
        changed[
            "host_runtime/native/resource_trace.H"
        ] = """// No sanitizer allocator is present in this experimental build.
// Independently collected /proc and cgroup accounting remain mandatory.
#ifndef OPENBEXI_V08_RESOURCE_TRACE_H
#define OPENBEXI_V08_RESOURCE_TRACE_H
static void v08_resource_trace(unsigned int) noexcept {}
#endif
"""
        session = changed["host_runtime/python/native.py"]
        session = replace_exact(
            session,
            "['spell-native', 'listener', '-c', example['config']]",
            "[sys.executable, '-I', str(self.native_home / 'launch-listener.py'), '-c', example['config']]",
        )
        if "import sys\n" not in session:
            session = "import sys\n" + session
        changed["host_runtime/python/native.py"] = session
    manifest = {}
    # Validate every transformation before writing anything.
    for relative, text in changed.items():
        if relative.endswith(".py"):
            compile(text, relative, "exec")
        if text != originals[relative]:
            manifest[relative] = {
                "before_sha256": digest(originals[relative].encode()),
                "after_sha256": digest(text.encode()),
            }
    for relative in manifest:
        (root / relative).write_text(changed[relative])
    return manifest


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid_numeric_observation")
    return value


def assess_experiment(output, profile, soak_seconds):
    """Check RAM+swap growth, original process identity and actual instrumentation.

    A comparison receipt is deliberately not a mandatory release-gate receipt.
    A swap-capacity pass without swap use is explicitly not evidence of swap benefit.
    """
    validate_profile(profile, soak_seconds)
    output = Path(output)
    swap = profile == "asan-swap"
    result = {
        "schema": "openbexi.native-memory-comparison-resources/1",
        "profile": profile,
        "diagnostic_only": True,
        "full_v08_qualified": False,
        "eligible_for_publication": False,
        "passed": False,
        "resident_limit_bytes": 2 * GIB,
        "swap_limit_bytes": 2 * GIB if swap else 0,
        "resident_peak_budget_bytes": 2 * GIB if swap else 1792 * MIB,
        "combined_peak_budget_bytes": 3584 * MIB if swap else 1792 * MIB,
        "maximum_combined_window_growth_bytes": 64 * MIB,
        "minimum_soak_seconds": soak_seconds,
        "swap_exercised": False,
        "failures": [],
    }
    try:
        observer = json.loads((output / "native-resource-observer.json").read_text())
        soak = json.loads((output / "native-recovery-soak.json").read_text())
        path = output / "native-resources.jsonl"
        if path.stat().st_size > 8 * MIB:
            raise ValueError("resource_evidence_too_large")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        samples = [r for r in rows if r.get("schema") == "openbexi.native-resources/1"]
        if observer["errors"] or not 20 <= len(samples) <= 300:
            raise ValueError("incomplete_resource_observation")
        if any(r not in samples and r != {"container_exited": True} for r in rows):
            raise ValueError("unrecognized_resource_record")
        identities = {(r["container_id"], r["pid"], r["start_ticks"]) for r in samples}
        if (
            len(identities) != 1
            or samples[0]["container_id"] != observer["container_id"]
        ):
            raise ValueError("container_identity_changed")
        ticks = [_integer(r["monotonic_ns"]) for r in samples]
        if any(not 0 < b - a <= 6 * 10**9 for a, b in zip(ticks, ticks[1:])):
            raise ValueError("resource_sampling_gap")
        start, end = _integer(soak["start_ns"]), _integer(soak["end_ns"])
        if end - start < soak_seconds * 10**9:
            raise ValueError("recovery_soak_too_short")
        if (
            soak["original_processes"] != 8
            or soak["all_intervals_advanced"] is not True
        ):
            raise ValueError("original_family_progress_unproven")
        window = [r for r in samples if start <= r["monotonic_ns"] <= end]
        if len(window) < max(20, math.floor(soak_seconds / 2.5)):
            raise ValueError("incomplete_soak_sampling")
        if (
            window[0]["monotonic_ns"] > start + 5 * 10**9
            or window[-1]["monotonic_ns"] < end - 5 * 10**9
        ):
            raise ValueError("incomplete_soak_endpoints")
        original_roster = None
        programs = set()
        for row in window:
            roster = frozenset((p["pid"], p["start_ticks"]) for p in row["processes"])
            if len(roster) != 8 or (
                original_roster is not None and roster != original_roster
            ):
                raise ValueError("original_process_roster_changed")
            original_roster = roster
            for process in row["processes"]:
                if process.get("program") in NATIVE_PROGRAMS:
                    programs.add(process["program"])
                    if process.get("native_maps_observed") is not True:
                        raise ValueError("native_instrumentation_unobserved")
                    expected = profile != "optimized-noswap"
                    if process.get("sanitizer_mapped") is not expected:
                        raise ValueError("native_instrumentation_mismatch")
        if not {
            "SPELL-Context",
            "SPELL-Listener",
            "spell-host-ipc",
        } <= programs or not programs.intersection(
            {"SPELL-Executor", "SPELL-Executor_v3"}
        ):
            raise ValueError("incomplete_native_role_observation")
        for row in samples:
            values = row["values"]
            for key in (
                "memory.max",
                "memory.peak",
                "memory.current",
                "memory.swap.max",
                "memory.swap.current",
            ):
                _integer(values[key])
            if (
                values["memory.max"] != 2 * GIB
                or values["memory.swap.max"] != result["swap_limit_bytes"]
            ):
                raise ValueError("resource_limits_differ")
            if values["memory.swap.current"] > result["swap_limit_bytes"]:
                raise ValueError("swap_allowance_exceeded")
            for key in ("max", "oom", "oom_kill"):
                value = _integer(values["memory.events"][key])
                if value and (key != "max" or not swap):
                    raise ValueError("native_memory_pressure_or_oom")
            if values.get("memory.swap.events", {}).get("fail", 0):
                raise ValueError("swap_allocation_failed")
        peak = max(r["values"]["memory.peak"] for r in samples)

        def combined(r):
            return r["values"]["memory.current"] + r["values"]["memory.swap.current"]

        total_peak = max(combined(r) for r in samples)
        first = [combined(r) for r in window if r["monotonic_ns"] <= start + 10 * 10**9]
        last = [combined(r) for r in window if r["monotonic_ns"] >= end - 10 * 10**9]
        growth = statistics.median(last) - statistics.median(first)
        swap_peak = max(r["values"]["memory.swap.current"] for r in samples)
        result.update(
            samples=len(samples),
            soak_samples=len(window),
            duration_seconds=(end - start) / 10**9,
            resident_peak_bytes=peak,
            sampled_combined_peak_bytes=total_peak,
            combined_window_growth_bytes=growth,
            sampled_swap_peak_bytes=swap_peak,
            swap_exercised=swap_peak > 0,
            native_instrumentation_verified=True,
            original_processes=8,
            memory_max_events=max(r["values"]["memory.events"]["max"] for r in samples),
        )
        for failed, label in (
            (
                peak > result["resident_peak_budget_bytes"],
                "resident_peak_budget_exceeded",
            ),
            (
                total_peak > result["combined_peak_budget_bytes"],
                "combined_peak_budget_exceeded",
            ),
            (growth > 64 * MIB, "combined_memory_still_growing"),
        ):
            if failed:
                result["failures"].append(label)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        statistics.StatisticsError,
    ) as error:
        label = (
            str(error)
            if type(error) is ValueError and str(error).isidentifier()
            else type(error).__name__
        )
        result["failures"].append(label)
    result["passed"] = not result["failures"]
    (output / "native-resource-acceptance.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result
