"""The optional profiler must never silently alter mandatory recovery evidence."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_allocation_profile_rejected_outside_live_recovery():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/qualify_v08_native_launch.py"),
         "--native-allocation-diagnostics"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 2
    assert "allocation diagnostics require --native-handoff or --native-ide" in result.stderr


def test_allocation_profile_is_opt_in_and_scope_limited():
    sys.path.insert(0, str(ROOT / "server/src"))
    spec = importlib.util.spec_from_file_location(
        "native_consumption_allocation_test", ROOT / "scripts/v08_native_consumption.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allocation_diagnostic_args(live_handoff=True, enabled=False) == []
    assert module.allocation_diagnostic_args(live_handoff=False, enabled=False) == []
    assert module.allocation_diagnostic_args(live_handoff=True, enabled=True) == [
        "--env", "OPENBEXI_V08_ALLOCATION_DIAGNOSTICS=1"
    ]
    try:
        module.allocation_diagnostic_args(live_handoff=False, enabled=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Profiler leaked into a non-recovery worker")
