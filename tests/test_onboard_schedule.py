"""Real packet, persistent engine, and independent dynamics evidence for timetags."""
import pytest

from dss.engine import DssConflict, DssEngine, scenario_retirement_token
from dss.packets import decode_tc, decode_tm, encode_tc


def body(engine, *, ticks=3, name='CMD1', element='1'):
    state = engine.state()
    return dict(schema_version='openbexi.dss.tc/1', satellite_id='GENERIC',
        database_revision=engine.catalog.revision, database_digest=engine.catalog.digest,
        satellite_epoch=state['epoch'], scenario_id=state['scenario_id'],
        operation_id='operation-'+element, procedure_id='schedule-test', execution_id='execution',
        plan_id='plan', element_id=element, stage='TRANSPORT', command_name=name,
        arguments=[], command_digest='a'*64,
        execution_time_unix_ns=state['clock_epoch_unix_ns']+state['core']['sim_time_ns']+
            round(ticks*engine.catalog.material['dynamics']['tick_ns']))


def send(engine, command, stage):
    message = dict(command, stage=stage)
    return engine.process_tc(message, encode_tc(message))


def step(engine, ticks):
    state = engine.state()
    return engine.control('STEP', state['epoch'], state['revision'], ticks)


def evidence(engine):
    return engine.evidence(engine.state()['scenario_id'])


def test_load_and_release_before_target_then_execute_on_first_due_tick(tmp_path):
    engine = DssEngine(tmp_path/'schedule.sqlite')
    command = body(engine, ticks=2.5)
    try:
        assert send(engine,command,'TRANSPORT')['outcome']=='ACCEPTED'
        assert send(engine,command,'LOADING')['outcome']=='LOADED'
        release = send(engine,command,'RELEASE')
        assert release['outcome']=='RELEASED' and release['simulation_time_ns']==0
        assert send(engine,command,'ACKNOWLEDGEMENT')['outcome']=='ACKNOWLEDGED'
        assert not engine.state()['payload']['enabled']
        assert step(engine,2)['core']['commands_executed']==0
        assert step(engine,1)['core']['commands_executed']==1
        assert engine.state()['payload']['enabled']
        assert send(engine,command,'ONBOARD_EXECUTION')['outcome']=='SUCCEEDED'
        assert send(engine,command,'RELEASE')==release
        state=step(engine,3)
        assert state['core']['commands_executed']==1
        record=evidence(engine)
        assert record['commands'][0]['results']['execution_sim_time_ns']==3*engine.catalog.material['dynamics']['tick_ns']
        assert all(decode_tc(bytes.fromhex(row['packet_hex']))['execution_time_unix_ns']==command['execution_time_unix_ns'] for row in record['operations'])
        caused=[decode_tm(bytes.fromhex(row['packet_hex'])) for row in record['packets'] if row['topic'].endswith('.tm')]
        effect=next(row for row in caused if row.get('cause_command')=='CMD1' and any(
            item['item_id']=='TM.PAYLOAD.ENABLED' and item['engineering']['value'] is True for item in row['items']))
        assert effect['operation_id']==command['operation_id']
    finally:
        engine.close()


def test_schedule_survives_restart_and_does_not_need_a_driver(tmp_path):
    path=tmp_path/'persistent.sqlite';engine=DssEngine(path)
    command=body(engine)
    send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
    saved=engine.state();engine.close();engine=DssEngine(path)
    try:
        assert engine.state()==saved
        step(engine,3)
        assert engine.state()['core']['commands_executed']==1
        assert evidence(engine)['commands'][0]['results']['ONBOARD_EXECUTION']=='SUCCEEDED'
        assert engine.db.execute('SELECT count(*) FROM onboard_schedule').fetchone()[0]==0
    finally:engine.close()


def test_loaded_only_timetag_does_not_execute_when_clock_advances():
    engine=DssEngine(':memory:');command=body(engine)
    try:
        send(engine,command,'TRANSPORT');send(engine,command,'LOADING')
        assert step(engine,10)['core']['commands_executed']==0
        assert not evidence(engine)['commands'][0]['executed']
        assert 'RELEASE' not in evidence(engine)['commands'][0]['results']
    finally:engine.close()


@pytest.mark.parametrize('ticks',[0,-1])
def test_due_or_past_timetag_executes_at_release(ticks):
    engine=DssEngine(':memory:');command=body(engine,ticks=ticks)
    try:
        send(engine,command,'TRANSPORT')
        assert send(engine,command,'RELEASE')['outcome']=='RELEASED'
        assert engine.state()['core']['commands_executed']==1
        assert engine.db.execute('SELECT count(*) FROM onboard_schedule').fetchone()[0]==0
    finally:engine.close()


@pytest.mark.parametrize('value',[True,-1,1.5,'2026-01-01',1<<63,None,'tomorrow'])
def test_invalid_execution_time_has_no_state_or_command_intent(value):
    engine=DssEngine(':memory:');command=body(engine);command['execution_time_unix_ns']=value
    try:
        before=evidence(engine)
        with pytest.raises((ValueError,TypeError)):send(engine,command,'TRANSPORT')
        assert evidence(engine)==before
    finally:engine.close()


def test_horizon_boundary_and_changed_or_removed_timetag_are_rejected():
    engine=DssEngine(':memory:');command=body(engine)
    try:
        command['execution_time_unix_ns']=engine.state()['clock_epoch_unix_ns']+86_400_000_000_001
        with pytest.raises(ValueError,match='one-day'):send(engine,command,'TRANSPORT')
        command['execution_time_unix_ns']-=1
        send(engine,command,'TRANSPORT')
        for modified in (dict(command,execution_time_unix_ns=command['execution_time_unix_ns']-1),
                         {key:value for key,value in command.items() if key!='execution_time_unix_ns'}):
            with pytest.raises(DssConflict,match='definition changed'):send(engine,modified,'RELEASE')
        assert engine.state()['core']['commands_executed']==0
    finally:engine.close()


@pytest.mark.parametrize('faults,initial',[({'execution_fail':True},{}),({}, {'bus':{'safe_mode':True}})])
def test_scheduled_failure_is_terminal_and_does_not_replay(faults,initial):
    engine=DssEngine(':memory:');engine.reset('failure',initial_state=initial,faults=faults)
    command=body(engine)
    try:
        send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        step(engine,3)
        assert send(engine,command,'ONBOARD_EXECUTION')['outcome']=='FAILED'
        assert engine.state()['core']['commands_executed']==0
        state=step(engine,3)
        assert state['core']['commands_executed']==0
        assert evidence(engine)['commands'][0]['results']['RELEASE']=='RELEASED'
        assert engine.db.execute('SELECT count(*) FROM onboard_schedule').fetchone()[0]==0
    finally:engine.close()


def test_multiple_due_commands_follow_ticks_and_preserve_intervening_physics():
    engine=DssEngine(':memory:')
    try:
        for command in (body(engine,ticks=2,name='CMD1',element='on'),body(engine,ticks=4,name='CMD2',element='off')):
            send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        state=step(engine,6)
        assert state['core']['commands_executed']==2 and not state['payload']['enabled']
        assert state['payload']['generated_data_bytes']==2*engine.catalog.material['dynamics']['payload_bytes_per_tick']
        assert sorted(row['results']['execution_sim_time_ns'] for row in evidence(engine)['commands'])==[
            n*engine.catalog.material['dynamics']['tick_ns'] for n in (2,4)]
    finally:engine.close()


def test_pending_schedule_requires_explicit_retirement():
    engine=DssEngine(':memory:');command=body(engine)
    try:
        send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        with pytest.raises(DssConflict,match='pending onboard'):engine.reset('next')
        old=engine.state()
        engine.reset('next',retirement_token=scenario_retirement_token(old))
        retired=engine.evidence(old['scenario_id'])['retirement']['scheduled_commands']
        assert retired[0]['element_id']==command['element_id']
        assert step(engine,5)['core']['commands_executed']==0
    finally:engine.close()


def test_early_execution_query_is_known_pending_and_later_query_observes_execution():
    engine=DssEngine(':memory:');command=body(engine)
    try:
        send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        pending=send(engine,command,'ONBOARD_EXECUTION')
        assert pending['outcome']=='PENDING'
        step(engine,3)
        assert send(engine,command,'ONBOARD_EXECUTION')==pending  # immutable original observation
        assert send(engine,dict(command,operation_id='fresh-observation'),'ONBOARD_EXECUTION')['outcome']=='SUCCEEDED'
    finally:engine.close()


def test_schedule_capacity_failure_retains_loaded_command_without_false_release():
    engine=DssEngine(':memory:')
    try:
        for number in range(64):
            command=body(engine,element=str(number))
            send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        overflow=body(engine,element='overflow')
        send(engine,overflow,'TRANSPORT')
        before=evidence(engine)
        with pytest.raises(DssConflict,match='capacity'):send(engine,overflow,'RELEASE')
        assert evidence(engine)==before
        assert engine.db.execute('SELECT count(*) FROM onboard_schedule').fetchone()[0]==64
        assert engine.state()['core']['commands_executed']==0
        record=next(row for row in before['commands'] if row['element_id']=='overflow')
        assert record['results']=={'TRANSPORT':'ACCEPTED','LOADING':'LOADED'}
    finally:engine.close()


def test_running_clock_executes_schedule_and_paused_clock_retains_it():
    engine=DssEngine(':memory:');command=body(engine)
    try:
        send(engine,command,'TRANSPORT');send(engine,command,'RELEASE')
        paused=engine.state()
        assert engine.advance(5)==paused
        engine.control('RESUME',paused['epoch'],paused['revision'])
        assert engine.advance(3)['core']['commands_executed']==1
    finally:engine.close()
