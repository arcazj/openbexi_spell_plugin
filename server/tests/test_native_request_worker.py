"""Compile real request lifecycle methods with the single idle callback worker.

Synchronization/transport adapters are component fixtures; actual source-bound
native handoff, installed IDE, lifecycle and sanitizer hours remain mandatory.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "request_worker_fixture", ROOT / "server/tests/test_native_message_workers.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    original = fixture.BUILDER.reuse_native_message_instances

    def patched(source):
        original(source)
        fixture.BUILDER.reuse_native_message_workers(source, requests=True)

    fixture.BUILDER.reuse_native_message_instances = patched
    try:
        return fixture.binaries.__wrapped__(tmp_path_factory)
    finally:
        fixture.BUILDER.reuse_native_message_instances = original


def test_all_request_callbacks_retain_less_heap_without_excluding_warmup(binaries):
    before = fixture.run(binaries["before"], "request_retention")
    after = fixture.run(binaries["after"], "request_retention")
    assert before["calls"] == after["calls"] == 10000
    assert before["os_threads_created"] == 10000 and after["os_threads_created"] == 1
    assert after["heap_growth_bytes"] < before["heap_growth_bytes"]
    (Path(binaries["after"]).parent / "request-retention.json").write_text(
        json.dumps(dict(dedicated=before, shared_idle=after), indent=2) + "\n"
    )


@pytest.mark.parametrize(
    "mode",
    [
        "request_nested",
        "request_nested_deep",
        "request_concurrent",
        "request_cancel",
        "request_rebind",
        "request_collector",
        "request_unwind",
        "message_thread_exit",
        "request_thread_exit",
        "message_pthread_cancel",
        "request_pthread_cancel",
    ],
)
def test_request_concurrency_nesting_cancellation_and_listener_lifetime(binaries, mode):
    assert fixture.run(binaries["before"], mode) == fixture.run(binaries["after"], mode)


@pytest.mark.parametrize("mode", ["overflow", "concurrent", "cancel", "rebind"])
def test_shared_request_slot_preserves_original_message_concurrency(binaries, mode):
    assert fixture.run(binaries["before"], mode) == fixture.run(binaries["after"], mode)
