"""Isolate one reusable worker from the current joined-processor cache."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "idle_worker_fixture", ROOT / "server/tests/test_native_message_workers.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.fixture(scope="module")
def binaries(tmp_path_factory, request):
    original = fixture.BUILDER.reuse_native_message_instances

    def patched(source):
        original(source)
        fixture.BUILDER.reuse_native_message_workers(source)

    fixture.BUILDER.reuse_native_message_instances = patched
    try:
        return fixture.binaries.__wrapped__(tmp_path_factory, request)
    finally:
        fixture.BUILDER.reuse_native_message_instances = original


def test_sequential_cache_reuse_has_one_os_thread_and_no_stale_ticket(binaries, tmp_path):
    before = fixture.run(binaries["before"], "sequential")
    after = fixture.run(binaries["after"], "sequential")
    assert before["os_threads_created"] == 10000
    assert after["calls"] == 10000 and after["os_threads_created"] == 1
    assert after["processors_constructed"] == 1


@pytest.mark.parametrize(
    "mode",
    [
        "overflow",
        "concurrent",
        "cancel",
        "requests",
        "exceptions",
        "rebind",
        "collector_cancel",
        "bounded_cache",
        "oversized_identity",
    ],
)
def test_concurrency_cancellation_requests_and_recycled_objects(binaries, mode):
    if mode in {"bounded_cache", "oversized_identity"}:
        assert fixture.run(binaries["after"], mode)["passed"]
    else:
        assert fixture.run(binaries["before"], mode) == fixture.run(binaries["after"], mode)


def test_current_cache_without_thread_reuse_has_more_retention(binaries, tmp_path_factory, request):
    # Rebuild the existing fixture without the new scheduling helper.
    current = fixture.binaries.__wrapped__(tmp_path_factory, request)
    dedicated = fixture.run(current["after"], "retention")
    reused = fixture.run(binaries["after"], "retention")
    assert dedicated["calls"] == reused["calls"] == 10000
    assert dedicated["os_threads_created"] == 10000 and reused["os_threads_created"] == 1
    assert reused["heap_growth_bytes"] < dedicated["heap_growth_bytes"]
    import json

    (Path(binaries["after"]).parent / "retention-measurement.json").write_text(
        json.dumps(dict(dedicated=dedicated, reused=reused), indent=2) + "\n"
    )
