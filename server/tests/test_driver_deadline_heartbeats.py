"""Original concurrent driver oracles with real, concurrently renewed leases."""

from functools import partial
import json
import os
from pathlib import Path
import threading
import time
import uuid

import pytest

from openbexi_spell_server.contracts import envelope
from openbexi_spell_server.liveness import ControllerLiveness
from openbexi_spell_server.services import Context
from openbexi_spell_server.transport import Route
import test_native_driver as driver
import test_preflight as helpers

independent_dss = driver.independent_dss


@pytest.fixture
def leased_driver(tmp_path, pki, source, independent_dss, monkeypatch):
    sessions = {}
    original = ControllerLiveness.open

    def remember(self, connection):
        result = original(self, connection)
        sessions[connection] = dict(result)
        return result

    monkeypatch.setattr(helpers, "Context", partial(Context, controller_liveness_seconds=5))
    monkeypatch.setattr(ControllerLiveness, "open", remember)
    for setup in driver.driver_setup.__wrapped__(tmp_path, pki, source, independent_dss):
        setup["lease"] = sessions[setup["connection"]]
        yield setup


@pytest.mark.parametrize("check", ["burst2", "burst3", "barrier"])
def test_original_concurrent_deadlines_with_live_heartbeats(leased_driver, pki, monkeypatch, check):
    setup = leased_driver
    route = Route(
        setup["config"]["context_url"], pki["context-a"]["pin"], pki["listener"]["client"]
    )
    stop = threading.Event()
    beats, failures = [], []

    def renew():
        nonce = setup["lease"]["heartbeat_nonce"]
        while not stop.is_set():
            started = time.monotonic()
            try:
                result = route.call(
                    envelope(
                        "A",
                        "alice",
                        "session.heartbeat",
                        dict(connection_id=setup["connection"], heartbeat_nonce=nonce),
                        str(uuid.uuid4()),
                    )
                )
                nonce = result["heartbeat_nonce"]
                beats.append(dict(started=started, elapsed=time.monotonic() - started))
            except BaseException as error:
                failures.append(type(error).__name__)
                break
            stop.wait(0.1)

    thread = threading.Thread(target=renew)
    begin = time.monotonic()
    thread.start()
    try:
        if check == "barrier":
            driver.test_ten_pending_receipts_bound_eleventh_rpc_without_effect(
                setup, pki, monkeypatch, False
            )
        else:
            driver.test_three_ten_request_bursts_keep_original_receipts_and_no_busy_loss(
                setup, pki, int(check[-1])
            )
    finally:
        stop.set()
        thread.join(6)
        if output := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
            Path(output, "heartbeat-" + check + ".json").write_text(
                json.dumps(
                    dict(
                        check=check,
                        beats=beats,
                        failures=failures,
                        started=begin,
                        ended=time.monotonic(),
                        thread_alive=thread.is_alive(),
                        original_driver_oracle_unchanged=True,
                        heartbeat_socket_timeout_seconds=2,
                    ),
                    indent=2,
                )
            )
    assert not thread.is_alive()
    assert not failures
    assert len(beats) >= 2
    assert max(beat["elapsed"] for beat in beats) < 2
