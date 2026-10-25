"""Regression for real native owner RUN receipt-versus-status race.

The worker must never query PAUSED-only variables after a final RUN has
already been admitted but before its durable consumption receipt arrives.
"""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "driver_plugin/src", ROOT / "host_runtime/python"):
    sys.path.insert(0, str(path))
spec = importlib.util.spec_from_file_location(
    "v08_owner_resume_race", ROOT / "host_runtime/python/v08_worker.py"
)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class NativeSession:
    def __init__(self, status):
        self.status = status
        self.queries = []

    def request(self, operation, **kwargs):
        self.queries.append(operation)
        if operation == "REQ_EXEC_INFO":
            return {"ExecutorStatus": self.status}
        if operation == "REQ_GET_VARIABLES":
            if self.status != "PAUSED":
                raise RuntimeError("Variable analysis cannot be done in current status")
            return {"TotalChunks": "1", "VarName": "FIRST", "VarValue": "1"}
        raise AssertionError(operation)


@pytest.mark.parametrize("status", ["RUNNING", "FINISHED", "ABORTED", "ERROR"])
def test_inflight_final_owner_consumption_never_queries_paused_only_variables(status):
    session = NativeSession(status)
    controls = SimpleNamespace(owner_consume_attempted={"first", "pause", "resume"})
    assert worker.owner_resume_paused_guard(session, controls) is False
    assert session.queries == ["REQ_EXEC_INFO"]


def test_unadmitted_resume_is_rejected_before_variable_read():
    session = NativeSession("RUNNING")
    controls = SimpleNamespace(owner_consume_attempted={"first", "pause"})
    with pytest.raises(RuntimeError, match="before third owner consumption"):
        worker.owner_resume_paused_guard(session, controls)
    assert session.queries == ["REQ_EXEC_INFO"]


def test_still_paused_fixture_is_checked():
    session = NativeSession("PAUSED")
    controls = SimpleNamespace(owner_consume_attempted={"first", "pause"})
    assert worker.owner_resume_paused_guard(session, controls) is True
    assert session.queries == ["REQ_EXEC_INFO", "REQ_GET_VARIABLES"]


def test_lost_variable_read_ack_after_admitted_resume_keeps_uncertainty():
    class Race(NativeSession):
        def request(self, operation, **kwargs):
            if operation == "REQ_GET_VARIABLES":
                raise RuntimeError("Variable analysis cannot be done in current status")
            return super().request(operation, **kwargs)

    session = Race("PAUSED")
    controls = SimpleNamespace(owner_consume_attempted={"first", "pause", "resume"})
    assert worker.owner_resume_paused_guard(session, controls) is False
    controls.owner_consume_attempted.remove("resume")
    with pytest.raises(RuntimeError, match="Variable analysis"):
        worker.owner_resume_paused_guard(session, controls)
