"""Replay the native measured five-callback peak without queuing or warmup exclusion."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "burst_fixture", ROOT / "server/tests/test_native_message_workers.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_measured_parallel_peak_reuses_threads_without_limiting_callbacks(
    tmp_path_factory, request
):
    original_instances = fixture.BUILDER.reuse_native_message_instances
    original_workers = fixture.BUILDER.reuse_native_message_workers
    outcomes = {}
    try:
        for label, previous in [("one_idle", True), ("five_idle", False)]:

            def patched(source):
                original_instances(source)
                original_workers(source, requests=True)
                if previous:
                    header = source / "include/SPELL_IPC/v08_message_workers.H"
                    text = header.read_text()
                    assert text.count("static constexpr size_t capacity = 5;") == 1
                    header.write_text(text.replace("capacity = 5;", "capacity = 1;"))

            fixture.BUILDER.reuse_native_message_instances = patched
            binaries = fixture.binaries.__wrapped__(tmp_path_factory, request)
            outcomes[label] = fixture.run(binaries["after"], "retention_bursts")
            # This must exceed both slot capacities, including nested waits.
            assert fixture.run(binaries["after"], "overflow") == {"parallel_callbacks": 24}
            assert fixture.run(binaries["after"], "request_nested_deep") == {
                "nested_completed": True,
                "distinct_callback_threads": 13,
            }
            (Path(binaries["after"]).parent / "burst-retention.json").write_text(
                json.dumps(outcomes[label], indent=2) + "\n"
            )
    finally:
        fixture.BUILDER.reuse_native_message_instances = original_instances
    before, after = outcomes["one_idle"], outcomes["five_idle"]
    assert before["calls"] == after["calls"] == 10000
    assert before["simultaneous"] == after["simultaneous"] == 5
    assert before["os_threads_created"] == 8001 and after["os_threads_created"] == 5
    assert after["heap_growth_bytes"] < before["heap_growth_bytes"]
