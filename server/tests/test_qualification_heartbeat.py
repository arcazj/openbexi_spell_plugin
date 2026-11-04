"""Lost keepalive evidence remains bounded and never includes credentials."""

import importlib.util
import json
from pathlib import Path

import pytest

from openbexi_spell_server.contracts import Fault

spec = importlib.util.spec_from_file_location(
    "qualification_heartbeat",
    Path(__file__).resolve().parents[2] / "scripts/v08_controller_heartbeat.py",
)
heartbeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heartbeat)


@pytest.fixture
def manual_controller(monkeypatch):
    # Drive the actual renewal loop deterministically, without a background race.
    monkeypatch.setattr(heartbeat.threading.Thread, "start", lambda self: None)
    monkeypatch.setattr(heartbeat.threading.Thread, "join", lambda self, timeout: None)
    now = [100.0]
    monkeypatch.setattr(heartbeat.time, "monotonic", lambda: now[0])
    yield now
    heartbeat.HeartbeatController.close_all()


def one_iteration(controller, monkeypatch):
    waits = iter((False, True))
    monkeypatch.setattr(controller.stop, "wait", lambda timeout: next(waits))
    controller._run()


def test_failed_renewal_retains_cause_without_retry_or_secret(manual_controller, monkeypatch):
    calls = []

    def call(method, payload, subject):
        calls.append(method)
        if method == "session.open":
            return dict(
                connection_id="private-id", heartbeat_nonce="private-nonce", lease_seconds=9
            )
        raise Fault(503, "context_unavailable") from TimeoutError("private-nonce")

    controller = heartbeat.HeartbeatController(call)
    controller("session.open", {}, "private-subject")
    manual_controller[0] = 104.0
    one_iteration(controller, monkeypatch)
    one_iteration(controller, monkeypatch)
    reports = heartbeat.HeartbeatController.close_all()
    assert calls == ["session.open", "session.heartbeat"]
    assert not heartbeat.HeartbeatController.instances
    assert reports == [
        dict(
            renewals=0,
            failures=1,
            active_sessions=0,
            failure_tail=[
                dict(
                    elapsed_seconds=4.0,
                    call_seconds=0.0,
                    overdue_seconds=1.0,
                    lease_seconds=9,
                    error_type="Fault",
                    cause_type="TimeoutError",
                    status=503,
                    code="context_unavailable",
                )
            ],
        )
    ]
    assert "private" not in json.dumps(reports)


def test_success_rotates_nonce_and_intentional_loss_is_not_failure(manual_controller, monkeypatch):
    seen = []

    def call(method, payload, subject):
        seen.append(payload)
        if method == "session.open":
            return dict(connection_id="session", heartbeat_nonce="first", lease_seconds=9)
        return dict(heartbeat_nonce="rotated", lease_seconds=9)

    controller = heartbeat.HeartbeatController(call)
    controller("session.open", {})
    manual_controller[0] = 103.0
    one_iteration(controller, monkeypatch)
    assert seen[-1]["heartbeat_nonce"] == "first"
    assert controller.sessions["session"]["nonce"] == "rotated"
    assert controller.lose("session")["lease_seconds"] == 9
    assert controller.diagnostics() == dict(
        renewals=1, failures=0, active_sessions=0, failure_tail=[]
    )


def test_failure_history_is_bounded_and_arbitrary_codes_are_redacted(
    manual_controller, monkeypatch
):
    def call(method, payload, subject):
        if method == "session.open":
            return dict(connection_id="session", heartbeat_nonce="secret", lease_seconds=9)
        raise Fault(503, "credential=secret")

    controller = heartbeat.HeartbeatController(call)
    for _ in range(20):
        controller("session.open", {})
        manual_controller[0] += 4
        one_iteration(controller, monkeypatch)
    result = controller.diagnostics()
    assert result["failures"] == 20
    assert len(result["failure_tail"]) == 16
    assert all(row["code"] is None for row in result["failure_tail"])
    assert "secret" not in json.dumps(result)
