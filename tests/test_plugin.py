from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from dss.local import create_servers
from dss.packets import decode_tc
from openbexi_spell import BuildTC, Display, GetTM, Send, Verify, WaitFor
from openbexi_spell.api import DriverException, _context
from openbexi_spell_plugin.runtime import activate


@pytest.fixture
def fixture_dss(tmp_path):
    runtime, tcp, api = create_servers(tmp_path / 'dss.sqlite', 0)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (tcp, api)]
    for thread in threads:
        thread.start()
    try:
        yield runtime, f'http://127.0.0.1:{api.server_port}'
    finally:
        runtime.stop_event.set()
        for server in (api, tcp):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)
        runtime.engine.close()
        _context.set(None)


def test_real_sdk_dss_command_binary_stages_and_current_sample(fixture_dss, capsys):
    runtime, url = fixture_dss
    context = activate(url)
    assert runtime.health()['kafka_publisher'] is False
    assert runtime.engine.state()['payload']['enabled'] is False
    before = GetTM('TM1')
    assert Verify('TM1', before)
    assert not Verify('TM1', before+12345)
    assert Send(BuildTC('CMD1'))
    assert runtime.engine.state()['payload']['enabled'] is True
    assert runtime.engine.state()['core']['commands_executed'] == 1
    evidence = runtime.engine.evidence(runtime.engine.state()['scenario_id'])
    assert {decode_tc(bytes.fromhex(o['packet_hex']))['stage'] for o in evidence['operations']} >= {'TRANSPORT', 'LOADING', 'RELEASE', 'ACKNOWLEDGEMENT', 'ONBOARD_EXECUTION'}
    assert Display('plugin works') and WaitFor(0.01)
    assert 'plugin works' in capsys.readouterr().out


def test_unsupported_profiles_and_critical_command_have_no_effect(fixture_dss):
    runtime, url = fixture_dss
    activate(url)
    with pytest.raises(DriverException, match='current sample'):
        Verify('TM1', 1, Retries=1)
    with pytest.raises(DriverException, match='fresh telemetry'):
        GetTM('TM1', Wait=True)
    with pytest.raises(DriverException, match='Critical commands'):
        Send(BuildTC('TC.SIMULATOR.RESET'))
    assert runtime.engine.state()['core']['commands_executed'] == 0


def test_lost_send_response_is_unknown_and_never_automatically_replayed(fixture_dss, monkeypatch):
    runtime, url = fixture_dss
    context = activate(url)
    command = BuildTC('CMD1')
    original = context.runtime.request
    sends = []
    def lost(route, body=None):
        value = original(route, body)
        if route.endswith('/commands'):
            sends.append(body)
            raise DriverException('response lost', 'LOST', operation='Send', effect_certainty='UNKNOWN')
        return value
    monkeypatch.setattr(context.runtime, 'request', lost)
    with pytest.raises(DriverException) as failure:
        Send(command)
    assert failure.value.effect_certainty == 'UNKNOWN'
    assert len(sends) == 1 and runtime.engine.state()['core']['commands_executed'] == 1


def test_packaged_catalogue_bytes_and_preserved_original_archive():
    from dss.catalog import DATABASE_DIGEST, DATABASE_PATH
    import hashlib
    assert hashlib.sha256(DATABASE_PATH.read_bytes()).hexdigest() == DATABASE_DIGEST
    archive = Path(__file__).resolve().parents[1] / 'docs/reference/SPELL2.6.10-src.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'


def test_rejection_after_confirmed_release_cannot_resend(fixture_dss, monkeypatch):
    from openbexi_spell.common import RESEND
    runtime, url = fixture_dss
    context = activate(url)
    command = BuildTC('CMD1')
    original = context.runtime.request
    sends = []
    def reject_after_release(route, body=None):
        value = original(route, body)
        if route.endswith('/commands'):
            sends.append(body)
            return {**value, 'outcome': 'REJECTED'}
        return value
    monkeypatch.setattr(context.runtime, 'request', reject_after_release)
    with pytest.raises(DriverException) as failure:
        Send(command, HandleError=True, OnFailure=RESEND, PromptFailure=False)
    assert failure.value.effect_certainty == 'CONFIRMED'
    assert len(sends) == 1 and runtime.engine.state()['core']['commands_executed'] == 1
