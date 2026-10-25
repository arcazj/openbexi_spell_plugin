"""Separate native authorization-only probes cannot inherit a DSS entrypoint config."""

from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "native_probe_profile",
    Path(__file__).resolve().parents[2] / "scripts/v08_native_consumption.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_control_probe_config_preserves_primary_driver_and_immutable_source():
    entry = {"revision": "a" * 40, "driver_binding": "simulator", "entrypoint": "main.py"}
    primary = {
        "native_driver": {"bindings": {"simulator": "original"}},
        "approved_sources": {"probe": entry},
        "worker_slots": {"slot": "original"},
    }
    isolated = module.isolate_audit_probe(primary)
    assert "native_driver" not in isolated
    assert isolated["approved_sources"]["probe"] == dict(entry, driver_binding="context-audit")
    assert primary["approved_sources"]["probe"]["driver_binding"] == "simulator"
    assert primary["native_driver"]["bindings"] == {"simulator": "original"}
    assert isolated["worker_slots"] == primary["worker_slots"]


def test_existing_audit_only_probe_profile_is_unchanged():
    primary = {"approved_sources": {"probe": {"driver_binding": "context-audit"}}}
    assert module.isolate_audit_probe(primary) == primary
