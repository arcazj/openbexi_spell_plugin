"""Deterministic diagnostic fault paths; real socket/ledger tests remain separate."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "driver_plugin/src")]
from openbexi_spell_dss import fenced_transport as transport_module  # noqa: E402
from openbexi_spell_dss.context_driver import failure_chain  # noqa: E402
from openbexi_spell_dss.fenced_transport import CommandTiming, Transport  # noqa: E402
from openbexi_spell_dss.journal import UncertainEffect  # noqa: E402


class Clock:
    value = 0.0

    def monotonic(self):
        return self.value


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(transport_module, "time", value)
    return value


def test_metadata_failure_keeps_original_error_and_excludes_private_details(clock):
    secret = "private-endpoint-and-credential"
    transport = Transport.__new__(Transport)
    transport.arguments = lambda *_: []
    original = TimeoutError(secret)

    def state():
        clock.value += 0.125
        raise original

    transport.current_state = state
    admission = SimpleNamespace(validate=lambda *_: None)
    with pytest.raises(TimeoutError) as denied:
        transport.command("CMD1", [], {}, "op", lambda: None, admission=admission)
    assert denied.value is original
    chain = failure_chain(denied.value)
    assert secret not in str(chain)
    assert chain[0]["command_timing"] == {
        "elapsed_ms": 125,
        "steps": [
            dict(phase="preparation", stage=None, elapsed_ms=0, failed=False),
            dict(phase="metadata", stage=None, elapsed_ms=125, failed=True),
        ],
    }


@pytest.mark.parametrize("failed_phase", ["send", "receipt", "settle"])
@pytest.mark.parametrize(
    "failed_stage",
    ["TRANSPORT", "LOADING", "RELEASE", "ACKNOWLEDGEMENT", "ONBOARD_EXECUTION"],
)
def test_stage_failure_is_timed_without_resend_or_loss_of_uncertainty(
    clock, monkeypatch, failed_phase, failed_stage
):
    transport = Transport.__new__(Transport)
    transport.arguments = lambda *_: []
    transport.current_state = lambda: dict(epoch=1, scenario_id="scenario")
    transport.epoch, transport.scenario = 1, "scenario"
    transport.database = SimpleNamespace(revision=1, digest="digest")
    transport.tc_address = ("127.0.0.1", 1234)
    calls, body = [], {}
    original = TimeoutError("private-upstream-detail")

    stages = {
        "TRANSPORT": "ACCEPTED",
        "LOADING": "LOADED",
        "RELEASE": "RELEASED",
        "ACKNOWLEDGEMENT": "ACKNOWLEDGED",
        "ONBOARD_EXECUTION": "SUCCEEDED",
    }

    def phase(name, stage):
        calls.append((name, stage))
        if name == failed_phase and stage == failed_stage:
            clock.value += 0.2
            raise original

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append("close")

        def settimeout(self, _):
            pass

    class Admission:
        def validate(self, *_):
            pass

        def send(self, stage, connection, packet):
            phase("send", stage)

        def settle(self, stage, raw):
            phase("settle", stage)

        def uncertain(self, stage):
            assert stage == failed_stage
            calls.append("uncertain")

    def encode(value, _sequence):
        body.update(value)
        return b"packet"

    def receive(*_args, **_kwargs):
        phase("receipt", body["stage"])
        return b"reply"

    monkeypatch.setattr(
        transport_module.socket, "create_connection", lambda *_a, **_k: Connection()
    )
    monkeypatch.setattr(transport_module, "encode_tc", encode)
    monkeypatch.setattr(transport_module, "recv_packet", receive)
    monkeypatch.setattr(transport_module, "decode_packet", lambda _: SimpleNamespace(apid=102))
    monkeypatch.setattr(
        transport_module,
        "decode_tm",
        lambda _: {
            **body,
            "schema_version": "openbexi.dss.ack/1",
            "outcome": stages[body["stage"]],
        },
    )
    with pytest.raises(UncertainEffect) as denied:
        transport.command(
            "CMD1",
            [],
            dict(definition="procedure", procedure="execution"),
            "op",
            lambda: None,
            admission=Admission(),
            timeout=2,
        )
    assert denied.value.__cause__ is original
    completed = list(stages).index(failed_stage)
    assert [entry for entry in calls if isinstance(entry, tuple) and entry[0] == "send"] == [
        ("send", stage) for stage in list(stages)[: completed + 1]
    ]
    assert calls.count("uncertain") == 1
    assert calls[-2:] == ["close", "uncertain"]
    chain = failure_chain(denied.value)
    assert "private-upstream-detail" not in str(chain)
    trace = chain[0]["command_timing"]
    assert trace["elapsed_ms"] == 200
    assert trace["steps"][-1] == dict(
        phase=failed_phase, stage=failed_stage, elapsed_ms=200, failed=True
    )


def test_diagnostics_are_bounded_and_do_not_accept_arbitrary_exception_attributes(clock):
    error = RuntimeError("secret")
    error._dss_command_timing = {"secret": "untrusted"}
    assert failure_chain(error) == [{"type": "RuntimeError"}]
    timing = CommandTiming()
    with pytest.raises(ValueError):
        with timing.measure("private-endpoint"):
            pytest.fail("Invalid label must not execute")
    for _ in range(40):
        with timing.measure("send", "TRANSPORT"):
            clock.value += 1000
    snapshot = timing.snapshot()
    assert snapshot["elapsed_ms"] == 300000 and len(snapshot["steps"]) == 32
    assert all(step["elapsed_ms"] == 300000 for step in snapshot["steps"])
