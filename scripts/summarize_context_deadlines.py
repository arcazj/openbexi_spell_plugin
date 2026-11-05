"""Summarize nested diagnostic timings without adding overlapping categories."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics


def read_rows(paths):
    return [
        json.loads(line) for path in paths for line in path.read_text().splitlines()
    ]


def statistics_ms(rows):
    values = sorted(row["duration_ns"] / 1e6 for row in rows)
    return dict(
        count=len(values),
        sum_ms=sum(values),
        p50_ms=statistics.median(values),
        p95_ms=values[int((len(values) - 1) * 0.95)],
        max_ms=values[-1],
    )


def overlap_union_ms(rows, start, end):
    spans = sorted(
        (max(start, r["start_ns"]), min(end, r["start_ns"] + r["duration_ns"]))
        for r in rows
        if r["start_ns"] < end and r["start_ns"] + r["duration_ns"] > start
    )
    total, last = 0, start
    for left, right in spans:
        if right > last:
            total += right - max(left, last)
            last = right
    return total / 1e6


def summarize(directory):
    results = json.loads((directory / "results.json").read_text())
    for result in results:
        target = directory / f"{result['repeat']}-{result['mode']}-{result['check']}"
        python = read_rows(target.glob("python-*.jsonl"))
        io = read_rows(target.glob("io-*.jsonl"))
        outcomes = [
            row for row in python if row["kind"] == "outcome" and row["when"] == "call"
        ]
        if not outcomes:
            continue
        outcome = outcomes[-1]
        end = outcome["start_ns"]
        start = end - int(outcome["reported_duration"] * 1e9)
        groups = defaultdict(list)
        for row in python + io:
            if not start <= row["start_ns"] <= end:
                continue
            kind, label = row["kind"], row["label"]
            if kind == "sqlite":
                if row["statement"] != "COMMIT":
                    continue
                label = Path(label).name
            if kind == "io":
                label += ":" + Path(row["path"]).name
            if kind in ("span", "sqlite", "lock_wait", "rpc_phase", "io"):
                groups[kind + ":" + label].append(row)
        result["profile"] = {
            key: statistics_ms(rows) for key, rows in sorted(groups.items())
        }
        result["observer_pids"] = sorted(
            {r["pid"] for r in python if r["kind"] == "observer"}
        )
        waits = groups.get("span:LedgerMutex.wait", [])
        if waits:
            wait = max(waits, key=lambda r: r["duration_ns"])
            left, right = wait["start_ns"], wait["start_ns"] + wait["duration_ns"]
            commits = [
                r
                for r in python
                if r["kind"] == "sqlite" and r["statement"] == "COMMIT"
            ]
            syncs = [r for r in io if r["label"] in ("fsync", "fdatasync")]
            result["longest_ledger_wait"] = dict(
                duration_ms=wait["duration_ns"] / 1e6,
                commit_union_ms=overlap_union_ms(commits, left, right),
                durable_sync_union_ms=overlap_union_ms(syncs, left, right),
            )
    return dict(
        timings_overlap_do_not_sum_categories=True,
        trials=results,
        passes=sum(r["exit_code"] == 0 for r in results),
        failures=sum(r["exit_code"] != 0 for r in results),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    summary = summarize(args.directory)
    (args.directory / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({key: summary[key] for key in ("passes", "failures")}))


if __name__ == "__main__":
    main()
