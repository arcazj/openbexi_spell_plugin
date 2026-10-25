"""Bounded queue draining must not confuse lifetime traffic with backlog."""

import ast
from pathlib import Path
import queue
from types import SimpleNamespace

import pytest


@pytest.fixture
def notifications():
    source = Path(__file__).resolve().parents[2] / "host_runtime/python/v08_worker.py"
    tree = ast.parse(source.read_text())
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "drain_native_notifications"
    )
    reports = []
    namespace = {"queue": queue, "emit": lambda name, **body: reports.append((name, body))}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    seen = []
    session = SimpleNamespace(instance="root#1", events=queue.Queue(maxsize=256))
    children = SimpleNamespace(observe=seen.append)
    return namespace["drain_native_notifications"], session, children, seen, reports


def test_sustained_drained_traffic_exceeds_old_lifetime_cap_without_loss(notifications):
    drain, session, children, seen, _ = notifications
    count = 0
    for batch in range(40):
        for offset in range(128):
            session.events.put_nowait(dict(message=dict(index=batch * 128 + offset)))
        while not session.events.empty():
            count = drain(session, children, None, "execution", count)
    assert count == 5120
    assert [m["index"] for m in seen] == list(range(5120))


def test_busy_backlog_yields_before_all_notifications_to_allow_rpc_progress(notifications):
    drain, session, children, seen, _ = notifications
    for _ in range(200):
        session.events.put_nowait(dict(message=dict(id="status")))
    count = drain(session, children, None, "execution", 0)
    assert 0 < count < 200 and not session.events.empty()
    while not session.events.empty():
        count = drain(session, children, None, "execution", count)
    assert count == len(seen) == 200


def test_real_connection_failure_is_fatal_and_does_not_forward_later_events(notifications):
    drain, session, children, seen, reports = notifications
    session.events.put_nowait(dict(event="connectionError", error="private native details"))
    session.events.put_nowait(dict(message=dict(id="later")))
    with pytest.raises(RuntimeError, match="Native notification connection failed"):
        drain(session, children, None, "execution", 0)
    assert not seen and not session.events.empty()
    assert reports and "private native details" not in repr(reports)


@pytest.mark.parametrize("registered", [False, True])
def test_child_open_still_requires_the_original_admitted_member(notifications, registered):
    drain, session, children, seen, reports = notifications
    session.events.put_nowait(
        dict(message=dict(id="MSG_EXEC_OP", fields=dict(ExecOp="OPEN", ProcId="child#0")))
    )
    gate = SimpleNamespace(started={"child#0": "original-admission"} if registered else {})
    if registered:
        assert drain(session, children, gate, "execution", 0) == 1
        assert len(seen) == 1 and reports[0][0] == "native-child-open"
    else:
        with pytest.raises(RuntimeError, match="Native child admission is not qualified"):
            drain(session, children, gate, "execution", 0)
        assert not seen and not reports
