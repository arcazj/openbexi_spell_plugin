"""Bounded compiler parallelism over independently frozen fixture inputs.

Only compilation overlaps. All binaries finish building before the existing
fixture returns, so test order, native scenario concurrency and deadlines stay
unchanged. Every invocation retains its original timeout inside timed pytest.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shlex
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
                    timeout=min(
                        job["timeout"], max(0, job.get("deadline", float("inf")) - time.monotonic())
                    ),
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
        return self.run_all([self])

    @staticmethod
    def run_all(batches):
        """Build frozen batches with one shared two-compiler limit."""
        batches = list(batches)
        record_lock = threading.Lock()
        for batch in batches:
            batch.record_lock = record_lock
        jobs = [(batch, job) for batch in batches for job in batch.jobs]

        def execute(item):
            batch, job = item
            return batch.execute(job)

        with ThreadPoolExecutor(max_workers=2) as pool:
            # Results remain in original profile order, including failures.
            results = list(pool.map(execute, jobs))
        for result in results:
            assert result.returncode == 0, result.stderr
        return results

    def run_cached(self, cache):
        """Reuse only session-local, byte-verified identical native executables.

        Every scenario still starts a fresh process. Preprocessing and any
        required compilation remain inside the original timed pytest run.
        """
        pending = []
        descriptions = {}
        for job in self.jobs:
            job["deadline"] = time.monotonic() + job["timeout"]
            compiler = Path(shutil.which(job["command"][0])).resolve()
            prefix = str(job["directory"])
            command = job["command"]
            output_index = command.index("-o") + 1
            normalized_command = [
                "<OUTPUT>" if i == output_index else argument.replace(prefix, "<INPUT>")
                for i, argument in enumerate(command)
            ]
            sources = [
                argument for argument in command if Path(argument).suffix in {".cpp", ".cc", ".C"}
            ]
            flags = [
                argument
                for i, argument in enumerate(command[1:], 1)
                if argument not in sources and i not in {output_index - 1, output_index}
            ]
            # A byte-identical input tree alone is insufficient: include search,
            # macros and expanded __FILE__ can change executable tokens.
            preprocessed = []
            dependencies = {}
            for source_index, source in enumerate(sources):
                prefix = self.records / f"{job['index']}.preprocess-{source_index}"
                depfile = prefix.with_suffix(prefix.suffix + ".d")
                command = [str(compiler), *flags, "-E", "-P", "-MD", "-MF", str(depfile), source]
                with (
                    prefix.with_suffix(prefix.suffix + ".stdout").open("wb") as stdout,
                    prefix.with_suffix(prefix.suffix + ".stderr").open("wb") as stderr,
                ):
                    result = subprocess.run(
                        command,
                        stdout=stdout,
                        stderr=stderr,
                        timeout=max(0, job["deadline"] - time.monotonic()),
                    )
                raw_stdout = prefix.with_suffix(prefix.suffix + ".stdout").read_bytes()
                raw_stderr = prefix.with_suffix(prefix.suffix + ".stderr").read_bytes()
                prefix.with_suffix(prefix.suffix + ".json").write_text(
                    json.dumps(
                        dict(
                            command=command,
                            returncode=result.returncode,
                            stdout_sha256=hashlib.sha256(raw_stdout).hexdigest(),
                            stderr_sha256=hashlib.sha256(raw_stderr).hexdigest(),
                            original_deadline_seconds=job["timeout"],
                        ),
                        indent=2,
                    )
                    + "\n"
                )
                assert result.returncode == 0, raw_stderr
                preprocessed.append(hashlib.sha256(raw_stdout).hexdigest())
                for name in shlex.split(depfile.read_text().replace("\\\n", "").split(":", 1)[1]):
                    normalized_dependency = name.replace(str(job["directory"]), "<INPUT>")
                    dependencies[normalized_dependency] = digest(Path(name))
            description = dict(
                compiler=str(compiler),
                compiler_sha256=digest(compiler),
                command=normalized_command,
                frozen_input_sha256=job["inputs"],
                preprocessed_sha256=preprocessed,
                dependency_sha256=dependencies,
                compiler_environment={
                    name: os.environ.get(name)
                    for name in (
                        "CPATH",
                        "CPLUS_INCLUDE_PATH",
                        "LIBRARY_PATH",
                        "GCC_EXEC_PREFIX",
                        "COMPILER_PATH",
                    )
                },
            )
            key = hashlib.sha256(json.dumps(description, sort_keys=True).encode()).hexdigest()
            descriptions[job["index"]] = key, description
            prior = cache.get(key)
            if prior is None:
                pending.append(job)
                continue
            if digest(prior["binary"]) != prior["binary_sha256"]:
                raise ValueError("Cached native executable byte drift")
            actual = {
                path.relative_to(job["directory"]).as_posix(): digest(path)
                for path in job["directory"].rglob("*")
                if path.is_file()
            }
            if actual != job["inputs"]:
                raise ValueError("Frozen compiler input drift before reuse")
            shutil.copy2(prior["binary"], job["binary"])
            if digest(job["binary"]) != prior["binary_sha256"]:
                raise ValueError("Reused native executable byte drift")
            record = dict(
                state="reused",
                source=description,
                original_command=job["original_command"],
                timeout_seconds=job["timeout"],
                original_compilation=prior["record"],
                binary_sha256=prior["binary_sha256"],
                fresh_scenario_processes_required=True,
            )
            (self.records / f"{job['index']}.reuse.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.execute, pending))
        for job, result in zip(pending, results):
            assert result.returncode == 0, result.stderr
            key, description = descriptions[job["index"]]
            if key not in cache and len(cache) >= 16:
                raise ValueError("Native executable cache capacity exceeded")
            cache[key] = dict(
                source=description,
                binary=job["binary"],
                binary_sha256=digest(job["binary"]),
                record=str(self.records / f"{job['index']}.json"),
            )
        return results
