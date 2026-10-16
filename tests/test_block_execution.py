"""A block is one real encoded uplink frame, not a series relabelled as atomic."""
import pytest

from test_command_execution import bridge,packets,steps,until,target
from test_group_execution import plans,launch
from dss.packets import encode_tc
from openbexi_spell_dss.command_blocks import BlockExecution
from openbexi_spell_dss.journal import UncertainEffect


def test_block_uses_one_real_frame_for_two_distinct_command_elements(bridge):
    executor=BlockExecution(bridge.transport)
    passed,receipts=executor.execute(plans(bridge,('CMD1',{}),('CMD3',{})),bridge.identity,'block-operation',bridge.check)
    assert passed and len(receipts)==9
    rows=packets(bridge)
    transport,=[row for row in rows if row['stage']=='TRANSPORT']
    assert [e['command_name'] for e in transport['elements']]==['CMD1','CMD3']
    assert [e['element_id'] for e in transport['elements']]==['command-0','command-1']
    assert bridge.engine.state()['core']['commands_executed']==2


def test_block_duplicate_members_remain_distinct_and_load_only(bridge):
    executor=BlockExecution(bridge.transport)
    passed,receipts=executor.execute(plans(bridge,('CMD1',{'LoadOnly':True}),('CMD1',{'LoadOnly':True})),bridge.identity,'block-operation',bridge.check)
    assert passed and [r['stage'] for r in receipts]==['TRANSPORT','LOADING','LOADING']
    assert len(packets(bridge)[0]['elements'])==2
    assert [r['state'] for r in executor.member_results]==['LOADED','LOADED']
    assert steps(bridge,10)['core']['commands_executed']==0


def test_block_binds_each_members_metadata_and_time(bridge):
    due=target(bridge,3.5)
    executor=BlockExecution(bridge.transport)
    rows=plans(bridge,('CMD1',{'Time':due,'addInfo':{'note':'café λ'}}),
                      ('CMD3',{'Time':due,'addInfo':{'ordinal':2}}))
    future=launch(bridge,rows,executor)
    until(lambda:len(packets(bridge))==7)
    assert bridge.engine.state()['core']['commands_executed']==0
    elements=packets(bridge)[0]['elements']
    assert [e['additional_info'] for e in elements]==[{'note':'café λ'},{'ordinal':2}]
    assert all(e['execution_time_unix_ns']==round(due*1e9) for e in elements)
    steps(bridge,4)
    assert future.result(timeout=5)[0]
    assert bridge.engine.state()['core']['commands_executed']==2
    assert [r['state'] for r in executor.member_results]==['SUCCEEDED','SUCCEEDED']


def test_shared_frame_waits_until_all_ground_constraints_are_due(bridge):
    executor=BlockExecution(bridge.transport)
    future=launch(bridge,plans(bridge,('CMD1',{'ReleaseTime':target(bridge,1.5)}),
        ('CMD3',{'ReleaseTime':target(bridge,3.5)})),executor)
    until(lambda:bridge.calls>=2)
    steps(bridge,3)
    assert packets(bridge)==[]
    steps(bridge,1)
    assert future.result(timeout=5)[0]
    assert len([r for r in packets(bridge) if r['stage']=='TRANSPORT'])==1


def test_failed_first_member_leaves_other_block_members_loaded(bridge):
    state=bridge.engine.state()
    state=bridge.engine.reset('block-failure',faults={'execution_fail':True},expected_epoch=state['epoch'])
    bridge.transport.epoch,bridge.transport.scenario=state['epoch'],state['scenario_id']
    executor=BlockExecution(bridge.transport)
    success,receipts=executor.execute(plans(bridge,('CMD1',{}),('CMD3',{})),bridge.identity,'block-operation',bridge.check)
    assert not success and len(receipts)==5
    assert [r['state'] for r in executor.member_results]==['FAILED','LOADED']
    assert bridge.engine.state()['core']['loaded_commands_count']==2
    assert bridge.engine.state()['core']['commands_executed']==0


def test_authority_loss_after_shared_frame_preserves_loads_without_release(bridge):
    executor=BlockExecution(bridge.transport)
    def check():
        if packets(bridge):raise PermissionError('Controller revoked')
    with pytest.raises(UncertainEffect):
        executor.execute(plans(bridge,('CMD1',{}),('CMD3',{})),bridge.identity,'block-operation',check)
    assert len(packets(bridge))==1
    assert bridge.engine.state()['core']['loaded_commands_count']==2
    assert bridge.engine.state()['core']['commands_executed']==0


@pytest.mark.parametrize('change',[{'execution_time_unix_ns':True},{'execution_time_unix_ns':-1},
    {'additional_info':[]},{'additional_info':{'oversize':'x'*8192}},{'unknown':True}])
def test_invalid_later_element_rolls_back_whole_shared_frame(bridge,change,tmp_path):
    executor=BlockExecution(bridge.transport)
    # Obtain a genuine encoded frame, then use a separate reset scenario to
    # prove a malformed second element cannot leave the valid first one loaded.
    executor.execute(plans(bridge,('CMD1',{'LoadOnly':True}),('CMD3',{'LoadOnly':True})),bridge.identity,'fixture-frame',bridge.check)
    frame=packets(bridge)[0]
    # A fresh engine avoids retiring any of this retained frame's loaded state.
    from dss.engine import DssEngine
    engine=DssEngine(tmp_path/'separate.sqlite')
    try:
        state=engine.state();frame.update(scenario_id=state['scenario_id'],satellite_epoch=state['epoch'])
        frame['elements'][1].update(change)
        with pytest.raises(ValueError):engine.process_tc(frame,encode_tc(frame))
        assert engine.state()['core']['loaded_commands_count']==0
        assert engine.evidence(state['scenario_id'])['operations']==[]
    finally:engine.close()
