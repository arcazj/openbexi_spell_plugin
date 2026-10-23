import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from openbexi_spell_server.contracts import Fault
from openbexi_spell_server.store import ContextStore


def payload(expected=0, value=1, name="key"):
    return dict(key=name, expected_revision=expected, value=value)


def test_atomic_concurrent_compare_and_swap(tmp_path):
    store = ContextStore(tmp_path, "A")
    try:

        def attempt(n):
            try:
                return store.cas("alice", "request-" + str(n), payload())["revision"]
            except Fault as error:
                return error.code

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(attempt, range(100)))
        assert results.count(1) == 1
        assert results.count("blackboard_revision_conflict") == 99
        assert store.snapshot()["blackboard"]["key"] == {"revision": 1, "value": 1}
    finally:
        store.close()


def test_restart_preserves_data_sequence_and_idempotency_but_rotates_incarnation(tmp_path):
    store = ContextStore(tmp_path, "A")
    first = store.cas("alice", "one", payload())
    incarnation = store.incarnation
    store.close()
    restored = ContextStore(tmp_path, "A")
    try:
        assert restored.incarnation != incarnation
        assert restored.snapshot()["sequence"] > first["sequence"]
        assert restored.cas("alice", "one", payload()) == first
        with pytest.raises(Fault, match="idempotency_payload_conflict"):
            restored.cas("alice", "one", payload(value=2))
        assert restored.cas("bob", "one", payload(1, 2))["revision"] == 2
    finally:
        restored.close()


def test_same_state_directory_cannot_change_context_identity(tmp_path):
    store = ContextStore(tmp_path, "A")
    store.close()
    with pytest.raises(ValueError, match="different Context"):
        ContextStore(tmp_path, "B")
    reopened = ContextStore(tmp_path, "A")
    reopened.close()


def test_second_real_process_is_excluded_before_opening_state(tmp_path):
    store = ContextStore(tmp_path, "A")
    try:
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        command = [
            sys.executable,
            "-c",
            "from openbexi_spell_server.store import ContextStore; "
            "import sys; ContextStore(sys.argv[1], 'A')",
            str(tmp_path),
        ]
        result = subprocess.run(command, env=environment, capture_output=True, timeout=5)
        assert result.returncode != 0
        assert b"BlockingIOError" in result.stderr
        assert store.snapshot()["sequence"] == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    "limit,error",
    [
        ("max_idempotency", "idempotency_capacity_reached"),
        ("max_keys", "blackboard_capacity_reached"),
        ("max_events", "audit_capacity_reached"),
    ],
)
def test_capacity_failure_rolls_back_value_revision_and_event(tmp_path, limit, error):
    bound = 2 if limit == "max_events" else 1
    store = ContextStore(tmp_path, "A", **{limit: bound})
    try:
        original = store.cas("alice", "one", payload())
        before = store.snapshot()
        with pytest.raises(Fault, match=error):
            store.cas("alice", "two", payload(name="other"))
        assert store.snapshot() == before
        assert store.cas("alice", "one", payload()) == original
    finally:
        store.close()


def test_sqlite_write_failure_fences_service(tmp_path):
    store = ContextStore(tmp_path, "A")
    try:
        store.db.execute("PRAGMA query_only=ON")
        with pytest.raises(Fault, match="state_unavailable"):
            store.cas("alice", "one", payload())
        assert store.failed
        with pytest.raises(Fault, match="state_unavailable"):
            store.snapshot()
    finally:
        store.close()


def test_snapshot_excludes_values_and_service_credentials(tmp_path):
    store = ContextStore(tmp_path, "A")
    try:
        store.cas("alice", "one", payload(value="context-member-data"))
        result = store.snapshot(values=False)
        assert result["blackboard_revisions"] == {"key": 1}
        assert "context-member-data" not in json.dumps(result)
        assert result["runtime_enabled"] is False
    finally:
        store.close()
