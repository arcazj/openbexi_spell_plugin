"""Incoming finish() must recycle before clear() destroys its fields."""

import pytest
from test_native_message_storage import run, storage_binaries as storage_fixture


@pytest.fixture(scope="session")
def clear_binaries(tmp_path_factory):
    return storage_fixture.__wrapped__(tmp_path_factory)


def test_native_incoming_clear_lifecycle_reuses_owned_storage(clear_binaries):
    before = run(clear_binaries["before"], "clear_bench")
    after = run(clear_binaries["after"], "clear_bench")
    assert before["allocated_bytes"] > 20_000_000
    assert after["allocations"] == after["allocated_bytes"] == 0
