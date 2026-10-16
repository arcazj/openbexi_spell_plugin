"""Grouped driver commands observed at actual TCP/engine boundaries."""
import time

import pytest

from test_command_execution import bridge,packets,steps,until,target
from openbexi_spell_dss.command_execution import plan
from openbexi_spell_dss.command_groups import GroupExecution
from openbexi_spell_dss.journal import UncertainEffect


def plans(env,*rows):
    return [plan(env.transport,name,[],options) for name,options in rows]


def launch(env,rows,executor=None,check=None):
    executor=executor or GroupExecution(env.transport)
    return env.pool.submit(executor.execute,rows,env.identity,'group-operation',check or env.check)


def test_group_preserves_members_and_actual_stage_receipts(bridge):
    executor=GroupExecution(bridge.transport)
    rows=plans(bridge,('CMD1',{}),('CMD3',{}))
    passed,receipts=executor.execute(rows,bridge.identity,'group-operation',bridge.check)
    assert passed and len(receipts)==10
    assert [p['command_name'] for p in packets(bridge) if p['stage']=='TRANSPORT']==['CMD1','CMD3']
    assert len({p['plan_id'] for p in packets(bridge)})==1
    assert len({p['element_id'] for p in packets(bridge)})==2
    assert [r['state'] for r in executor.member_results]==['SUCCEEDED','SUCCEEDED']
    assert bridge.engine.state()['core']['commands_executed']==2
    assert executor.control_receipts[-1]['stage']=='GROUP_END'


def test_competing_source_cannot_enter_between_group_members(bridge):
    rows=plans(bridge,('CMD1',{'LoadOnly':True}),('CMD3',{'SendDelay':2}))
    future=launch(bridge,rows)
    until(lambda:len(packets(bridge))==2)
    success,receipts=bridge.transport.command('CMD2',[],bridge.identity,'competing-source',bridge.check)
    assert not success and receipts[0]['detail']['reason']=='UPLINK_GROUP_BUSY'
    assert bridge.engine.state()['core']['loaded_commands_count']==1
    assert bridge.engine.state()['core']['commands_executed']==0
    steps(bridge,21)
    assert future.result(timeout=5)[0]
    accepted=[row for row in bridge.engine.evidence(bridge.engine.state()['scenario_id'])['operations']
              if row['acknowledgement']['stage']=='TRANSPORT' and row['acknowledgement']['outcome']=='ACCEPTED']
    assert [row['acknowledgement']['command_name'] for row in accepted]==['CMD1','CMD3']


def test_future_group_loads_and_releases_all_members_before_execution(bridge):
    due=target(bridge,3.5)
    executor=GroupExecution(bridge.transport)
    future=launch(bridge,plans(bridge,('CMD1',{'Time':due}),('CMD3',{'Time':due})),executor)
    until(lambda:len(packets(bridge))==8)
    assert [p['stage'] for p in packets(bridge)]==['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT']*2
    assert bridge.engine.state()['core']['commands_executed']==0
    assert steps(bridge,3)['core']['commands_executed']==0
    steps(bridge,1)
    assert future.result(timeout=5)[0]
    assert [p['element_id'] for p in packets(bridge)[-2:]]==['command-0','command-1']
    assert bridge.engine.state()['core']['commands_executed']==2


def test_duplicate_group_commands_are_distinct_elements(bridge):
    executor=GroupExecution(bridge.transport)
    assert executor.execute(plans(bridge,('CMD1',{}),('CMD1',{})),bridge.identity,'group-operation',bridge.check)[0]
    assert bridge.engine.state()['core']['commands_executed']==2
    assert len({row['element_id'] for row in packets(bridge)})==2


def test_load_only_group_and_per_member_metadata_are_preserved(bridge):
    one={'note':'café λ'};two={'ordinal':2}
    executor=GroupExecution(bridge.transport)
    assert executor.execute(plans(bridge,('CMD1',{'LoadOnly':True,'addInfo':one}),
        ('CMD3',{'LoadOnly':True,'addInfo':two})),bridge.identity,'group-operation',bridge.check)[0]
    rows=packets(bridge)
    assert [row['stage'] for row in rows]==['TRANSPORT','LOADING']*2
    assert [row['additional_info'] for row in rows]==[one,one,two,two]
    assert steps(bridge,10)['core']['commands_executed']==0
    assert [r['state'] for r in executor.member_results]==['LOADED','LOADED']


def test_group_delay_longer_than_idle_limit_keeps_live_reservation(bridge):
    executor=GroupExecution(bridge.transport)
    future=launch(bridge,plans(bridge,('CMD1',{'LoadOnly':True}),('CMD3',{'SendDelay':8})),executor)
    until(lambda:len(packets(bridge))==2)
    time.sleep(5.2)
    assert not future.done() and len(packets(bridge))==2
    steps(bridge,81)
    assert future.result(timeout=5)[0]
    assert sum(r['stage']=='GROUP_HOLD' for r in executor.control_receipts)>=4


def test_group_authority_loss_leaves_later_members_unsent_and_prevents_replay(bridge):
    executor=GroupExecution(bridge.transport)
    rows=plans(bridge,('CMD1',{}),('CMD3',{}))
    def check():
        if len(packets(bridge))>=2:raise PermissionError('Authority lost')
    with pytest.raises(UncertainEffect):executor.execute(rows,bridge.identity,'group-operation',check)
    assert [row['stage'] for row in packets(bridge)]==['TRANSPORT','LOADING']
    assert executor.member_results[1]['state']=='NOT_SENT'
    with pytest.raises(ValueError,match='replayed'):executor.execute(rows,bridge.identity,'group-operation',bridge.check)
    assert bridge.engine.state()['core']['commands_executed']==0


def test_definitive_failed_member_stops_before_next_transport(bridge):
    state=bridge.engine.state()
    state=bridge.engine.reset('failure',faults={'execution_fail':True},expected_epoch=state['epoch'])
    bridge.transport.epoch,bridge.transport.scenario=state['epoch'],state['scenario_id']
    executor=GroupExecution(bridge.transport)
    success,receipts=executor.execute(plans(bridge,('CMD1',{}),('CMD3',{})),bridge.identity,'group-operation',bridge.check)
    assert not success and len(receipts)==5
    assert [r['state'] for r in executor.member_results]==['FAILED','NOT_SENT']
    assert bridge.engine.state()['core']['commands_executed']==0


def test_invalid_group_size_has_no_packet(bridge):
    executor=GroupExecution(bridge.transport)
    with pytest.raises(ValueError):
        executor.execute(plans(bridge,*[('CMD1',{})]*17),bridge.identity,'group-operation',bridge.check)
    assert packets(bridge)==[]
