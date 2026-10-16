"""Observe actual TCP stage packets and independently controlled simulator time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'driver_plugin/src'))
from dss.local import create_servers
from dss.packets import decode_tc
from openbexi_spell_dss.command_execution import CommandExecution, plan
from openbexi_spell_dss.journal import UncertainEffect
from openbexi_spell_dss.transport import Transport


@pytest.fixture
def bridge(tmp_path):
    runtime,tcp,api=create_servers(tmp_path/'dss.sqlite',0)
    threads=[threading.Thread(target=service.serve_forever) for service in (tcp,api)]
    for thread in threads:thread.start()
    transport=Transport('http://127.0.0.1:'+str(api.server_port),tcp.server_address)
    pool=ThreadPoolExecutor(max_workers=1)
    env=SimpleNamespace(engine=runtime.engine,transport=transport,pool=pool,executor=CommandExecution(transport),
        identity=dict(definition='command-stages',procedure='execution'),calls=0)
    def check():env.calls+=1
    env.check=check
    env.send=lambda **options:env.executor.execute(plan(transport,'CMD1',[],options),env.identity,'operation',check)
    try:yield env
    finally:
        transport.close()
        pool.shutdown(wait=True,cancel_futures=True)
        for service in (tcp,api):service.shutdown();service.server_close()
        for thread in threads:
            thread.join(5);assert not thread.is_alive()
        runtime.engine.close()


def evidence(env):return env.engine.evidence(env.engine.state()['scenario_id'])
def packets(env):return [decode_tc(bytes.fromhex(row['packet_hex'])) for row in evidence(env)['operations']]
def steps(env,count):
    state=env.engine.state()
    return env.engine.control('STEP',state['epoch'],state['revision'],count)
def until(condition):
    deadline=time.monotonic()+5
    while not condition():
        assert time.monotonic()<deadline,'Independent stage observation timed out'
        time.sleep(.005)
def target(env,ticks):
    return (env.engine.state()['clock_epoch_unix_ns']+round(ticks*env.engine.catalog.material['dynamics']['tick_ns']))/1e9


def test_normal_command_has_five_actual_receipts_and_live_checks(bridge):
    passed,receipts=bridge.send(Timeout=60)
    assert passed and [row['stage'] for row in receipts]==['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION']
    assert [row['stage'] for row in packets(bridge)]==[row['stage'] for row in receipts]
    assert bridge.engine.state()['core']['commands_executed']==1
    assert bridge.calls>=10


@pytest.mark.parametrize('timed',[False,True])
def test_load_only_finishes_at_loading_without_release_or_execution(bridge,timed):
    options=dict(LoadOnly=True)
    if timed:options['Time']=target(bridge,3.5)
    passed,receipts=bridge.send(**options)
    assert passed and [row['stage'] for row in receipts]==['TRANSPORT','LOADING']
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING']
    assert steps(bridge,6)['core']['commands_executed']==0


def test_time_loads_and_releases_now_but_waits_for_onboard_execution(bridge):
    future=bridge.pool.submit(bridge.send,Time=target(bridge,3.5))
    until(lambda:len(packets(bridge))==4)
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT']
    assert bridge.engine.state()['core']['commands_executed']==0 and not future.done()
    assert steps(bridge,3)['core']['commands_executed']==0
    steps(bridge,1)
    passed,receipts=future.result(timeout=5)
    assert passed and receipts[-1]['outcome']=='SUCCEEDED'
    assert bridge.engine.state()['core']['commands_executed']==1
    assert len(packets(bridge))==5


@pytest.mark.parametrize('option',['SendDelay','ReleaseTime'])
def test_ground_delay_sends_no_frame_until_due(bridge,option):
    ticks=bridge.engine.catalog.material['dynamics']['tick_ns']
    value=3.5*ticks/1e9 if option=='SendDelay' else target(bridge,3.5)
    future=bridge.pool.submit(bridge.send,**{option:value})
    until(lambda:bridge.calls>=2)
    assert packets(bridge)==[] and bridge.engine.state()['core']['loaded_commands_count']==0
    steps(bridge,3)
    assert packets(bridge)==[]
    steps(bridge,1)
    assert future.result(timeout=5)[0]
    assert len(packets(bridge))==5


def test_relative_delay_is_added_to_verification_window(bridge):
    delay=2
    future=bridge.pool.submit(bridge.send,SendDelay=delay,Timeout=1)
    until(lambda:bridge.calls>=2)
    time.sleep(1.25)  # Longer than Timeout alone; still within SendDelay+Timeout.
    assert not future.done() and packets(bridge)==[]
    steps(bridge,1+round(delay*1e9/bridge.engine.catalog.material['dynamics']['tick_ns']))
    assert future.result(timeout=5)[0]


def test_ground_release_and_onboard_time_have_distinct_packet_boundaries(bridge):
    future=bridge.pool.submit(bridge.send,ReleaseTime=target(bridge,1.5),Time=target(bridge,5.5))
    until(lambda:bridge.calls>=2)
    assert packets(bridge)==[]
    steps(bridge,2)
    until(lambda:len(packets(bridge))==4)
    assert bridge.engine.state()['core']['commands_executed']==0
    steps(bridge,4)
    assert future.result(timeout=5)[0]
    assert bridge.engine.state()['core']['commands_executed']==1


def test_additional_information_reaches_actual_packets_and_persisted_definition(bridge):
    info={'note':'café λ','attempt':1,'details':{'enabled':True,'values':[1,'two']}}
    assert bridge.send(addInfo=info)[0]
    assert all(row['additional_info']==info for row in packets(bridge))
    assert evidence(bridge)['commands'][0]['definition']['additional_info']==info


@pytest.mark.parametrize('options',[
    {'Timeout':0},{'Timeout':True},{'Timeout':3601},{'Timeout':float('nan')},
    {'SendDelay':-1},{'SendDelay':86401},{'SendDelay':True},{'Time':'tomorrow'},
    {'Time':False},{'ReleaseTime':float('inf')},{'LoadOnly':1},{'addInfo':[]},
    {'addInfo':{'too-long':'a'*8192}},{'addInfo':{'invalid':float('nan')}},{'Unknown':1},
    {'addInfo':None},{'Time':None},{'ReleaseTime':None}])
def test_invalid_plan_has_no_transmission(bridge,options):
    with pytest.raises((ValueError,TypeError)):bridge.send(**options)
    assert packets(bridge)==[] and bridge.engine.state()['core']['commands_executed']==0


def test_schedule_beyond_horizon_is_rejected_before_transmission(bridge):
    with pytest.raises(ValueError,match='one-day'):
        bridge.send(Time=bridge.engine.state()['clock_epoch_unix_ns']/1e9+86401)
    assert packets(bridge)==[]


def test_authority_loss_after_loading_retains_receipts_and_does_not_release(bridge):
    def check():
        if len(packets(bridge))>=2:raise PermissionError('controller lease lost')
    with pytest.raises(UncertainEffect):
        bridge.executor.execute(plan(bridge.transport,'CMD1',[],{}),bridge.identity,'lease-test',check)
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING']
    assert bridge.engine.state()['core']['commands_executed']==0


def test_closed_transport_cannot_wait_or_replay_a_scheduled_command(bridge):
    future=bridge.pool.submit(bridge.send,Time=target(bridge,3.5))
    until(lambda:len(packets(bridge))==4)
    bridge.transport.close()
    with pytest.raises(UncertainEffect):future.result(timeout=5)
    assert steps(bridge,4)['core']['commands_executed']==1
    assert len(packets(bridge))==4  # Onboard work continues without driver retries.


def test_closed_transport_cannot_begin_an_immediate_command(bridge):
    bridge.transport.close()
    with pytest.raises(RuntimeError,match='closed'):bridge.send()
    assert packets(bridge)==[]
