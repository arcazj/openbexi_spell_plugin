"""Regression for cgroup-v2 transient peaks; native accounting stays mandatory."""

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def native_memory(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("qualify_v08_native_launch")


def test_kernel_transient_peak_is_retained_without_inventing_an_oom(native_memory, monkeypatch):
    values = dict(
        peak_bytes=1024 * 1024 * 1024 + 4096,
        limit_bytes=1024 * 1024 * 1024,
        oom_events=0,
        oom_kills=0,
    )
    monkeypatch.setattr(native_memory, "command", lambda *args: json.dumps(values))
    assert native_memory.family_memory("worker", 1024) == values


@pytest.mark.parametrize(
    "changed", [dict(limit_bytes=512 * 1024 * 1024), dict(oom_events=1), dict(oom_kills=1)]
)
def test_limit_substitution_and_real_oom_never_pass(native_memory, monkeypatch, changed):
    values = dict(
        peak_bytes=600 * 1024 * 1024, limit_bytes=1024 * 1024 * 1024, oom_events=0, oom_kills=0
    )
    values.update(changed)
    monkeypatch.setattr(native_memory, "command", lambda *args: json.dumps(values))
    with pytest.raises(RuntimeError, match="memory binding/OOM differs"):
        native_memory.family_memory("worker", 1024)
