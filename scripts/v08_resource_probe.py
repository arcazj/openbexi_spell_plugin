"""Read-only host observations for a bound native worker; never a release proof."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import time


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
    for log in sorted((root / "root/tmp").glob("spell-host-*/native.log"))[:2]:
        try:
            with log.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 65536))
                result["native_allocator"].extend(allocator_records(stream.read(65536)))
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
