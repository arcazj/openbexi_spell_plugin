"""Isolated memory comparisons; never modify or promote mandatory release gates."""

import hashlib
import json
import math
from pathlib import Path
import statistics

MIB = 1024**2
GIB = 1024**3
PROFILES = ("asan-noswap", "optimized-noswap", "asan-swap", "asan-o2-noswap")
# Fail closed when the source to be transformed changes. No fuzzy patches.
PREIMAGES = {
    "scripts/v08_endurance.py": "c3608d88cd3e6217a9eba9b33f60ba6e23466f85ca54ad299b6d2edfcfaa2527",
    "host_runtime/build_native_profile.py": "f3b84111e2d0c3f2f4e465b8eae2c4d7c59554259e2bc3804aab89d07a32b757",
    "host_runtime/build_admission_context.py": "800fe0839a616a04bd1802e13f59d6e0631aa863c4298ee518cd97e3d197ad06",
    "host_runtime/python/native.py": "4d8a1664622dddd5192451f230b3fbc4361d632ae23692aa1a989b62d92b3ff7",
    "scripts/qualify_v08_native_launch.py": "fc33b8358cf3ed019d84056c0b8e139688b6bc206cc3cc1784c14ac67fa43d29",
    "scripts/v08_native_consumption.py": "4ab366a3b03541ede860acb1e63b7d4952312b2af9150b61ca874ebef406a039",
    "scripts/v08_resource_probe.py": "a5d4fda1063af6b0e2f3b6ae24a65fb5d79ebc2e7f233fbf2c9300596a127063",
    "scripts/v08_handoff_cohort.py": "d54ca70c8073f96445a30d57fd7fd5adc116e21b28657f508e07caeaea241117",
    "host_runtime/python/handoff_probe.py": "d2c2ee8d05bd6d4fc0e79d11387058c79508b2f346ae7d6710c5ebae48ff0023",
    "host_runtime/native/allocation_trace.H": "f89d661ee8ae19d41bb81af87063967eae81ab84dd667888bf17907355ed17b8",
    "host_runtime/native/resource_trace.H": "0f55d562c2a40c4b733520c1c9386842955cf5ba9229d8b336c9ad8c980415a8",
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
        or not 45 <= soak_seconds <= 3600
        or soak_seconds % 5
        or (soak_seconds > 300 and soak_seconds != 3600)
    ):
        raise ValueError("soak_requires_45_to_300_or_3600_seconds")


def replace_exact(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError("memory_experiment_patch_anchor_changed")
    return text.replace(before, after)


def explicit_builder(launch, profile):
    """Select the tracked builder; do not rewrite runtime build source code."""
    selected = "optimized" if profile == "optimized-noswap" else "asan-o2"
    launch = replace_exact(
        launch,
        'ROOT / "host_runtime/build_admission_context.py",\n                        native_build / "build.py",',
        'ROOT / "host_runtime/build_native_profile.py",\n                        native_build / "build.py",',
    )
    launch = replace_exact(
        launch,
        "                    # Ship the exact opt-in composition module",
        '                    shutil.copy2(ROOT / "host_runtime/build_admission_context.py", native_build / "build_admission_context.py")\n'
        "                    # Ship the exact opt-in composition module",
    )
    launch = replace_exact(
        launch,
        "COPY *.H private_bridge.cpp build.py native_prompt_patch.py",
        "COPY *.H private_bridge.cpp build.py build_admission_context.py native_prompt_patch.py",
    )
    launch = replace_exact(
        launch,
        '"RUN python /candidate/build.py"',
        '"RUN python /candidate/build.py --profile ' + selected + '"',
    )
    return launch


def endurance_cohort(text):
    # Thread the live proof to the host-only endurance exercise. It is popped
    # from the private sink and never included in any receipt.
    anchor = '    await_event,\n):\n    """Actual disconnect'
    text = replace_exact(
        text,
        anchor,
        '    await_event,\n    proof_sink=None,\n):\n    """Actual disconnect',
    )
    text = replace_exact(
        text,
        "    return dict(\n        passed=True,\n        automatic_disconnect_detection=True,",
        "    if proof_sink is not None:\n        proof_sink.update(new_proof)\n"
        "    return dict(\n        passed=True,\n        automatic_disconnect_detection=True,",
    )
    text = replace_exact(
        text,
        "        reconnection = qualify_reconnect(",
        "        endurance_proof = {}\n        reconnection = qualify_reconnect(\n            proof_sink=endurance_proof,",
    )
    begin = text.index("        # Continue the same original family for 45 seconds")
    end = text.index("        with closing(", begin)
    text = (
        text[:begin]
        + """        from v08_endurance import run_soak
        soak = run_soak(duration=3600, name=name, controller=controller,
                        proof=endurance_proof, bob_connection=bob, handoff_call=handoff_call,
                        command=command, control=control, handles=handles, original=original,
                        output=output, await_event=await_event)
        endurance_proof.clear()
        (output / "native-recovery-soak.json").write_text(json.dumps(soak) + "\\n")
"""
        + text[end:]
    )
    text = replace_exact(
        text,
        "            or history != 2",
        '            or history != 2 + soak["extra_history_entries"]',
    )
    text = replace_exact(
        text,
        "            epoch=3,\n            accepted_transfers=2,\n            same_owner_reconnections=1,",
        '            epoch=soak["final_epoch"],\n            accepted_transfers=2 + soak["extra_transfers"],\n            same_owner_reconnections=1 + soak["extra_reconnections"],',
    )
    return text


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
    max_samples = max(300, soak_seconds // 2 + 150)
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
    probe = replace_exact(
        probe, "for _ in range(120):", f"for _ in range({max_samples}):"
    )
    probe = replace_exact(
        probe, "maximum_samples=120,", f"maximum_samples={max_samples},"
    )
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
    if soak_seconds == 3600:
        cohort = endurance_cohort(cohort)
    else:
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
        '        ROOT / "scripts/v08_memory_experiment.py",\n        ROOT / "scripts/v08_endurance.py",\n        ROOT / "host_runtime/build_native_profile.py",\n        Path(__file__),',
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
    if profile in {"optimized-noswap", "asan-o2-noswap"}:
        changed["scripts/qualify_v08_native_launch.py"] = explicit_builder(
            launch, profile
        )
        session = changed["host_runtime/python/native.py"]
        session = replace_exact(
            session,
            "['spell-native', 'listener', '-c', example['config']]",
            "[sys.executable, '-I', str(self.native_home / 'launch-listener.py'), '-c', example['config']]",
        )
        if "import sys\n" not in session:
            session = "import sys\n" + session
        changed["host_runtime/python/native.py"] = session
    if soak_seconds > 45 and profile in {"asan-noswap", "asan-swap"}:
        header = changed["host_runtime/native/resource_trace.H"]
        changed["host_runtime/native/resource_trace.H"] = replace_exact(
            header,
            "#define OPENBEXI_NATIVE_TRACE_LIMIT 120",
            f"#define OPENBEXI_NATIVE_TRACE_LIMIT {max_samples}",
        )
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
        if path.stat().st_size > 64 * MIB:
            raise ValueError("resource_evidence_too_large")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        samples = [r for r in rows if r.get("schema") == "openbexi.native-resources/1"]
        if observer["errors"] or not 20 <= len(samples) <= max(
            300, soak_seconds // 2 + 150
        ):
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
        # Separate live allocations, retained allocator heap, anonymous and file
        # charges, thread counts, and late-window trends; no fabricated counters.
        first_time, last_time = start + 60 * 10**9, end - 60 * 10**9

        def med(values):
            return statistics.median(values) if values else None

        thread_first = [
            sum(p.get("status", {}).get("Threads", 0) for p in row["processes"])
            for row in window
            if row["monotonic_ns"] <= first_time
        ]
        thread_last = [
            sum(p.get("status", {}).get("Threads", 0) for p in row["processes"])
            for row in window
            if row["monotonic_ns"] >= last_time
        ]
        result["thread_observations_available"] = any(thread_first) and any(thread_last)
        result["thread_first_median"] = med(thread_first) if any(thread_first) else None
        result["thread_last_median"] = med(thread_last) if any(thread_last) else None
        result["allocator_observations_available"] = any(
            row.get("native_allocator") for row in window
        )
        result["last_memory_stat"] = window[-1]["values"].get("memory.stat", {})
        result["last_native_allocator"] = window[-1].get("native_allocator", [])
        if soak_seconds == 3600:
            late = [
                r
                for r in window
                if end - 600 * 10**9 <= r["monotonic_ns"] <= end - 540 * 10**9
            ]
            ending = [r for r in window if r["monotonic_ns"] >= end - 60 * 10**9]
            if not late or not ending:
                raise ValueError("late_window_samples_missing")
            result["late_ten_minute_growth_bytes"] = med(
                [combined(r) for r in ending]
            ) - med([combined(r) for r in late])
            cycles = json.loads((output / "endurance-cycles.json").read_text())
            if (
                cycles.get("passed") is not True
                or cycles.get("extra_transfers") != 4
                or cycles.get("extra_reconnections") != 1
                or cycles.get("rotations") != 8
            ):
                raise ValueError("endurance_cycles_unproven")
            result["endurance_cycles_verified"] = True
            result["rpc_latency"] = cycles["rpc_latency"]
            result["latency_slo_qualified"] = False
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
