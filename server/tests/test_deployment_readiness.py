"""Both delegated TLS Contexts must be ready before prelaunch mutations start."""

import importlib.util
from pathlib import Path
import re
import runpy
from types import SimpleNamespace
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "prelaunch_probe", ROOT / "deploy/v0.8/qualify_compose.py"
)
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


@pytest.fixture
def clock(monkeypatch):
    value = SimpleNamespace(now=0.0)

    def sleep(seconds):
        value.now += seconds

    monkeypatch.setattr(
        probe_module, "time", SimpleNamespace(monotonic=lambda: value.now, sleep=sleep)
    )
    return value


def healthy(context):
    return dict(
        schema="openbexi.listener/1",
        result=dict(context_id=context, status="ready", runtime_enabled=False),
    )


@pytest.mark.parametrize("delayed", ["A", "B"])
def test_readiness_waits_for_both_contexts_without_mutation_or_replay(clock, delayed):
    calls, counts = [], {"A": 0, "B": 0}

    def call(subject, method, path):
        context = path.split("/")[3]
        assert subject == "alice" and method == "GET" and path.endswith("/health")
        counts[context] += 1
        code = 503 if context == delayed and counts[context] == 1 else 200
        calls.append((context, code))
        return code, healthy(context)

    probe_module.ready(SimpleNamespace(call=call))
    assert counts[delayed] >= 2 and counts["B" if delayed == "A" else "A"] >= 1
    assert set(calls[-2:]) == {("A", 200), ("B", 200)}
    assert clock.now < 65


def test_unready_second_context_uses_original_shared_budget(clock):
    calls = []

    def call(subject, method, path):
        calls.append((subject, method, path))
        context = path.split("/")[3]
        return (200 if context == "A" else 503), healthy(context)

    with pytest.raises(RuntimeError, match="B.*HTTP_503"):
        probe_module.ready(SimpleNamespace(call=call))
    assert 65 <= clock.now < 65.5
    assert all(method == "GET" for _, method, _ in calls)


def test_readiness_pin_failure_is_not_retried(clock):
    calls = []

    def call(*args):
        calls.append(args)
        raise AssertionError("Pinned gateway leaf differs before any request")

    with pytest.raises(AssertionError, match="Pinned gateway"):
        probe_module.ready(SimpleNamespace(call=call))
    assert len(calls) == 1 and clock.now == 0


def test_prelaunch_image_markers_match_the_installed_package_version():
    version = tomllib.loads((ROOT / "server/pyproject.toml").read_text())["project"]["version"]
    deployment = ROOT / "deploy/v0.8"
    expected = "openbexi-spell-server:" + version + "-prelaunch"
    assert runpy.run_path(str(deployment / "render_kubernetes.py"))["AUTHORITY_IMAGE"] == expected
    images = re.findall(
        r"image: (openbexi-spell-server:\S+)", (deployment / "compose.yaml").read_text()
    )
    assert images == [expected] * 4
    assert (
        f'org.opencontainers.image.version="{version}"'
        in (deployment / "Dockerfile.server").read_text()
    )
