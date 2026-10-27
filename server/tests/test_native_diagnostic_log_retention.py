"""Exact-source native log retention; do not modify procedure or audit logs."""

import hashlib
import importlib.util
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "lib/SPELL_UTIL/src/SPELLlog.C"
OLD = "RollingFileAppender(LOG4CPLUS_TEXT(logfilename), 10*1024*1024, 5, true, true)"
NEW = "RollingFileAppender(LOG4CPLUS_TEXT(logfilename), 1024*1024, 1, true, true)"


def builder():
    spec = importlib.util.spec_from_file_location(
        "log_retention_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def logger_source(tmp_path):
    path = tmp_path / RELATIVE
    path.parent.mkdir(parents=True)
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        path.write_bytes(archive.read(RELATIVE))
    return path


def test_only_size_and_backup_count_change(tmp_path):
    path = logger_source(tmp_path)
    before = path.read_text()
    builder().bound_native_diagnostic_logs(tmp_path)
    assert path.read_text() == before.replace(OLD, NEW)
    # Default native diagnostic inventory: Context, Listener, and two Executors.
    assert 4 * 1024**2 * (1 + 1) == 8 * 1024**2
    assert 4 * 10 * 1024**2 * (1 + 5) == 240 * 1024**2


def test_original_asrun_and_warmstart_sources_are_not_touched(tmp_path):
    logger_source(tmp_path)
    witnesses = {}
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        for name in archive.namelist():
            if "asrun" in name.lower() and name.endswith((".C", ".H")):
                path = tmp_path / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
                witnesses[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert witnesses
    builder().bound_native_diagnostic_logs(tmp_path)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in witnesses.items())


@pytest.mark.parametrize("change", ["comment", "duplicate", "reapply"])
def test_drift_and_duplicate_application_are_rejected_without_mutation(tmp_path, change):
    path = logger_source(tmp_path)
    if change == "comment":
        path.write_text(path.read_text() + "\n// different source\n")
    elif change == "duplicate":
        path.write_text(path.read_text() + OLD)
    else:
        builder().bound_native_diagnostic_logs(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="preimage differs"):
        builder().bound_native_diagnostic_logs(tmp_path)
    assert path.read_bytes() == before
