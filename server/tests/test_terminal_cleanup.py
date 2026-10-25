"""Cleanup evidence must identify the original isolated process family."""

import importlib.util
import ast
from pathlib import Path
import os
import select
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "terminal_cohort", ROOT / "scripts/v08_terminal_cohort.py"
)
cohort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cohort)


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
