"""Cleanup evidence must identify the original isolated process family."""

import importlib.util
import ast
import json
from pathlib import Path
import os
import select
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "terminal_cohort", ROOT / "scripts/v08_terminal_cohort.py"
)
cohort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cohort)

probe_spec = importlib.util.spec_from_file_location(
    "terminal_probe", ROOT / "host_runtime/python/terminal_probe.py"
)
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)


def test_every_supported_terminal_case_is_scheduled_by_native_qualification():
    assert set(cohort.CASES) == probe.CASES
    assert "forced-loss" in cohort.CASES


def test_forced_loss_observes_original_process_and_reports_unknown(tmp_path, monkeypatch):
    process = subprocess.Popen(["sleep", "30"])
    handle = os.pidfd_open(process.pid)
    events = []
    (tmp_path / "kill-native").touch()
    monkeypatch.setattr(probe, "Path", lambda value: tmp_path / Path(value).name)
    controls = SimpleNamespace(lock=threading.Lock(), owner_operations={}, owner_consumed=set())
    controls.poll_owner = lambda: None
    session = SimpleNamespace(instance="original")
    session.request = lambda *args, **kwargs: {"ExecutorStatus": "RUNNING"}
    admission = SimpleNamespace(members={"original": (process.pid, handle)})
    try:
        probe.run_terminal_probe(
            "forced-loss",
            session,
            controls,
            admission,
            None,
            None,
            lambda: None,
            None,
            lambda event, **data: events.append(dict(event=event, **data)),
        )
        process.wait(timeout=5)
        assert process.returncode == -9
        assert events[-1]["event"] == "native-terminal-observed"
        assert events[-1]["native_status"] == "UNKNOWN"
        assert events[-1]["hold_retained"] is True
        assert events[-1]["quiescence_proven"] is False
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        os.close(handle)


def test_private_terminal_profile_loads_in_isolated_python(tmp_path):
    worker = ast.parse((ROOT / "host_runtime/python/v08_worker.py").read_text())
    run = next(
        node for node in worker.body if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    validation = next(
        node
        for node in run.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "terminal_case is not None"
    )

    # Substitute only the operator mount location; execute the actual validation
    # block under the same -I mode, without relying on cwd or PYTHONPATH.
    class Mount(ast.NodeTransformer):
        def visit_Constant(self, node):
            return (
                ast.copy_location(ast.Constant(str(tmp_path)), node)
                if node.value == "/v08"
                else node
            )

    validation = Mount().visit(validation)
    (tmp_path / "terminal_probe.py").write_bytes(
        (ROOT / "host_runtime/python/terminal_probe.py").read_bytes()
    )
    program = (
        "import sys\nterminal_case='abort-paused'\nprompt_profile=True\n"
        "build_receipt={'native_terminal_hooks':True}\n" + ast.unparse(validation)
    )
    result = subprocess.run([sys.executable, "-I", "-c", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "change",
    [
        {"Id": "replacement-container"},
        {"Image": "substituted-image"},
        {"Running": True},
        {"Pid": 1},
        {"OOMKilled": True},
        {"ExitCode": 1},
    ],
)
def test_cleanup_rejects_replacement_survivor_and_unclean_exit(change):
    info = dict(
        Id="original-container",
        Image="exact-image",
        State=dict(Running=False, Pid=0, OOMKilled=False, ExitCode=0),
    )
    cohort.validate_stopped(info, "original-container", "exact-image")
    for key, value in change.items():
        (info if key in {"Id", "Image"} else info["State"])[key] = value
    with pytest.raises(RuntimeError, match="identity or clean exit"):
        cohort.validate_stopped(info, "original-container", "exact-image")


@pytest.mark.skipif(not hasattr(os, "pidfd_open"), reason="Linux pidfd qualification")
def test_original_process_handle_distinguishes_live_from_exited():
    process = subprocess.Popen(["sleep", "30"])
    handles = []
    try:
        handles = cohort.capture_process_handles(
            lambda *args: f"PID\n{process.pid}\n", "original-container"
        )
        assert len(handles) == 1
        assert not select.select(handles, [], [], 0)[0]
        process.terminate()
        process.wait(timeout=5)
        assert select.select(handles, [], [], 1)[0] == handles
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for handle in handles:
            os.close(handle)


def test_retirement_preserves_evidence_before_releasing_networks(tmp_path):
    names, networks = ["worker", "context", "unrelated"], ["private", "control", "unrelated"]
    calls = []

    def command(*args):
        calls.append(args)
        if args[1] == "inspect":
            return json.dumps(
                [
                    dict(
                        Id=args[2],
                        Image="exact-image",
                        State=dict(Running=False, Pid=0, ExitCode=0),
                        HostConfig=dict(Memory=768 * 1024 * 1024, ReadonlyRootfs=True),
                    )
                ]
            )
        if args[1] == "logs":
            return '{"event":"retained"}'
        if args[1] == "rm":
            assert args == ("docker", "rm", "worker", "context")
            for name in args[2:]:
                assert (tmp_path / (name + ".state.json")).is_file()
                assert "retained" in (tmp_path / (name + ".stdout.jsonl")).read_text()
        return ""

    cohort.retire_terminal_probe(
        command, tmp_path, "worker", "context", ("private", "control"), names, networks
    )
    assert names == networks == ["unrelated"]
    assert calls[0] == ("docker", "stop", "--time", "5", "context")
    assert calls[-2:] == [
        ("docker", "network", "rm", "private"),
        ("docker", "network", "rm", "control"),
    ]
