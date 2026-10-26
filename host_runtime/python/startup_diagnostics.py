"""Bounded, read-only native startup diagnostics; never reads argv or environment."""

# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import re

STAGES = frozenset(
    {
        "entered",
        "admitted",
        "ipc-ready",
        "spawn-requested",
        "fork-entered",
        "fork-returned",
        "fork-failed",
        "process-started",
        "login-entered",
        "login-published",
        "login-observed",
        "binding-requested",
        "member-bound",
    }
)
PROGRAMS = frozenset(
    {
        "SPELL-Listener",
        "SPELL-Context",
        "SPELL-Executor_v3",
        "SPELL-Executor",
        "python",
        "python3",
        "python3.13",
        "bash",
    }
)


def trace_records(raw):
    records = []
    for line in raw[-262144:].splitlines():
        if not line.startswith(b"V08_START ") or len(line) > 255:
            continue
        try:
            record = json.loads(line[10:])
            if (
                type(record) is dict
                and set(record) == {"member", "pid", "stage", "monotonic_ns"}
                and type(record["member"]) is str
                and re.fullmatch(r"[0-9a-f]{16}", record["member"])
                and type(record["pid"]) is int
                and 0 < record["pid"] < 2**31
                and type(record["stage"]) is str
                and record["stage"] in STAGES
                and type(record["monotonic_ns"]) is int
                and 0 <= record["monotonic_ns"] < 2**64
            ):
                records.append(record)
        except (ValueError, TypeError):
            continue
    return records[-1024:]


def snapshot(proc=Path("/proc"), temporary=Path("/tmp")):
    result = dict(
        schema="openbexi.native-startup-diagnostic/1", processes=[], traces=[]
    )
    task_budget = 256
    for path in sorted(proc.iterdir()):
        if not path.name.isdigit() or len(result["processes"]) >= 64:
            continue
        try:
            executable = (path / "exe").resolve(strict=True).name
            if executable not in PROGRAMS:
                continue
            stat = (path / "stat").read_text()[:4096].rsplit(")", 1)[1].split()
            process = dict(
                pid=int(path.name), ppid=int(stat[1]), executable=executable, tasks=[]
            )
            for task in sorted((path / "task").iterdir()):
                if not task.name.isdigit() or task_budget <= 0:
                    continue
                try:
                    state = (
                        (task / "stat").read_text()[:4096].rsplit(")", 1)[1].split()[0]
                    )
                    wait = (task / "wchan").read_text()[:128].strip()
                    if state not in "RSDZTWtXxKWPIN" or len(state) != 1:
                        continue
                    process["tasks"].append(
                        dict(
                            tid=int(task.name),
                            state=state,
                            wait=wait
                            if re.fullmatch(r"[A-Za-z0-9_]{1,128}", wait)
                            else "unavailable",
                        )
                    )
                    task_budget -= 1
                except (OSError, ValueError, IndexError):
                    continue
            result["processes"].append(process)
        except (OSError, ValueError, IndexError):
            continue
    for path in sorted(temporary.glob("spell-host-*/native.log"))[:2]:
        try:
            with path.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 262144))
                result["traces"].extend(trace_records(stream.read(262144)))
        except OSError:
            continue
    result["task_limit_reached"] = task_budget == 0
    return result


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
