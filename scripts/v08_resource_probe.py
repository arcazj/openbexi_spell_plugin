"""Read-only host observations for a bound native worker; never a release proof."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import statistics
import stat
import threading
import time


def temporary_file_usage(root, maximum_entries=4096):
    """Bounded metadata-only inventory; never emit names or read file contents.

    File/shmem kernel accounting overlaps. These allocated blocks attribute
    temporary-file growth independently, without subtracting it from acceptance.
    Directory descriptors and O_NOFOLLOW exclude symlink targets and replacements.
    """
    totals = {
        name: dict(files=0, logical_bytes=0, allocated_bytes=0)
        for name in ("native_console", "native_diagnostic", "asrun", "other")
    }
    result = dict(categories=totals, entries=0, complete=True, errors=0, symlinks=0)
    seen = set()

    def walk(fd, depth):
        with os.scandir(fd) as entries:
            for entry in entries:
                if result["entries"] >= maximum_entries:
                    result["complete"] = False
                    return
                result["entries"] += 1
                try:
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        result["symlinks"] += 1
                    elif stat.S_ISDIR(info.st_mode):
                        if depth >= 8:
                            result["complete"] = False
                            continue
                        child = os.open(
                            entry.name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd,
                        )
                        try:
                            walk(child, depth + 1)
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode):
                        identity = (info.st_dev, info.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        name = entry.name.lower()
                        category = (
                            "native_console"
                            if name == "native.log"
                            else "asrun"
                            if name.endswith((".asrun", ".asr"))
                            else "native_diagnostic"
                            if name.endswith((".log", ".log.1"))
                            else "other"
                        )
                        bucket = totals[category]
                        bucket["files"] += 1
                        bucket["logical_bytes"] += info.st_size
                        bucket["allocated_bytes"] += info.st_blocks * 512
                except OSError:
                    result["errors"] += 1
                    result["complete"] = False

    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            walk(fd, 0)
        finally:
            os.close(fd)
    except OSError:
        result["errors"] += 1
        result["complete"] = False
    return result


def assess_recovery_resources(output):
    """Fail closed on missing, swapped, pressure-limited or still-growing evidence.

    This is a bounded acceptance of one instrumented two-Executor fixture, not
    a production capacity recommendation or proof of indefinite stability.
    """
    result = dict(
        schema="openbexi.native-recovery-resources/1",
        passed=False,
        resident_limit_bytes=2 * 1024**3,
        swap_limit_bytes=0,
        peak_budget_bytes=1792 * 1024**2,
        maximum_window_growth_bytes=64 * 1024**2,
        full_v08_qualified=False,
        failures=[],
    )
    failures = result["failures"]
    try:
        observer = json.loads((output / "native-resource-observer.json").read_text())
        soak = json.loads((output / "native-recovery-soak.json").read_text())
        path = output / "native-resources.jsonl"
        if path.stat().st_size > 4 * 1024**2:
            raise ValueError("resource_evidence_too_large")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        samples = [r for r in rows if r.get("schema") == "openbexi.native-resources/1"]
        if observer["errors"] or not 20 <= len(samples) <= 120:
            raise ValueError("incomplete_resource_observation")
        if any(r not in samples and r != {"container_exited": True} for r in rows):
            raise ValueError("unrecognized_resource_observation")
        identities = {(r["container_id"], r["pid"], r["start_ticks"]) for r in samples}
        if (
            len(identities) != 1
            or samples[0]["container_id"] != observer["container_id"]
        ):
            raise ValueError("resource_container_identity_changed")
        ticks = [r["monotonic_ns"] for r in samples]
        if any(not 0 < b - a <= 6 * 10**9 for a, b in zip(ticks, ticks[1:])):
            raise ValueError("resource_sampling_gap")
        if soak["end_ns"] - soak["start_ns"] < 45 * 10**9:
            raise ValueError("recovery_soak_too_short")
        window = [
            r
            for r in samples
            if soak["start_ns"] <= r["monotonic_ns"] <= soak["end_ns"]
        ]
        if (
            len(window) < 20
            or window[0]["monotonic_ns"] > soak["start_ns"] + 5 * 10**9
            or window[-1]["monotonic_ns"] < soak["end_ns"] - 5 * 10**9
        ):
            raise ValueError("recovery_soak_coverage_incomplete")
        for row in samples:
            values = row["values"]
            for key in (
                "memory.max",
                "memory.peak",
                "memory.current",
                "memory.swap.max",
                "memory.swap.current",
            ):
                if type(values[key]) is not int or values[key] < 0:
                    raise ValueError("invalid_resource_counter")
            if (
                values["memory.max"] != result["resident_limit_bytes"]
                or values["memory.swap.max"] != 0
            ):
                raise ValueError("resource_limits_differ")
            if values["memory.swap.current"] != 0:
                raise ValueError("native_recovery_swapped")
            events = values["memory.events"]
            for key in ("max", "oom", "oom_kill"):
                if type(events[key]) is not int or events[key] != 0:
                    raise ValueError("native_recovery_memory_pressure")
        peak = max(r["values"]["memory.peak"] for r in samples)
        if peak > result["peak_budget_bytes"]:
            failures.append("native_recovery_peak_budget_exceeded")
        first = [
            r["values"]["memory.current"]
            for r in window
            if r["monotonic_ns"] <= soak["start_ns"] + 10 * 10**9
        ]
        last = [
            r["values"]["memory.current"]
            for r in window
            if r["monotonic_ns"] >= soak["end_ns"] - 10 * 10**9
        ]
        growth = statistics.median(last) - statistics.median(first)
        if growth > result["maximum_window_growth_bytes"]:
            failures.append("native_recovery_memory_still_growing")
        result.update(
            samples=len(samples),
            soak_samples=len(window),
            duration_seconds=(soak["end_ns"] - soak["start_ns"]) / 10**9,
            peak_bytes=peak,
            window_growth_bytes=growth,
            first_window_median_bytes=statistics.median(first),
            last_window_median_bytes=statistics.median(last),
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        statistics.StatisticsError,
    ) as error:
        # Only fixed labels from this verifier enter the public receipt.
        label = str(error) if type(error) is ValueError else type(error).__name__
        failures.append(label if label.isidentifier() else type(error).__name__)
    result["passed"] = not failures
    (output / "native-resource-acceptance.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result


def read(path):
    with path.open() as stream:
        value = stream.read(65537)
    if len(value) > 65536:
        raise ValueError("Resource observation exceeds bound")
    return value.strip()


def numbers(path, allowed=None, *, colon=False):
    result = {}
    for line in read(path).splitlines():
        parts = line.replace(":", " ", 1).split() if colon else line.split()
        if len(parts) >= 2 and (allowed is None or parts[0] in allowed):
            if len(parts) == 2 and parts[1].isdecimal():
                result[parts[0]] = int(parts[1])
            elif len(parts) == 3 and parts[1].isdecimal() and parts[2] == "kB":
                result[parts[0] + "_bytes"] = int(parts[1]) * 1024
    return result


def identity(path):
    fields = read(path / "stat").rsplit(")", 1)[1].split()
    return int(fields[19])


def allocator_records(raw):
    """Fixed numeric metadata only; never return arbitrary native log text."""
    latest = {}
    fields = {
        "pid",
        "role",
        "monotonic_ns",
        "allocated_bytes",
        "heap_bytes",
        "free_bytes",
        "unmapped_bytes",
    }
    for line in raw[-65536:].splitlines():
        if not line.startswith(b"V08_MEMORY ") or len(line) >= 384:
            continue
        try:
            record = json.loads(line[11:])
            if (
                type(record) is dict
                and set(record) == fields
                and all(
                    type(value) is int and 0 <= value < 2**64
                    for value in record.values()
                )
                and 0 < record["pid"] < 2**31
                and record["role"] == 1
            ):
                latest[record["pid"]] = record
        except (ValueError, TypeError):
            continue
    return list(latest.values())[:256]


def allocation_profiles(raw):
    """Retain only bounded numeric counters and compiler symbol/offset metadata."""
    latest = {}
    totals = re.compile(
        rb"V08_ALLOC pid=(\d{1,10}) tick=(\d{1,20}) calls=(\d{1,20}) "
        rb"bytes=(\d{1,20}) samples=(\d{1,20}) skipped=(\d{1,20})"
        rb"(?: frees=(\d{1,20}) free_misses=(\d{1,20}) pointer_full=(\d{1,20}))?"
    )
    site = re.compile(
        rb"V08_ALLOC_SITE pid=(\d{1,10}) rank=([0-5]) samples=(\d{1,20}) bytes=(\d{1,20})"
        rb"(?: freed_samples=(\d{1,20}) freed_bytes=(\d{1,20}))?"
    )
    frame = re.compile(
        rb"([A-Za-z0-9_.?+\-]{1,60})\+([0-9a-f]{1,16}):([A-Za-z0-9_.$?]{1,100})"
    )
    for line in raw[-262144:].splitlines():
        if len(line) >= 4096:
            continue
        matched = totals.fullmatch(line)
        if matched:
            values = [int(value) for value in matched.groups() if value is not None]
            if not 0 < values[0] < 2**31 or any(value >= 2**64 for value in values):
                continue
            if values[0] not in latest and len(latest) >= 32:
                continue
            latest[values[0]] = dict(
                zip(
                    (
                        "pid",
                        "monotonic_ns",
                        "calls",
                        "bytes",
                        "samples",
                        "skipped",
                        "frees",
                        "free_misses",
                        "pointer_full",
                    ),
                    values,
                )
            )
            latest[values[0]]["sites"] = {}
            continue
        parts = line.split(b" | ")
        matched = site.fullmatch(parts[0])
        if not matched or not 1 < len(parts) <= 21:
            continue
        owner, rank, samples, size = map(int, matched.groups()[:4])
        if owner not in latest or max(samples, size) >= 2**64:
            continue
        frames = [frame.fullmatch(part) for part in parts[1:]]
        if not all(frames):
            continue
        latest[owner]["sites"][rank] = dict(
            rank=rank,
            samples=samples,
            bytes=size,
            frames=[
                dict(
                    module=item[1].decode(),
                    offset=int(item[2], 16),
                    symbol=item[3].decode(),
                )
                for item in frames
            ],
        )
        if matched[5] is not None:
            freed_samples, freed_bytes = int(matched[5]), int(matched[6])
            if freed_samples > samples or freed_bytes > size:
                del latest[owner]["sites"][rank]
                continue
            latest[owner]["sites"][rank].update(
                freed_samples=freed_samples,
                freed_bytes=freed_bytes,
                unmatched_samples_upper_bound=samples - freed_samples,
                unmatched_bytes_upper_bound=size - freed_bytes,
            )
    result = []
    for record in latest.values():
        sites = record.pop("sites")
        record["all_six_sites_observed"] = set(sites) == set(range(6))
        record["sites"] = [sites[rank] for rank in sorted(sites)]
        result.append(record)
    return result


STORAGE_METRICS = (
    "node_requests",
    "node_reused",
    "node_unavailable",
    "node_lock_miss",
    "node_empty",
    "copy_calls",
    "copy_whole_map",
    "copy_map_lock_miss",
    "copy_shape_miss",
    "copy_allocations",
    "recycle_calls",
    "recycle_empty",
    "recycle_wide",
    "recycle_capacity",
    "recycle_unavailable",
    "recycle_lock_miss",
    "recycle_full",
    "recycled_maps",
)


def message_storage_profiles(raw):
    """Fixed numeric cache decisions only; never retain property names or values."""
    pattern = re.compile(
        rb"V08_STORAGE pid=(\d{1,10}) tick=(\d{1,20})"
        + b"".join(b" " + name.encode() + rb"=(\d{1,20})" for name in STORAGE_METRICS)
    )
    latest = {}
    for line in raw[-262144:].splitlines():
        if len(line) >= 1536:
            continue
        match = pattern.fullmatch(line)
        if match is None:
            continue
        values = [int(value) for value in match.groups()]
        if not 0 < values[0] < 2**31 or any(value >= 2**64 for value in values):
            continue
        if values[0] not in latest and len(latest) >= 32:
            continue
        latest[values[0]] = dict(zip(("pid", "monotonic_ns", *STORAGE_METRICS), values))
    return list(latest.values())


def snapshot(pid, *, proc=Path("/proc"), groups=Path("/sys/fs/cgroup")):
    root = proc / str(pid)
    start = identity(root)
    rows = read(root / "cgroup").splitlines()
    if len(rows) != 1 or not rows[0].startswith("0::/"):
        raise ValueError("Resource observation requires cgroup v2")
    relative = Path(rows[0][4:])
    if ".." in relative.parts or relative.is_absolute():
        raise ValueError("Cgroup path differs")
    group = groups / relative
    result = dict(
        schema="openbexi.native-resources/1",
        monotonic_ns=time.monotonic_ns(),
        pid=pid,
        start_ticks=start,
        values={},
        processes=[],
        unavailable=[],
    )
    # Numeric kernel counters only. No command lines, environments, source,
    # credentials or native log contents enter this record.
    for name in (
        "memory.current",
        "memory.peak",
        "memory.max",
        "memory.swap.current",
        "memory.swap.peak",
        "memory.swap.max",
        "pids.current",
        "pids.max",
    ):
        try:
            value = read(group / name)
            if value != "max" and not value.isdecimal():
                raise ValueError("Invalid resource counter")
            result["values"][name] = value if value == "max" else int(value)
        except FileNotFoundError:
            result["unavailable"].append(name)
    for name in ("memory.stat", "memory.events", "memory.swap.events", "cpu.stat"):
        try:
            result["values"][name] = numbers(group / name)
        except FileNotFoundError:
            result["unavailable"].append(name)
    for name in ("cpu.pressure", "memory.pressure", "io.pressure"):
        try:
            result["values"][name] = {
                line.split()[0]: int(line.rsplit("total=", 1)[1])
                for line in read(group / name).splitlines()
                if line.startswith(("some ", "full "))
            }
        except FileNotFoundError:
            result["unavailable"].append(name)
    tasks = [int(value) for value in read(group / "cgroup.procs").split()]
    if len(tasks) > 256:
        raise ValueError("Resource process roster exceeds bound")
    for task in sorted(set(tasks)):
        path = proc / str(task)
        try:
            before = identity(path)
            row = dict(pid=task, start_ticks=before)
            namespace = [
                line.split()[1:]
                for line in read(path / "status").splitlines()
                if line.startswith("NSpid:")
            ]
            if namespace:
                row["namespace_pid"] = int(namespace[0][-1])
            # /proc/PID/exe is a magic link into the container mount namespace.
            # Resolving its textual target on the host can falsely report exit.
            program = Path(os.readlink(path / "exe")).name
            row["program"] = (
                program
                if program
                in {
                    "SPELL-Listener",
                    "SPELL-Context",
                    "SPELL-Executor_v3",
                    "SPELL-Executor",
                    "python",
                    "python3",
                    "python3.13",
                    "bash",
                    "docker-init",
                    "spell-host-ipc",
                }
                else "other"
            )
            row["status"] = numbers(
                path / "status",
                {
                    "VmRSS",
                    "VmHWM",
                    "VmSize",
                    "VmSwap",
                    "RssAnon",
                    "RssFile",
                    "RssShmem",
                    "Threads",
                    "voluntary_ctxt_switches",
                    "nonvoluntary_ctxt_switches",
                },
                colon=True,
            )
            try:
                row["smaps"] = numbers(
                    path / "smaps_rollup",
                    {
                        "Rss",
                        "Pss",
                        "Pss_Anon",
                        "Pss_File",
                        "Pss_Shmem",
                        "Anonymous",
                        "Private_Dirty",
                        "Shared_Dirty",
                        "Swap",
                        "SwapPss",
                    },
                    colon=True,
                )
            except (FileNotFoundError, PermissionError):
                row["smaps_unavailable"] = True
            if identity(path) != before:
                raise ValueError("Resource process identity changed")
            result["processes"].append(row)
        except FileNotFoundError:
            result["processes"].append(dict(pid=task, exited_during_sample=True))
    result["native_allocator"] = []
    result["native_allocation_profiles"] = []
    result["native_message_storage"] = []
    result["temporary_files"] = temporary_file_usage(root / "root/tmp")
    original_pids = {row.get("namespace_pid") for row in result["processes"]}
    for log in sorted((root / "root/tmp").glob("spell-host-*/native.log"))[:2]:
        try:
            with log.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 262144))
                raw = stream.read(262144)
                result["native_allocator"].extend(allocator_records(raw))
                result["native_allocation_profiles"].extend(
                    record
                    for record in allocation_profiles(raw)
                    if record["pid"] in original_pids
                )
                result["native_message_storage"].extend(
                    record
                    for record in message_storage_profiles(raw)
                    if record["pid"] in original_pids
                )
        except FileNotFoundError:
            continue
    if identity(root) != start or read(root / "cgroup").splitlines() != rows:
        raise ValueError("Bound resource container changed during observation")
    return result


@contextmanager
def observe(command, name, output):
    """Bounded host sampling also retains observations when qualification fails."""
    info = json.loads(command("docker", "inspect", name))[0]
    if not info["State"]["Running"] or info["State"]["Pid"] <= 0:
        raise ValueError("Resource sampling requires a live container")
    pid = info["State"]["Pid"]
    program = Path(__file__).read_text()
    stop = threading.Event()
    errors = []
    samples = []

    def collect():
        with (output / "native-resources.jsonl").open("a") as stream:
            for _ in range(120):
                if stop.is_set():
                    return
                try:
                    record = json.loads(
                        command(
                            "sudo",
                            "-n",
                            "python3",
                            "-c",
                            program,
                            str(pid),
                            timeout=5,
                        )
                    )
                    record["container_id"] = info["Id"]
                    stream.write(json.dumps(record, sort_keys=True) + "\n")
                    stream.flush()
                    samples.append(record["monotonic_ns"])
                except Exception as error:
                    try:
                        ended = json.loads(command("docker", "inspect", name))[0]
                    except Exception:
                        ended = None
                    if (
                        ended is not None
                        and ended["Id"] == info["Id"]
                        and not ended["State"]["Running"]
                        and samples
                    ):
                        stream.write(json.dumps(dict(container_exited=True)) + "\n")
                        return
                    errors.append(type(error).__name__)
                    stream.write(json.dumps(dict(observation_error=errors[-1])) + "\n")
                    stream.flush()
                    return
                if stop.wait(2):
                    return
            errors.append("ResourceObservationBudgetExceeded")

    thread = threading.Thread(
        target=collect, name="host-resource-observer", daemon=True
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=6)
        if thread.is_alive():
            errors.append("ResourceObserverDidNotStop")
        if not samples:
            errors.append("NoResourceSamples")
        (output / "native-resource-observer.json").write_text(
            json.dumps(
                dict(
                    errors=errors,
                    container_id=info["Id"],
                    maximum_samples=120,
                    interval_seconds=2,
                    samples=len(samples),
                    samples_atomic=False,
                    changes_resource_limits=False,
                ),
                indent=2,
            )
            + "\n"
        )
    if errors:
        raise RuntimeError("Native resource observation incomplete")


if __name__ == "__main__":
    import sys

    print(json.dumps(snapshot(int(sys.argv[1])), sort_keys=True))
