"""Atomic ranging and catalog semantics through the original protobuf dispatcher."""
import ast
import json
from pathlib import Path
import types
import uuid

import pytest
from google.protobuf.message_factory import GetMessageClass
import test_command_rpc as base
import ranging_complete_patches
from openbexi_spell_dss.codec import pack,unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from openbexi_spell_dss.ranging_complete import PATHS


def composed(name):
    path='openbexi_spell_dss/'+name+'.py'
    raw=(base.ROOT/'driver_plugin/src'/path).read_bytes()
    for recipe in dict.fromkeys((*base.integrated_patches.DRIVER_RECIPES,ranging_complete_patches)):
        if path in recipe.PREIMAGES:raw=recipe.apply(path,raw)
    module=types.ModuleType('openbexi_spell_dss._ranging_complete_test_'+name)
    exec(compile(raw,path,'exec'),module.__dict__)
    return module


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(base,'composed',composed)
    yield from base.bridge.__wrapped__(tmp_path,monkeypatch)


def rpc(env,method,request):
    descriptor=p.DESCRIPTOR.services_by_name['SPELLDriverInterface_RNG'].methods_by_name[method]
    raw=env.dispatch('/spell.driver.SPELLDriverInterface_RNG/'+method,request.SerializeToString())
    return GetMessageClass(descriptor.output_type).FromString(raw)


def capture(env):
    return (env.dispatcher.ground.state(),env.journal.db.execute('SELECT * FROM effects ORDER BY request_id').fetchall(),
            env.engine.state())


def dual(env,selected=None,method='StartRanging'):
    return rpc(env,method,p.Ranging(config=pack({'Paths':selected if selected is not None else [list(v) for v in PATHS]}))).value


def test_dual_activity_is_one_receipted_effect_and_schedule_is_independent(env):
    before=env.engine.state()
    assert dual(env)
    assert env.dispatcher.ground.state()['ranging_paths']==[list(v) for v in PATHS]
    assert env.journal.db.execute('SELECT state FROM effects').fetchall()==[('RECEIPTED',)]
    assert rpc(env,'DisableRanging',p.Ranging()).value
    assert rpc(env,'EnableRanging',p.Ranging()).value
    state=env.dispatcher.ground.state()
    assert state['ranging']=='RANGING' and state['ranging_schedule_enabled']
    assert state['ranging_paths']==[list(v) for v in PATHS]
    assert rpc(env,'AbortRanging',p.Ranging()).value
    state=env.dispatcher.ground.state()
    assert state['ranging']=='READY' and state['ranging_paths']==[] and state['ranging_schedule_enabled']
    assert env.engine.state()==before


def test_duplicate_dual_request_returns_receipt_without_restarting_or_changing_activity(env):
    env.request_id=uuid.uuid4().hex
    assert dual(env)
    before=capture(env)
    assert dual(env)
    assert capture(env)==before
    env.request_id=None
    assert rpc(env,'AbortRanging',p.Ranging()).value
    assert env.dispatcher.ground.state()['ranging_paths']==[]


@pytest.mark.parametrize('selected',[
    [],[['DSS-BBE-1','DSS-ANTENNA-1'],['DSS-BBE-2','MISSING']],
    [['DSS-BBE-1','DSS-ANTENNA-1']]*2,[['DSS-BBE-1']],
    [['DSS-BBE-1','DSS-ANTENNA-2']],
])
def test_invalid_dual_paths_leave_no_partial_activity_or_intent(env,selected):
    before=capture(env)
    with pytest.raises(ValueError):dual(env,selected)
    assert capture(env)==before
    assert dual(env)


def batch(env,pairs):
    return rpc(env,'SetBasebandConfig',p.BaseBandConfig(bbe='DSS-BBE-2',config=pack({'Parameters':pairs}))).value


@pytest.mark.parametrize('pairs',[
    [],[['frequency_hz','2000000'],['MISSING','1']],
    [['frequency_hz','2000000'],['integration_ms','bad']],
    [['frequency_hz','2000000'],['frequency_hz','3000000']],
    [['frequency_hz','0']], [['integration_ms','1000000001']],
])
def test_entire_batch_is_validated_before_journal_intent(env,pairs):
    before=capture(env)
    with pytest.raises(ValueError):batch(env,pairs)
    assert capture(env)==before
    assert batch(env,[['frequency_hz','1'],['integration_ms','1000000000']])
    assert env.dispatcher.ground.state()['baseband']['DSS-BBE-2']=={'frequency_hz':'1','integration_ms':'1000000000'}


def test_revoked_authority_prevents_dual_and_batch_mutation(env):
    before=capture(env);env.allowed=False
    with pytest.raises(PermissionError):dual(env)
    with pytest.raises(PermissionError):batch(env,[['frequency_hz','3000000']])
    assert capture(env)==before
    env.allowed=True;assert dual(env,method='StartCalibration')
    assert env.dispatcher.ground.state()['ranging']=='CALIBRATING'


def test_catalog_and_identity_calibration_are_explicit_and_read_only(env):
    before=capture(env)
    assert list(rpc(env,'GetRangingPaths',pack({})).names)==['/'.join(v) for v in PATHS]
    assert list(rpc(env,'GetBasebandNames',pack({})).names)==[v[0] for v in PATHS]
    for format in ('Raw format','Eng format','Default format'):
        assert rpc(env,'GetBasebandConfig',p.BaseBandConfig(bbe='DSS-BBE-2',param='frequency_hz',
            config=pack({'ValueFormat':format}))).value=='1000000'
    with pytest.raises(ValueError):
        rpc(env,'GetBasebandConfig',p.BaseBandConfig(bbe='DSS-BBE-1',param='frequency_hz',config=pack({'ValueFormat':'bad'})))
    assert capture(env)==before


def test_status_validation_and_legacy_activity_migration(env):
    ground=env.dispatcher.ground
    for status in ('READY','RANGING','CALIBRATING','ERROR'):
        ground.update(lambda state:state.__setitem__('ranging',status))
        assert rpc(env,'GetRangingStatus',pack({})).value==status
    ground.update(lambda state:state.__setitem__('ranging','MALFORMED'))
    with pytest.raises(ValueError):rpc(env,'GetRangingStatus',pack({}))
    assert dual(env)
    def legacy(state):
        state.pop('ranging_paths');state['baseband'].pop('DSS-BBE-2')
    ground.update(legacy)
    restored=composed('ground').Ground(env.transport,env.journal)
    assert restored.state()['ranging']=='RANGING'
    assert restored.state()['ranging_paths']==[list(PATHS[0])]
    assert restored.state()['ranging_schedule_enabled'] is False


def test_reopening_current_database_preserves_exact_persisted_bytes(env):
    assert dual(env)
    ground=env.dispatcher.ground
    state=ground.state();encoded=json.dumps(state,indent=3,sort_keys=False)+'\n'
    env.journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(encoded,ground.namespace))
    effects=env.journal.db.execute('SELECT * FROM effects').fetchall()
    for _ in range(2):
        reopened=composed('ground').Ground(env.transport,env.journal)
        assert reopened.state()==state
        assert env.journal.db.execute('SELECT state FROM ground WHERE namespace=?',(ground.namespace,)).fetchone()[0]==encoded
        assert env.journal.db.execute('SELECT * FROM effects').fetchall()==effects


def proxy(env,monkeypatch):
    path=base.ROOT/'driver_plugin/src/openbexi_dss_proxy/ranging_complete.py'
    tree=ast.parse(path.read_bytes())
    tree.body=[node for node in tree.body if not isinstance(node,ast.ImportFrom)]
    module=types.ModuleType('_ranging_proxy')
    module.__dict__.update(DriverException=RuntimeError,p=p,PackValue=pack,UnpackValue=unpack,
                          IDLE=0,RANGING=1,CALIBRATING=3,ERROR=2,
                          call=lambda family,method,request:rpc(env,method,request))
    # The two local imports invoke the existing policy filter. Bind its package
    # explicitly while exercising the actual new proxy function bodies.
    module.__package__='openbexi_dss_proxy'
    original=types.ModuleType('openbexi_dss_proxy.ranging')
    original.ranging_settings=lambda config:pack(config or {})
    monkeypatch.setitem(__import__('sys').modules,'openbexi_dss_proxy.ranging',original)
    exec(compile(tree,str(path),'exec'),module.__dict__)
    return module


def test_original_helper_list_forms_encode_one_atomic_original_rpc(env,monkeypatch):
    module=proxy(env,monkeypatch)
    assert module.operation('StartRanging',[v[0] for v in PATHS],[v[1] for v in PATHS],{})
    assert module.configure('DSS-BBE-1',['frequency_hz','integration_ms'],[2000000,250],{})
    assert env.journal.db.execute('SELECT state FROM effects').fetchall()==[('RECEIPTED',),('RECEIPTED',)]
    assert [module.status(value) for value in ('READY','RANGING','CALIBRATING','ERROR')]==[0,1,3,2]
    with pytest.raises(RuntimeError):module.status('MALFORMED')
