"""Execute the device shell with fake privileged commands, never kernel swap."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEVICE = ROOT / "scripts/v08_memory_swap_device.sh"

FAKE = r"""#!PYTHON
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == "id":
    print(1001)
elif name == "wc":
    print(1)
elif name == "sudo":
    assert args[0] == "-n"
    assert args[1] in {"losetup", "cryptsetup", "mkswap", "swapon", "swapoff"}
    os.execv(str(pathlib.Path(__file__).parent / args[1]), args[1:])
else:
    row = {"command": name, "args": args}
    if name == "dd":
        file = pathlib.Path(next(a[3:] for a in args if a.startswith("of=")))
        file.write_bytes(b"mock backing; no kernel device")
        row["file_mode"] = file.stat().st_mode & 0o777
        row["directory_mode"] = file.parent.stat().st_mode & 0o777
    elif name == "losetup" and "--find" in args:
        print("/dev/mock-openbexi-loop")
    elif name == "cryptsetup" and "open" in args:
        assert args[args.index("--key-file") + 1] == "/dev/urandom"
    with open(os.environ["FAKE_ACTIONS"], "a") as stream:
        stream.write(json.dumps(row) + "\n")
"""
CHILD = r"""
import json, os, pathlib, sys
mask = os.umask(0)
os.umask(mask)
root = pathlib.Path(sys.argv[1])
root.mkdir()
(root / "dss").mkdir()
(root / "dss" / "engine.py").write_text("class DssEngine: pass\n")
print(json.dumps({"umask": mask, "code_mode": root.stat().st_mode & 0o777,
                  "engine_mode": (root / "dss/engine.py").stat().st_mode & 0o777}))
sys.exit(int(sys.argv[2]))
"""


def run_device(tmp_path, mask="022", exit_code=0, script=DEVICE):
    mocks = tmp_path / "mock-bin"
    mocks.mkdir()
    for name in ("id", "wc", "sudo", "dd", "losetup", "cryptsetup", "mkswap", "swapon", "swapoff"):
        path = mocks / name
        path.write_text(FAKE.replace("#!PYTHON", "#!" + sys.executable + " -S"))
        path.chmod(0o755)
    actions = tmp_path / "actions.jsonl"
    environment = dict(
        os.environ,
        PATH=str(mocks) + os.pathsep + os.environ["PATH"],
        GITHUB_ACTIONS="true",
        RUNNER_ENVIRONMENT="github-hosted",
        RUNNER_OS="Linux",
        GITHUB_RUN_ID="998877665544332211",
        GITHUB_RUN_ATTEMPT="1",
        RUNNER_TEMP=str(tmp_path),
        FAKE_ACTIONS=str(actions),
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            'umask "$1"; shift; exec bash "$@"',
            "test",
            mask,
            str(script),
            sys.executable,
            "-c",
            CHILD,
            str(tmp_path / "code"),
            str(exit_code),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=15,
    )
    return result, [json.loads(line) for line in actions.read_text().splitlines()]


@pytest.mark.parametrize("mask", ["022", "027", "077"])
def test_private_swap_creation_preserves_callers_umask(tmp_path, mask):
    result, actions = run_device(tmp_path, mask)
    assert result.returncode == 0, result.stdout + result.stderr
    child = json.loads(result.stdout)
    assert child["umask"] == int(mask, 8)
    assert child["code_mode"] == 0o777 & ~int(mask, 8)
    assert child["engine_mode"] == 0o666 & ~int(mask, 8)
    backing = next(row for row in actions if row["command"] == "dd")
    assert backing["file_mode"] == 0o600
    assert backing["directory_mode"] == 0o700
    assert not list(tmp_path.glob("openbexi-memory-swap.*"))
    assert [row["command"] for row in actions][-3:] == ["swapoff", "cryptsetup", "losetup"]


@pytest.mark.parametrize("exit_code", [1, 2, 42, 130])
def test_comparison_failure_is_preserved_after_device_cleanup(tmp_path, exit_code):
    result, actions = run_device(tmp_path, exit_code=exit_code)
    assert result.returncode == exit_code
    assert json.loads(result.stdout)["code_mode"] & 0o005 == 0o005
    assert actions[-1]["command"] == "losetup"
    assert not list(tmp_path.glob("openbexi-memory-swap.*"))


def test_changed_permissions_reproduce_dss_cross_uid_failure(tmp_path):
    # Replay the exact prior helper, rather than replacing the runtime or test gate.
    prior = DEVICE.read_text().replace(
        '(umask 077; dd if=/dev/zero of="$file" bs=1M count=2048 conv=fsync status=none)',
        'umask 077\ndd if=/dev/zero of="$file" bs=1M count=2048 conv=fsync status=none',
    )
    assert prior != DEVICE.read_text()
    baseline = tmp_path / "prior.sh"
    baseline.write_text(prior)
    result, _ = run_device(tmp_path, script=baseline)
    assert result.returncode == 0
    child = json.loads(result.stdout)
    assert child["umask"] == 0o077
    assert child["code_mode"] == 0o700
    assert child["engine_mode"] == 0o600
    assert child["code_mode"] & 0o005 != 0o005
