"""Original Group/Block RPC, durable member results, authority and partial effects."""
from copy import deepcopy
import types
import uuid

import grpc
import pytest
from google.protobuf.message_factory import GetMessageClass

import test_command_rpc as base
from test_command_rpc import p,g,pack,packets,until,step,target,composed as scheduling_module
import command_catalog_patches
import command_group_patches
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.command_results import KEY,SOURCE,Results


@pytest.fixture
def bridge(tmp_path,monkeypatch):
    def composed(name):
        if name!='rpc':return scheduling_module(name)
        path='openbexi_spell_dss/rpc.py';raw=(base.ROOT/'driver_plugin/src'/path).read_bytes()
        for recipe in base.integrated_patches.DRIVER_RECIPES:
            if path in recipe.PREIMAGES:raw=recipe.apply(path,raw)
        module=types.ModuleType('openbexi_spell_dss._command_group_rpc_test')
        exec(compile(raw,path,'exec'),module.__dict__);return module
    monkeypatch.setattr(base,'composed',composed)
    yield from base.bridge.__wrapped__(tmp_path,monkeypatch)


def request(blocked=False,rows=None,token=None):
    method='SendBlock' if blocked else 'SendList'
    rows=rows or [('CMD1',{}),('CMD3',{})]
    shape=p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TC'].methods_by_name[method].input_type
    commands=[p.CommandDesc(command=p.TcItemDesc(mnemonic=name),args=pack([]),config=pack(options)) for name,options in rows]
    token=token or uuid.uuid4().hex
    return method,GetMessageClass(shape)(commands=commands,config=pack({KEY:token,'Block' if blocked else 'Group':True})),token


def result(env,token):
    raw=p.LookupRequest(name=token,type='TC',source=SOURCE).SerializeToString()
    return unpack(p.LookupAnswer.FromString(env.dispatch('/spell.driver.SPELLDriverInterface_TM/DatabaseLookup',raw)).lookup)


@pytest.mark.parametrize('blocked',[False,True])
def test_original_rpc_reports_each_actual_member_once_and_replays_only_receipt(bridge,blocked):
    method,body,token=request(blocked)
    bridge.request_id=uuid.uuid4().hex
    assert getattr(bridge.stub,method)(body,timeout=8).value
    assert getattr(bridge.stub,method)(body,timeout=8).value
    observed=result(bridge,token)
    assert observed['outcome']=='SUCCEEDED'
    assert [row['name'] for row in observed['members']]==['CMD1','CMD3']
    assert [row['state'] for row in observed['members']]==['SUCCEEDED','SUCCEEDED']
    assert all(row['attempted'] and not row['uncertain'] for row in observed['members'])
    assert len([row for row in packets(bridge) if row['stage']=='TRANSPORT'])==(1 if blocked else 2)
    assert bridge.engine.state()['core']['commands_executed']==2
    assert bridge.journal.db.execute('SELECT state FROM effects').fetchall()==[('RECEIPTED',)]


@pytest.mark.parametrize('blocked',[False,True])
def test_rpc_load_only_group_never_releases_or_executes(bridge,blocked):
    method,body,token=request(blocked,[('CMD1',{'LoadOnly':True}),('CMD1',{'LoadOnly':True})])
    assert getattr(bridge.stub,method)(body,timeout=8).value
    assert [row['state'] for row in result(bridge,token)['members']]==['LOADED','LOADED']
    assert {row['stage'] for row in packets(bridge)}=={'TRANSPORT','LOADING'}
    assert step(bridge,10)['core']['commands_executed']==0


@pytest.mark.parametrize('blocked',[False,True])
def test_future_tagged_rpc_members_are_all_released_before_execution(bridge,blocked):
    due=target(bridge,3.5)
    method,body,token=request(blocked,[('CMD1',{'Time':due}),('CMD3',{'Time':due})])
    future=getattr(bridge.stub,method).future(body,timeout=10)
    until(lambda:len(packets(bridge))==(7 if blocked else 8))
    assert bridge.engine.state()['core']['commands_executed']==0
    step(bridge,4)
    assert future.result(timeout=5).value
    assert [row['state'] for row in result(bridge,token)['members']]==['SUCCEEDED','SUCCEEDED']


def fault(env,**faults):
    old=env.engine.state();new=env.engine.reset('group-rpc-failure',faults=faults,expected_epoch=old['epoch'])
    env.transport.epoch,env.transport.scenario=new['epoch'],new['scenario_id']
    env.dispatcher.ground=type(env.dispatcher.ground)(env.transport,env.journal)


@pytest.mark.parametrize('blocked',[False,True])
def test_failed_group_preserves_loaded_or_unsent_status_of_later_member(bridge,blocked):
    fault(bridge,execution_fail=True)
    method,body,token=request(blocked)
    assert getattr(bridge.stub,method)(body,timeout=8).value is False
    observed=result(bridge,token)
    assert observed['outcome']=='FAILED'
    assert [row['state'] for row in observed['members']]==['FAILED','LOADED' if blocked else 'NOT_SENT']
    assert observed['members'][1]['attempted']==blocked
    assert bridge.engine.state()['core']['commands_executed']==0


@pytest.mark.parametrize('blocked',[False,True])
def test_lost_ack_is_not_success_and_does_not_hide_possible_effect(bridge,blocked):
    fault(bridge,lost_ack=True)
    method,body,token=request(blocked)
    with pytest.raises(grpc.RpcError) as error:getattr(bridge.stub,method)(body,timeout=8)
    assert error.value.code()==grpc.StatusCode.FAILED_PRECONDITION
    observed=result(bridge,token)
    assert observed['outcome']=='UNCERTAIN' and observed['members'][0]['uncertain'] is True
    assert observed['members'][1]['attempted']==blocked
    assert bridge.engine.state()['core']['commands_executed']==1
    assert bridge.journal.db.execute('SELECT state FROM effects').fetchall()==[('PENDING',)]
    with pytest.raises(grpc.RpcError):getattr(bridge.stub,method)(body,timeout=5)
    assert bridge.engine.state()['core']['commands_executed']==1


def test_group_result_cannot_be_reused_or_read_under_changed_authority(bridge):
    method,body,token=request()
    assert getattr(bridge.stub,method)(body,timeout=8).value
    with pytest.raises(grpc.RpcError) as error:getattr(bridge.stub,method)(body,timeout=5)
    assert error.value.code()==grpc.StatusCode.PERMISSION_DENIED
    store=Results(bridge.journal,bridge.dispatcher.ground.namespace)
    original=store.read(bridge.identity,token)
    with pytest.raises(PermissionError):store.read(dict(bridge.identity,controller_epoch=2),token)
    changed=deepcopy(original);changed['outcome']='FAILED'
    request_id=bridge.journal.db.execute('SELECT request_id FROM command_results').fetchone()[0]
    with pytest.raises(ValueError,match='immutable'):store.save(bridge.identity,token,request_id,changed)
    assert store.read(bridge.identity,token)==original
    assert bridge.engine.state()['core']['commands_executed']==2


def test_invalid_later_member_is_rejected_before_any_effect_intent(bridge):
    method,body,token=request(rows=[('CMD1',{}),('CMD3',{'Timeout':0})])
    with pytest.raises(grpc.RpcError) as error:getattr(bridge.stub,method)(body,timeout=3)
    assert error.value.code()==grpc.StatusCode.INVALID_ARGUMENT
    assert packets(bridge)==[]
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


def test_command_binary_encoding_is_validated_before_effect_intent(bridge):
    method,body,token=request(rows=[('CMD1',{'addInfo':{1:'integer dictionary key'}})])
    with pytest.raises(grpc.RpcError) as error:getattr(bridge.stub,method)(body,timeout=3)
    assert error.value.code()==grpc.StatusCode.INVALID_ARGUMENT
    assert packets(bridge)==[]
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
