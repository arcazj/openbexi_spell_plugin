"""Capacity, crash and upgrade checks against the durable driver boundary."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import uuid

import grpc
import pytest

from openbexi_spell_dss.operational_journal import CapacityExceeded, Journal, UncertainEffect
from openbexi_spell_dss.server import Server
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p, SPELLDriver_pb2_grpc as g
from openbexi_spell_dss.codec import pack
from test_original_driver import bridge


def identity():
    return dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex, definition='quota-test',
                version='a' * 64, controller_epoch=1, procedure_fence=1,
                mode='Development', release=None)


def test_full_effect_budget_returns_receipts_and_rejects_new_intents_after_restart(tmp_path):
    path, who = tmp_path / 'journal.sqlite', identity()
    journal = Journal(path, max_effects=2, max_effects_per_run=2)
    requests = [uuid.uuid4().hex for _ in range(3)]
    for request in requests[:2]:
        assert journal.begin(who, request, 'write', b'command') is None
        journal.finish(who, request, b'confirmed')
    journal.close()
    journal = Journal(path, max_effects=2, max_effects_per_run=2)
    try:
        assert journal.begin(who, requests[0], 'write', b'command') == b'confirmed'
        with pytest.raises(CapacityExceeded):
            journal.begin(who, requests[2], 'write', b'command')
        assert journal.usage()['effects']['entries'] == 2
        assert journal.db.execute('SELECT COUNT(*) FROM effects').fetchone() == (2,)
    finally:
        journal.close()


def test_receipt_space_is_reserved_before_admission_and_released_atomically(tmp_path):
    journal = Journal(tmp_path / 'journal.sqlite', max_bytes=131072)
    who, other, first, second = identity(), identity(), uuid.uuid4().hex, uuid.uuid4().hex
    try:
        journal.begin(who, first, 'write', b'x')
        before = journal.usage()
        with pytest.raises(CapacityExceeded):
            journal.begin(other, second, 'write', b'y')
        assert journal.usage() == before
        journal.finish(who, first, b'ok')
        assert journal.usage()['effects']['reserved_bytes'] < before['effects']['reserved_bytes']
        journal.begin(other, second, 'write', b'y')
        journal.finish(other, second, b'r' * 65536)
        assert journal.begin(other, second, 'write', b'y') == b'r' * 65536
    finally:
        journal.close()


def test_event_capacity_is_persistent_and_grpc_reports_resource_exhausted(tmp_path):
    path, who = tmp_path / 'journal.sqlite', identity()
    journal = Journal(path, max_events=1)
    journal.event(who, uuid.uuid4().hex, 'retained operational event', 1, 1)
    journal.close()
    journal = Journal(path, max_events=1)
    server = Server(lambda method, raw: journal.event(who, uuid.uuid4().hex, 'denied', 1, 1))
    channel = grpc.insecure_channel('127.0.0.1:' + str(server.port))
    try:
        with pytest.raises(grpc.RpcError) as error:
            g.SPELLDriverInterface_TMStub(channel).RefreshItem(p.TmItemValue(), timeout=5)
        assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        assert journal.db.execute('SELECT message FROM events').fetchall() == [('retained operational event',)]
        assert journal.usage()['events']['entries'] == 1
    finally:
        channel.close()
        server.close()
        journal.close()


def test_full_journal_rejects_second_actual_tc_before_any_binary_write(bridge):
    runtime, transport, journal, dispatcher, who, calls, channel = bridge
    journal.db.execute("UPDATE journal_limits SET maximum=1 WHERE kind='effects'")
    stub = g.SPELLDriverInterface_TCStub(channel)
    command = p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1'), args=pack([]), config=pack({}))
    assert stub.SendCommand(command, timeout=5).value
    before = runtime.engine.state()['core']['commands_executed']
    with pytest.raises(grpc.RpcError) as error:
        stub.SendCommand(command, timeout=5)
    assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    assert runtime.engine.state()['core']['commands_executed'] == before == 1
    assert journal.db.execute('SELECT state FROM effects').fetchall() == [('RECEIPTED',)]


def test_private_rpc_concurrency_is_bounded_and_recovers_after_overload():
    barrier = threading.Barrier(5)
    release = threading.Event()
    def dispatch(method, raw):
        barrier.wait(timeout=10)
        release.wait(timeout=10)
        return b''
    server = Server(dispatch)
    channel = grpc.insecure_channel('127.0.0.1:' + str(server.port))
    try:
        call = g.SPELLDriverInterface_TMStub(channel).RefreshItem
        active = [call.future(p.TmItemValue(), timeout=15) for _ in range(4)]
        barrier.wait(timeout=10)
        with pytest.raises(grpc.RpcError) as error:
            call(p.TmItemValue(), timeout=3)
        assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        release.set()
        for future in active:
            future.result(timeout=5)
    finally:
        release.set()
        channel.close()
        server.close()
    # The same process can provision a new bounded service after saturation.
    server = Server(lambda method, raw: b'')
    channel = grpc.insecure_channel('127.0.0.1:' + str(server.port))
    try:
        g.SPELLDriverInterface_TMStub(channel).RefreshItem(p.TmItemValue(), timeout=3)
    finally:
        channel.close()
        server.close()


@pytest.mark.parametrize('after_effect', [False, True])
def test_killed_process_never_replays_pending_intent_or_external_write(tmp_path, after_effect):
    path, who, request = tmp_path / 'journal.sqlite', identity(), uuid.uuid4().hex
    effect = tmp_path / 'external-effect.txt'
    code = '''import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from openbexi_spell_dss.operational_journal import Journal
j=Journal(sys.argv[2]); who=json.loads(sys.argv[3])
j.begin(who, sys.argv[4], 'write', b'command')
if sys.argv[6]=='True':
 with open(sys.argv[5], 'xb') as f:
  f.write(b'one externally committed effect'); f.flush(); os.fsync(f.fileno())
os._exit(73)
'''
    source = Path(__file__).resolve().parents[1] / 'driver_plugin/src'
    result = subprocess.run([sys.executable, '-I', '-c', code, str(source), str(path), json.dumps(who),
                             request, str(effect), str(after_effect)], capture_output=True, timeout=20)
    assert result.returncode == 73, result.stderr
    journal = Journal(path)
    try:
        for retry in (request, uuid.uuid4().hex):
            with pytest.raises(UncertainEffect):
                journal.begin(who, retry, 'write', b'command')
        assert effect.exists() == after_effect
        if after_effect:
            assert effect.read_bytes() == b'one externally committed effect'
        assert journal.db.execute('SELECT state FROM effects').fetchall() == [('PENDING',)]
        assert journal.usage()['effects']['entries'] == 1
    finally:
        journal.close()


def test_existing_v06_pending_and_receipted_rows_are_counted_without_modification(tmp_path):
    path, who = tmp_path / 'journal.sqlite', identity()
    journal = Journal(path)
    first = uuid.uuid4().hex
    journal.begin(who, first, 'write', b'old')
    journal.finish(who, first, b'v06-receipt')
    pending = uuid.uuid4().hex
    journal.begin(who, pending, 'write', b'unconfirmed')
    old = journal.db.execute('SELECT * FROM effects ORDER BY created_ns').fetchall()
    journal.db.execute('DROP TABLE journal_budget')  # Exact pre-v07 schema.
    journal.close()
    journal = Journal(path)
    try:
        assert journal.db.execute('SELECT * FROM effects ORDER BY created_ns').fetchall() == old
        assert journal.usage()['effects']['entries'] == 2
        assert journal.begin(who, first, 'write', b'old') == b'v06-receipt'
        with pytest.raises(UncertainEffect):
            journal.begin(who, pending, 'write', b'unconfirmed')
    finally:
        journal.close()
