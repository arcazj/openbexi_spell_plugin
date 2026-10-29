"""Bounded compiler parallelism over independently frozen fixture inputs.

Only compilation overlaps. All binaries finish building before the existing
fixture returns, so test order, native scenario concurrency and deadlines stay
unchanged. Every invocation retains its original timeout inside timed pytest.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeBuildBatch:
    def __init__(self, folder, request):
        self.folder = folder
        self.snapshots = folder.with_name(folder.name + "-compiler-inputs")
        self.snapshots.mkdir()
        xmlpath = request.config.getoption("xmlpath", default=None)
        self.records = (
            Path(xmlpath).with_suffix(".native-builds") / folder.name
            if xmlpath
            else self.snapshots / "records"
        )
        self.records.mkdir(parents=True, exist_ok=True)
        self.terminal = request.config.pluginmanager.get_plugin("terminalreporter")
        self.record_lock = threading.Lock()
        self.jobs = []

    def add(self, command, *, timeout, text=False):
        index = len(self.jobs)
        destination = self.snapshots / str(index)
        shutil.copytree(self.folder, destination)
        inputs = {
            p.relative_to(destination).as_posix(): digest(p)
            for p in destination.rglob("*")
            if p.is_file()
        }
        for relative, expected in inputs.items():
            if digest(self.folder / relative) != expected:
                raise ValueError("Compiler snapshot differs from its original input")

        def remap(argument):
            prefix = "-I" if argument.startswith("-I") else ""
            value = argument[len(prefix) :]
            path = Path(value)
            if path.is_relative_to(self.folder):
                return prefix + str(destination / path.relative_to(self.folder))
            return argument

        output_index = command.index("-o") + 1
        changed = [
            argument if i == output_index else remap(argument) for i, argument in enumerate(command)
        ]
        output = Path(command[output_index])
        if any(job["binary"] == output for job in self.jobs):
            raise ValueError("Compiler batch output ownership is not exclusive")
        self.jobs.append(
            dict(
                index=index,
                original_command=command,
                command=changed,
                timeout=timeout,
                text=text,
                directory=destination,
                inputs=inputs,
                binary=output,
            )
        )

    def execute(self, job):
        actual = {
            p.relative_to(job["directory"]).as_posix(): digest(p)
            for p in job["directory"].rglob("*")
            if p.is_file()
        }
        if actual != job["inputs"]:
            raise ValueError("Frozen compiler input drift before execution")
        prefix = self.records / str(job["index"])
        record = dict(
            original_command=job["original_command"],
            command=job["command"],
            timeout_seconds=job["timeout"],
            original_input_bytes_verified=True,
            frozen_input_sha256=job["inputs"],
            compiler_concurrency_limit=2,
            started_monotonic_ns=time.monotonic_ns(),
            state="running",
        )
        prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        result = None
        error = None
        try:
            # Direct files retain any compiler output even if pytest is killed.
            with (
                prefix.with_suffix(".stdout").open("wb") as stdout,
                prefix.with_suffix(".stderr").open("wb") as stderr,
            ):
                result = subprocess.run(
                    job["command"],
                    stdout=stdout,
                    stderr=stderr,
                    timeout=job["timeout"],
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = exc
        raw_stdout = prefix.with_suffix(".stdout").read_bytes()
        raw_stderr = prefix.with_suffix(".stderr").read_bytes()
        record.update(
            state="finished",
            finished_monotonic_ns=time.monotonic_ns(),
            returncode=result.returncode if result else None,
            timed_out=isinstance(error, subprocess.TimeoutExpired),
            error=str(error) if error else None,
            stdout_sha256=hashlib.sha256(raw_stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(raw_stderr).hexdigest(),
        )
        record["elapsed_seconds"] = (
            record["finished_monotonic_ns"] - record["started_monotonic_ns"]
        ) / 1e9
        if job["binary"].exists():
            record["binary_sha256"] = digest(job["binary"])
        prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        if self.terminal:
            with self.record_lock:
                self.terminal.write_line(
                    "native_fixture_compile "
                    + json.dumps(
                        {
                            key: value
                            for key, value in record.items()
                            if key != "frozen_input_sha256"
                        },
                        sort_keys=True,
                    )
                )
        if error:
            raise error
        return subprocess.CompletedProcess(
            job["command"],
            result.returncode,
            raw_stdout.decode() if job["text"] else raw_stdout,
            raw_stderr.decode() if job["text"] else raw_stderr,
        )

    def run(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Results remain in original profile order, including failures.
            results = list(pool.map(self.execute, self.jobs))
        for result in results:
            assert result.returncode == 0, result.stderr
        return results
