"""Original TM RPC deadline, live authority and actual binary source samples."""
import types
import time
import sys
import base64
import threading

import grpc
import pytest

import test_command_rpc as base
from test_command_rpc import until, step
import limit_feature_patches
import telemetry_feature_patches
from openbexi_spell_dss.codec import pack, unpack
from openbexi_spell_dss.telemetry_budget import timeout, budget
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p, SPELLDriver_pb2_grpc as g


def composed(name):
    path = 'openbexi_spell_dss/'+name+'.py'
    raw = (base.ROOT/'driver_plugin/src'/path).read_bytes()
    for recipe in (*base.integrated_patches.DRIVER_RECIPES, limit_feature_patches, telemetry_feature_patches):
        if path in recipe.PREIMAGES:raw = recipe.apply(path, raw)
    module = types.ModuleType('openbexi_spell_dss._telemetry_test_'+name)
    exec(compile(raw, path, 'exec'), module.__dict__)
    return module


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(base, 'composed', composed)
    monkeypatch.setattr(base, 'Transport', composed('transport').Transport)
    monkeypatch.setitem(sys.modules, 'openbexi_spell_dss.command_budget', composed('command_budget'))
    yield from base.bridge.__wrapped__(tmp_path, monkeypatch)


def request(**settings):
    return p.TmItemValue(item=p.TmItemDesc(mnemonic='TM.POWER.BUS_VOLTAGE'), config=pack(settings))


def refresh(env, **settings):
    return p.TmItemValue.FromString(env.dispatch('/spell.driver.SPELLDriverInterface_TM/RefreshItem', request(**settings).SerializeToString()))


@pytest.mark.parametrize('value', [0, -1, 3600.001, True, float('inf'), float('nan'), 10**10000, '60'],
    ids=['zero', 'negative', 'over-cap', 'boolean', 'infinity', 'nan', 'huge-integer', 'string'])
def test_invalid_wait_bounds(value):
    with pytest.raises(ValueError):timeout(value)


@pytest.mark.parametrize('value,expected', [(.001,30), (30,30), (60,60), (3600,3600)])
def test_original_envelopes_agree_on_telemetry_duration(value, expected):
    message = request(Wait=True, Timeout=value)
    module = composed('command_budget')
    assert budget(message) == expected
    assert module.command_budget('TM','RefreshItem',message) == expected
    assert module.relay_budget('/spell.driver.SPELLDriverInterface_TM/RefreshItem',message.SerializeToString()) == expected


def test_no_update_times_out_then_real_update_recovers(env):
    with pytest.raises(TimeoutError):refresh(env, Wait=True, Timeout=.05)
    before = env.calls
    future = env.pool.submit(refresh, env, Wait=True, Timeout=60)
    until(lambda:env.calls > before+6)
    step(env, 1)
    row = future.result(timeout=5)
    assert row.validity and unpack(row.engValue) == 28
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0


def test_wait_checks_revoked_authority_and_recovers_without_mutation(env):
    future = env.pool.submit(refresh, env, Wait=True, Timeout=60)
    until(lambda:env.calls > 6)
    env.allowed = False
    with pytest.raises(PermissionError):future.result(timeout=3)
    env.allowed = True
    assert refresh(env, Wait=False).validity
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0


def test_original_rpc_and_relay_remain_live_beyond_old_limits(env):
    emitted, errors = [], []
    sent = threading.Event()
    work = []
    relay = None
    def emit(event, **row):
        emitted.append(dict(event=event, **row))
        future = env.pool.submit(env.dispatch, row['path'], base64.b64decode(row['payload'], validate=True))
        work.append(future)
        def reply(done):
            try:
                raw = done.result()
                relay.reply({'id':row['id'], 'payload':base64.b64encode(raw).decode('ascii')})
            except Exception as error:
                errors.append(repr(error))
        future.add_done_callback(reply)
        sent.set()
    relay = composed('relay').Relay(emit)
    channel = grpc.insecure_channel('127.0.0.1:'+str(relay.port))
    message = request(Wait=True, Timeout=60)
    started = time.monotonic()
    try:
        envelope = composed('command_budget').command_budget('TM', 'RefreshItem', message)
        future = g.SPELLDriverInterface_TMStub(channel).RefreshItem.future(message, timeout=envelope+4)
        assert sent.wait(3)
        until(lambda:env.calls > 6)
        # Actual gRPC -> private relay -> original dispatcher -> DSS acquisition,
        # held beyond both old 30-second transport and 35-second relay caps.
        time.sleep(max(0, 36-time.monotonic()+started))
        assert not future.done() and not work[0].done()
        step(env, 1)
        row = future.result(timeout=5)
        assert 36 <= time.monotonic()-started < 42
        assert row.validity and unpack(row.rawValue) == 28000
        assert len(emitted) == 1 and not errors
        assert emitted[0]['event'] == 'openbexi/driverRequest'
        assert p.TmItemValue.FromString(base64.b64decode(emitted[0]['payload'])) == message
    finally:
        env.allowed = False
        for future in work:
            try:future.result(timeout=3)
            except PermissionError:pass
        channel.close();relay.close()
