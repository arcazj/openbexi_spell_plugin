"""Actual original-schema dispatcher, DSS catalog and SQLite limit transactions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import types
import uuid

import pytest
from google.protobuf.wrappers_pb2 import BoolValue

import test_command_rpc as base
import limit_feature_patches
from openbexi_spell_dss.codec import pack, unpack
from openbexi_spell_dss.limits import PROFILE, CONTROL
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p

HARD = dict(LoRed=10, LoYel=20, HiYel=30, HiRed=40)


@pytest.fixture
def env(tmp_path, monkeypatch):
    def composed(name):
        path = 'openbexi_spell_dss/'+name+'.py'
        raw = (base.ROOT/'driver_plugin/src'/path).read_bytes()
        for recipe in (*base.integrated_patches.DRIVER_RECIPES, limit_feature_patches):
            if path in recipe.PREIMAGES:raw = recipe.apply(path, raw)
        module = types.ModuleType('openbexi_spell_dss._limit_rpc_test_'+name)
        exec(compile(raw, path, 'exec'), module.__dict__)
        return module
    monkeypatch.setattr(base, 'composed', composed)
    yield from base.bridge.__wrapped__(tmp_path, monkeypatch)


def call(env, method, request):
    raw = env.dispatch('/spell.driver.SPELLDriverInterface_TM/'+method, request.SerializeToString())
    return p.LimitSet.FromString(raw) if method == 'GetLimits' else BoolValue.FromString(raw).value


def set_limits(env, name='TMparam', **settings):
    return operation(env, 'Modify', settings, name)


def operation(env, operation, settings, name='TMparam'):
    return call(env, 'SetLimits', p.LimitSetRequest(item=p.TmItemDesc(mnemonic=name),
        set=p.LimitSet(limitset=pack({CONTROL: PROFILE, 'Operation': operation, 'Settings': settings}))))


def get(env, name='TMparam', **settings):
    return unpack(call(env, 'GetLimits', p.TmItemValue(item=p.TmItemDesc(mnemonic=name),
        config=pack({CONTROL: PROFILE, **settings}))).limitset)


def alarm(env, name='TMparam'):
    return call(env, 'IsAlarmed', p.TmItemValue(item=p.TmItemDesc(mnemonic=name)))


def inject(env, value, name='TMparam', serial=0, valid=True):
    row = env.transport.database.item(name)
    raw = round(value/row['engineering_scale']) if row['raw_type'] in ('INT64', 'UINT64') else value
    engineering = raw*row['engineering_scale'] if type(raw) is int else raw
    return call(env, 'InjectItem', p.TmItemValue(item=p.TmItemDesc(mnemonic=name),
        rawValue=pack(raw), engValue=pack(engineering), validity=valid,
        timestamp=(datetime.now(timezone.utc)+timedelta(microseconds=serial)).strftime('%Y-%m-%d %H:%M:%S.%f')))


def snapshot(env):
    return deepcopy(env.dispatcher.ground.state()), env.journal.db.execute('SELECT * FROM effects ORDER BY request_id').fetchall()


def test_named_definitions_active_selection_and_atomic_partial_updates(env):
    assert set_limits(env, Limits={'NORMAL': dict(HARD, Name='Normal', Hysteresis=2),
                                  'BACKUP': dict(HARD, Active=False)})
    assert set(get(env, Select='ALL')) == {'NORMAL', 'BACKUP'}
    assert set(get(env, Select='ACTIVE')) == {'NORMAL'}
    assert set_limits(env, Definition={'LoYel': 19}, Select='NORMAL')
    assert get(env, Select='NORMAL', Value='LoYel') == 19
    assert get(env, Select='BACKUP', Value='LoYel') == 20
    before = snapshot(env)
    with pytest.raises(ValueError):set_limits(env, Limits={'NORMAL': {'LoYel': 18}, 'BACKUP': {'LoRed': 50}})
    assert snapshot(env) == before
    assert set_limits(env, Definition={'Active': True}, Select='BACKUP')
    assert len(get(env, Select='ACTIVE')) == 2


def test_legacy_wire_and_restoration_remain_compatible(env):
    assert call(env, 'SetLimits', p.LimitSetRequest(item=p.TmItemDesc(mnemonic='TMparam'),
        set=p.LimitSet(limitset=pack(HARD))))
    assert env.dispatcher.ground.state()['limits']['TMparam'] == HARD
    assert get(env, Select='GENERIC') == dict(HARD, Type='HARDSOFT', Active=True)
    assert inject(env, 50)
    assert alarm(env)
    injection = env.dispatcher.ground.state()['injections']
    assert call(env, 'RestoreNormalLimits', pack({}))
    assert not alarm(env)
    assert env.dispatcher.ground.state()['injections'] == injection
    with pytest.raises(ValueError):get(env)


def test_hysteresis_counts_distinct_samples_and_recovers(env):
    assert set_limits(env, Definition=dict(HARD, Hysteresis=2))
    assert inject(env, 50)
    assert not alarm(env)
    assert not alarm(env)  # Re-reading one observation cannot create a violation.
    assert inject(env, 50, serial=1)
    assert alarm(env)
    assert inject(env, 25)
    assert not alarm(env)
    assert inject(env, 50)
    assert not alarm(env)
    assert inject(env, 50)
    assert alarm(env)


def test_alarm_enable_disable_and_restart_preserve_real_storage(env):
    assert set_limits(env, Definition=HARD)
    assert inject(env, 50)
    assert alarm(env)
    assert operation(env, 'Alarm', {'Enabled': False})
    assert not alarm(env)
    env.dispatcher.ground = type(env.dispatcher.ground)(env.transport, env.journal)
    assert not alarm(env)
    assert get(env, Select='GENERIC', Value='LoRed') == 10
    assert operation(env, 'Alarm', {'Enabled': True})
    assert alarm(env)


def test_dynamic_algorithm_uses_catalog_values_and_rejects_invalid_source(env):
    assert inject(env, 1, 'TMparam1')
    assert inject(env, 2, 'TMparam2')
    assert inject(env, 2, 'TMparam3')
    assert set_limits(env, Definition=dict(HARD, Algorithm='TMparam1<TMparam2+TMparam3'))
    assert len(get(env, Select='ACTIVE')) == 1
    assert inject(env, 5, 'TMparam1')
    assert get(env, Select='ACTIVE') == {}
    before = snapshot(env)
    with pytest.raises(ValueError):set_limits(env, Definition={'Algorithm': 'UNKNOWN>0'}, Select='GENERIC')
    assert snapshot(env) == before
    assert inject(env, 1, 'TMparam1', valid=False)
    with pytest.raises(ValueError):get(env, Select='ACTIVE')


@pytest.mark.parametrize('definition,values,expected', [
    ({'Delta': [2, 3]}, [10, 13, 17, 15, 12], [False, False, True, False, True]),
    ({'Delta': 3}, [10, 13, 17, 14, 10], [False, False, True, False, True]),
])
def test_step_and_spike_use_successive_distinct_observations(env, definition, values, expected):
    assert set_limits(env, Definition=definition)
    for value, wanted in zip(values, expected):
        assert inject(env, value)
        assert alarm(env) is wanted
        assert alarm(env) is wanted


def test_status_classes_preserve_exact_strings_and_ignore_recovers(env):
    name = 'TM.CORE.MODE'
    exotic = "A,'B' "+chr(0x3b1)
    assert set_limits(env, name, Definition={'Nominal': [exotic], 'Warning': ['SAFE'], 'Error': ['FAILED'], 'Ignore': ['OFF']})
    assert get(env, name, Select='GENERIC', Value='Nominal') == [exotic]
    for value, wanted in ((exotic, False), ('SAFE', True), ('FAILED', True), ('OFF', False), ('UNKNOWN', True), (exotic, False)):
        assert inject(env, value, name)
        assert alarm(env, name) is wanted


def test_limit_file_has_actual_persisted_hash_and_atomic_definitions(env):
    assert operation(env, 'Load', {'File': 'limits://normal'}, '')
    assert get(env, Select='GENERIC', Value='LoRed') == 0
    assert get(env, 'TM.CORE.MODE', Select='GENERIC', Value='Nominal') == ['NOMINAL']
    raw = (base.ROOT/'driver_plugin/src/openbexi_spell_dss/limit_files/normal.json').read_bytes()
    assert env.dispatcher.ground.state()['limit_files'] == {'limits://normal': hashlib.sha256(raw).hexdigest()}
    before = snapshot(env)
    for uri in ('limits://absent', 'limits://../normal', 'file://normal'):
        with pytest.raises(ValueError):operation(env, 'Load', {'File': uri}, '')
        assert snapshot(env) == before


def test_receipted_duplicate_never_reapplies_after_another_update(env):
    env.request_id = uuid.uuid4().hex
    token = env.request_id
    assert set_limits(env, Definition=HARD)
    env.request_id = None
    assert set_limits(env, Definition={'LoRed': 9})
    env.request_id = token
    assert set_limits(env, Definition=HARD)
    assert get(env, Select='GENERIC', Value='LoRed') == 9


def test_monitoring_and_revocation_have_no_effect(env):
    before = snapshot(env)
    env.identity['mode'] = 'Monitoring'
    with pytest.raises(PermissionError):set_limits(env, Definition=HARD)
    assert snapshot(env) == before
    env.identity['mode'] = 'Development'
    env.allowed = False
    with pytest.raises(PermissionError):set_limits(env, Definition=HARD)
    assert snapshot(env) == before


@pytest.mark.parametrize('settings', [
    {'Definition': dict(HARD, Hysteresis=-1)}, {'Definition': dict(HARD, Active='yes')},
    {'Definition': dict(HARD, Algorithm='open("x")')}, {'Definition': dict(HARD, HiRed=float('inf'))},
    {'Definition': {'Delta': [-1, 2]}}, {'Definition': {'Nominal': ['ON']}},
    {'Definition': HARD, 'Select': []}, {'Definition': HARD, 'Unknown': True},
])
def test_invalid_update_has_no_intent_and_successful_recovery(env, settings):
    before = snapshot(env)
    with pytest.raises((ValueError, TypeError)):set_limits(env, **settings)
    assert snapshot(env) == before
    assert set_limits(env, Definition=HARD)
    assert get(env, Select='GENERIC', Value='Midpoint') == 25
