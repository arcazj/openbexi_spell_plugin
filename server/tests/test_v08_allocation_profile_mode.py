"""The optional profiler is isolated from mandatory recovery acceptance."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_allocation_profile_rejected_outside_live_recovery():
    script = ROOT / "scripts" / "qualify_v08_native_launch.py"
    args = [sys.executable, str(script), "--native-allocation-diagnostics"]
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert "allocation diagnostics require" in result.stderr


def test_allocation_profile_is_opt_in_and_scope_limited():
    sys.path.insert(0, str(ROOT / "server" / "src"))
    script = ROOT / "scripts" / "v08_native_consumption.py"
    spec = importlib.util.spec_from_file_location("v08_consumption_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.allocation_diagnostic_args
    assert args(live_handoff=True, enabled=False) == []
    assert args(live_handoff=False, enabled=False) == []
    enabled = args(live_handoff=True, enabled=True)
    assert enabled == ["--env", "OPENBEXI_V08_ALLOCATION_DIAGNOSTICS=1"]
    try:
        args(live_handoff=False, enabled=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Profiler leaked into a non-recovery worker")
