"""Composed dispatcher, original protobuf RPC, real DSS TCP and immutable receipts."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
from pathlib import Path
import sys
import threading
import time
import types
import uuid

import grpc
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'driver_plugin/src'))
sys.path.insert(0,str(ROOT/'source_port'))
import command_feature_patches
import display_patches
import integrated_patches
from dss.local import create_servers
from dss.packets import decode_tc
from openbexi_spell_dss.codec import pack
from openbexi_spell_dss.command_budget import command_budget,relay_budget
from openbexi_spell_dss.journal import UncertainEffect
from openbexi_spell_dss.server import Server
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p, SPELLDriver_pb2_grpc as g
from openbexi_spell_dss.transport import Transport


def composed(name):
    path = 'openbexi_spell_dss/'+name+'.py'
    raw = (ROOT/'driver_plugin/src'/path).read_bytes()
    for recipe in integrated_patches.DRIVER_RECIPES+(display_patches,command_feature_patches):
        if path in recipe.PREIMAGES:
            raw = recipe.apply(path,raw)
    module = types.ModuleType('openbexi_spell_dss._command_rpc_test_'+name)
    exec(compile(raw,path,'exec'),module.__dict__)
    return module


@pytest.fixture
def bridge(tmp_path,monkeypatch):
    monkeypatch.setitem(sys.modules,'openbexi_spell_dss.ground',composed('ground'))
    runtime,tcp,http = create_servers(tmp_path/'dss.sqlite',0)
    threads = [threading.Thread(target=service.serve_forever) for service in (tcp,http)]
    for thread in threads:thread.start()
    transport = Transport('http://127.0.0.1:'+str(http.server_port),tcp.server_address)
    journal = composed('journal').Journal(tmp_path/'effects.sqlite')
    dispatcher = composed('rpc').Dispatcher(transport,journal)
    who = dict(session=uuid.uuid4().hex,procedure=uuid.uuid4().hex,definition='command-rpc',
               version='candidate',controller_epoch=1,procedure_fence=1,mode='Development',release=None)
    env = types.SimpleNamespace(engine=runtime.engine,transport=transport,journal=journal,dispatcher=dispatcher,
                                identity=who,request_id=None,calls=0,allowed=True)
    def check():
        env.calls += 1
        if not env.allowed:raise PermissionError('Authority revoked')
    env.check = check
    def dispatch(path,raw):
        return dispatcher.dispatch(path,raw,who,env.request_id or uuid.uuid4().hex,check)
    env.dispatch = dispatch
    server = Server(dispatch)
    channel = grpc.insecure_channel('127.0.0.1:'+str(server.port))
    env.stub = g.SPELLDriverInterface_TCStub(channel)
    env.pcs = g.SPELLDriverInterface_PCSStub(channel)
    env.pool = ThreadPoolExecutor(max_workers=2)
    try:yield env
    finally:
        transport.close();env.pool.shutdown(wait=True,cancel_futures=True)
        channel.close();server.close();journal.close()
        for service in (tcp,http):service.shutdown();service.server_close()
        for thread in threads:
            thread.join(5);assert not thread.is_alive()
        runtime.engine.close()


def command(name='CMD1',**options):
    return p.CommandDesc(command=p.TcItemDesc(mnemonic=name),args=pack([]),config=pack(options))


def packets(env):
    evidence = env.engine.evidence(env.engine.state()['scenario_id'])
    return [decode_tc(bytes.fromhex(row['packet_hex'])) for row in evidence['operations']]


def until(condition):
    deadline = time.monotonic()+5
    while not condition():
        assert time.monotonic()<deadline
        time.sleep(.005)


def step(env,count):
    state = env.engine.state()
    return env.engine.control('STEP',state['epoch'],state['revision'],count)


def target(env,ticks):
    state = env.engine.state()
    return (state['clock_epoch_unix_ns']+state['core']['sim_time_ns']+
            round(ticks*env.engine.catalog.material['dynamics']['tick_ns']))/1e9


def test_rpc_load_only_receipted_and_repeated_without_release(bridge):
    bridge.request_id = uuid.uuid4().hex
    request = command(LoadOnly=True,Timeout=60,Time=target(bridge,5))
    assert bridge.stub.SendCommand(request,timeout=5).value
    assert bridge.stub.SendCommand(request,timeout=5).value
    assert [row['stage'] for row in packets(bridge)] == ['TRANSPORT','LOADING']
    assert step(bridge,8)['core']['commands_executed'] == 0
    assert bridge.journal.db.execute('SELECT state FROM effects').fetchall() == [('RECEIPTED',)]


def test_rpc_onboard_time_has_four_receipts_before_effect(bridge):
    future = bridge.stub.SendCommand.future(command(Time=target(bridge,3.5)),timeout=8)
    until(lambda:len(packets(bridge))==4)
    assert bridge.engine.state()['core']['commands_executed']==0
    assert step(bridge,3)['core']['commands_executed']==0
    assert not future.done()
    step(bridge,1)
    assert future.result(timeout=5).value
    assert packets(bridge)[-1]['stage']=='ONBOARD_EXECUTION'
    assert bridge.engine.state()['core']['commands_executed']==1


@pytest.mark.parametrize('key',['SendDelay','ReleaseTime'])
def test_rpc_ground_hold_has_no_binary_command_before_due(bridge,key):
    value = .15 if key=='SendDelay' else target(bridge,1.5)
    future = bridge.stub.SendCommand.future(command(**{key:value}),timeout=8)
    until(lambda:bridge.calls>=4)
    assert packets(bridge)==[]
    step(bridge,1)
    assert packets(bridge)==[]
    step(bridge,1)
    assert future.result(timeout=5).value
    assert len(packets(bridge))==5


def test_rpc_list_preserves_duplicate_members_and_metadata(bridge):
    field = p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TC'].methods_by_name['SendList'].input_type
    from google.protobuf.message_factory import GetMessageClass
    request = GetMessageClass(field)(commands=[command(addInfo={'note':'café λ'}),command(),command('CMD2')],config=pack({'Timeout':60}))
    assert bridge.stub.SendList(request,timeout=8).value
    rows = packets(bridge)
    assert [row['command_name'] for row in rows if row['stage']=='RELEASE']==['CMD1','CMD1','CMD2']
    assert len({row['plan_id'] for row in rows})==3
    assert all(row['additional_info']=={'note':'café λ'} for row in rows[:5])
    assert bridge.engine.state()['core']['commands_executed']==3


@pytest.mark.parametrize('options',[{'Timeout':0},{'Timeout':3601},{'LoadOnly':1},{'Group':True},
                                  {'Block':True},{'Time':None},{'addInfo':None},{'ConfirmCritical':1}])
def test_invalid_rpc_never_creates_intent_or_packet(bridge,options):
    with pytest.raises(grpc.RpcError) as error:
        bridge.stub.SendCommand(command(**options),timeout=3)
    assert error.value.code()==grpc.StatusCode.INVALID_ARGUMENT
    assert packets(bridge)==[]
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


def test_rpc_out_of_horizon_rejected_before_effect_intent(bridge):
    with pytest.raises(grpc.RpcError) as error:
        bridge.stub.SendCommand(command(Time=target(bridge,1)+86400),timeout=3)
    assert error.value.code()==grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
    assert packets(bridge)==[]


def test_critical_requires_confirmation_policy_and_explicit_false_works(bridge):
    with pytest.raises(grpc.RpcError) as error:
        bridge.stub.SendCommand(command('TC.SIMULATOR.RESET'),timeout=3)
    assert error.value.code()==grpc.StatusCode.PERMISSION_DENIED
    assert packets(bridge)==[]
    assert bridge.stub.SendCommand(command('TC.SIMULATOR.RESET',ConfirmCritical=False),timeout=5).value
    assert len(packets(bridge))==5


def test_authority_loss_after_loading_never_releases_or_replays(bridge):
    old = bridge.check
    def check():
        old()
        if len(packets(bridge))>=2:raise PermissionError('Revoked after loading')
    path = '/spell.driver.SPELLDriverInterface_TC/SendCommand'
    raw = command().SerializeToString()
    request = uuid.uuid4().hex
    with pytest.raises(UncertainEffect):
        bridge.dispatcher.dispatch(path,raw,bridge.identity,request,check)
    journal_uncertain = bridge.journal.begin.__globals__['UncertainEffect']
    with pytest.raises(journal_uncertain,match='unresolved driver effect'):
        bridge.dispatcher.dispatch(path,raw,bridge.identity,uuid.uuid4().hex,lambda:None)
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING']
    assert bridge.engine.state()['core']['commands_executed']==0


def test_pcs_load_only_status_matches_actual_stage(bridge):
    request = p.PtcDesc(command=p.PtcItemDesc(mnemonic='CMD1'),args=pack([]),config=pack({'LoadOnly':True}))
    reply = bridge.pcs.SendPtcCommand(request,timeout=5)
    assert list(reply.success)==[True] and list(reply.stage)==['LOADING']
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING']


def test_command_wire_budget_covers_relative_delay_and_one_day_horizon():
    request = command(Timeout=60,SendDelay=2,Time=1800000000)
    path = '/spell.driver.SPELLDriverInterface_TC/SendCommand'
    assert command_budget('TC','SendCommand',request)==86462
    assert relay_budget(path,request.SerializeToString())==86462
    assert command_budget('TC','SendCommand',command(Timeout=60))==60


def test_relay_really_waits_beyond_old_35_second_limit():
    relay_type = composed('relay').Relay
    sent = threading.Event()
    rows=[]
    relay = relay_type(lambda event,**row:(rows.append(row),sent.set()))
    channel = grpc.insecure_channel('127.0.0.1:'+str(relay.port))
    from google.protobuf.wrappers_pb2 import BoolValue
    import base64
    try:
        future = g.SPELLDriverInterface_TCStub(channel).SendCommand.future(command(Timeout=60),timeout=64)
        assert sent.wait(3)
        time.sleep(36)
        assert not future.done()
        relay.reply({'id':rows[0]['id'],'payload':base64.b64encode(BoolValue(value=True).SerializeToString()).decode()})
        assert future.result(timeout=5).value
    finally:
        channel.close();relay.close()
