"""Fresh real-native boundary diagnostic; not v0.8 launch/driver qualification.

Uses the immutable published v0.7 container's original GPL native bridge in an
isolated container. Nothing is copied into the Apache-licensed server package.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
import uuid

ARCHIVE = "https://github.com/arcazj/openbexi_spell_plugin/releases/download/v0.7/openbexi-spell-v0.7-linux-amd64.tar.gz"
ARCHIVE_SHA256 = "d7535367869416f807b376dd0289b62a8aec70a9891a78e59a4e1535a03b25cd"
ARCHIVE_SIZE = 207521854
IMAGE = "sha256:d99b095d65c7fef008f9e6c02ff95c678cff295ee85a129f7a62fc0b795b1283"
PROBE = r"""
import json, os, queue, time, sys
from pathlib import Path
sys.path.insert(0, '/opt/host')
from native import NativeSession
session = NativeSession('/fixture', '/fixture/procedure.py', {})
report = {'native_executor_tested': True, 'v08_launch_qualified': False, 'runtime_enabled': False}
events = []
def pump():
    while True:
        try:
            item = session.events.get_nowait()
        except queue.Empty:
            break
        if item.get('event') == 'connectionError':
            raise RuntimeError('Native connection ended')
        events.append(item)
        if len(events) > 512:
            raise RuntimeError('Native event diagnostic capacity exceeded')
session.pump = pump
try:
    session.start()
    report['initial_status'] = session.request('REQ_EXEC_INFO', context=True)['ExecutorStatus']
    processes = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            executable = os.readlink(path / 'exe')
            command = (path / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if Path(executable).name.startswith('SPELL-'):
                processes.append({'pid': int(path.name), 'executable': executable, 'command': command})
        except (OSError, ValueError):
            continue
    report['native_processes'] = processes
    assert len({p['pid'] for p in processes}) >= 3, processes
    assert report['initial_status'] == 'PAUSED', report
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        pump()
        status = session.request('REQ_EXEC_INFO', context=True)['ExecutorStatus']
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            break
        time.sleep(.05)
    assert status == 'FINISHED', status
    report['final_status'] = status
    report['notification_count'] = len(events)
finally:
    session.close()
print(json.dumps(report), flush=True)
"""


def main():
    root = Path(__file__).resolve().parents[1]
    output = (
        root / ".qualification" / "v08-native-boundary" / ("run-" + uuid.uuid4().hex)
    )
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        passed=False,
        archive_sha256=ARCHIVE_SHA256,
        archive_size=ARCHIVE_SIZE,
        image=IMAGE,
        runtime_enabled=False,
        v08_launch_qualified=False,
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        git_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
    )
    name = "spell-v08-boundary-" + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix="spell-native-boundary-") as temp:
            temp = Path(temp)
            # Permit the fixed non-root container identity to traverse its fixture.
            temp.chmod(0o755)
            archive = temp / "runtime.tar.gz"
            sha, size = hashlib.sha256(), 0
            deadline = time.monotonic() + 120
            with (
                urlopen(ARCHIVE, timeout=30) as response,
                archive.open("xb") as destination,
            ):
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > ARCHIVE_SIZE or time.monotonic() > deadline:
                        raise RuntimeError(
                            "Runtime download exceeds its declared bound"
                        )
                    sha.update(chunk)
                    destination.write(chunk)
            if size != ARCHIVE_SIZE or sha.hexdigest() != ARCHIVE_SHA256:
                raise RuntimeError("Published runtime bytes differ")
            loaded = subprocess.run(
                ["docker", "load", "--input", str(archive)],
                capture_output=True,
                timeout=120,
            )
            (output / "docker-load.log").write_bytes(loaded.stdout + loaded.stderr)
            loaded.check_returncode()
            actual = subprocess.check_output(
                ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE],
                text=True,
                timeout=10,
            ).strip()
            if actual != IMAGE:
                raise RuntimeError("Loaded image identity differs")
            fixture = temp / "fixture"
            fixture.mkdir(mode=0o755)
            (fixture / "procedure.py").write_text(
                "VALUE = 21 * 2\nprint('native boundary completed', VALUE)\n"
            )
            (fixture / "probe.py").write_text(PROBE)
            command = [
                "docker",
                "run",
                "--name",
                name,
                "--rm",
                "--init",
                "--read-only",
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "256",
                "--memory",
                "768m",
                "--cpus",
                "2",
                "--user",
                "10003:10003",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "--tmpfs",
                "/workspace:rw,nosuid,nodev,size=16m",
                "--mount",
                f"type=bind,src={fixture},dst=/fixture,readonly",
                "--entrypoint",
                "python",
                IMAGE,
                "-I",
                "/fixture/probe.py",
            ]
            report["command"] = command
            run = subprocess.run(command, capture_output=True, timeout=90)
            (output / "native.stdout.log").write_bytes(run.stdout)
            (output / "native.stderr.log").write_bytes(run.stderr)
            run.check_returncode()
            native = json.loads(run.stdout.decode().strip().splitlines()[-1])
            report["native"] = native
            report["passed"] = native["final_status"] == "FINISHED"
    except Exception as error:
        report["error"] = str(error)
    finally:
        try:
            subprocess.run(
                ["docker", "rm", "--force", name], capture_output=True, timeout=15
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), error=report.get("error"))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
