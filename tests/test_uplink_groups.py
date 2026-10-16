"""Real competing TCP clients: group ownership, bounded waits and definitive rejection."""
import socket
import time

import pytest

from test_dss_transports import runtime,serving,command
from dss.packets import encode_tc,decode_tm,recv_packet,PacketError
from dss.server import TcServer


def member(runtime,index=0,stage='TRANSPORT',*,count=2,timeout=30):
    body=command(runtime,stage,'group-operation')
    body.update(plan_id='group-plan',element_id='command-'+str(index),
                uplink_group=dict(id='group-plan',index=index,count=count,timeout_seconds=timeout))
    return body


def send(connection,body):
    connection.sendall(encode_tc(body))
    return decode_tm(recv_packet(connection))


def ordinary(runtime,operation):
    body=command(runtime,'TRANSPORT',operation)
    body.update(plan_id=operation,element_id='ordinary')
    return body


def until(condition):
    deadline=time.monotonic()+3
    while not condition():
        assert time.monotonic()<deadline
        time.sleep(.005)


def test_foreign_source_is_rejected_without_loading_or_clock_advance(runtime):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner,socket.create_connection(address,timeout=3) as foreign:
            first=send(owner,member(runtime));assert first['outcome']=='ACCEPTED'
            before=runtime.engine.state()
            busy=send(foreign,ordinary(runtime,'competitor'))
            assert busy['outcome']=='REJECTED' and busy['detail']['reason']=='UPLINK_GROUP_BUSY'
            after=runtime.engine.state()
            assert after['core']==before['core'] and after['revision']==before['revision']
            assert send(owner,member(runtime,stage='LOADING'))['outcome']=='LOADED'
            assert send(owner,member(runtime,1))['outcome']=='ACCEPTED'
            assert send(owner,member(runtime,1,'LOADING'))['outcome']=='LOADED'
            assert send(owner,member(runtime,1,'GROUP_END'))['outcome']=='ACCEPTED'
            assert send(foreign,ordinary(runtime,'after-group'))['outcome']=='ACCEPTED'
            # A definitively rejected operation remains rejected after reservation ends.
            assert send(foreign,ordinary(runtime,'competitor'))==busy
    history=runtime.uplink_groups.history[-1]
    assert history['reason']=='COMPLETED' and history['count']==2 and history['frames']==4
    assert runtime.engine.state()['core']['loaded_commands_count']==3


def test_group_transport_duplicate_returns_same_ack_without_second_load(runtime):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner:
            body=member(runtime)
            first=send(owner,body)
            assert send(owner,body)==first
    assert runtime.engine.state()['core']['loaded_commands_count']==1
    assert runtime.uplink_groups.history[-1]['reason']=='DISCONNECTED'


def test_disconnect_releases_group_and_does_not_execute_loaded_member(runtime):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner:
            assert send(owner,member(runtime))['outcome']=='ACCEPTED'
        until(lambda:runtime.uplink_groups.owner is None)
        with socket.create_connection(address,timeout=3) as foreign:
            assert send(foreign,ordinary(runtime,'after-disconnect'))['outcome']=='ACCEPTED'
    assert runtime.engine.state()['core']['commands_executed']==0


def test_group_expiry_does_not_permit_resuming_a_partial_group(runtime):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner,socket.create_connection(address,timeout=3) as foreign:
            assert send(owner,member(runtime,timeout=.1))['outcome']=='ACCEPTED'
            time.sleep(.15)
            assert send(foreign,ordinary(runtime,'after-expiry'))['outcome']=='ACCEPTED'
            with pytest.raises(PacketError,match='TCP closed before a complete Space Packet'):
                send(owner,member(runtime,1,timeout=.1))
    assert any(row['reason']=='EXPIRED' for row in runtime.uplink_groups.history)
    assert runtime.engine.state()['core']['loaded_commands_count']==2


def test_heartbeats_survive_idle_bound_without_command_effect(runtime):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner:
            assert send(owner,member(runtime))['outcome']=='ACCEPTED'
            for _ in range(3):
                time.sleep(2)
                ack=send(owner,member(runtime,stage='GROUP_HOLD'))
                assert ack['schema_version']=='openbexi.dss.uplink-group-ack/1'
            assert send(owner,member(runtime,1))['outcome']=='ACCEPTED'
            assert send(owner,member(runtime,1,'GROUP_END'))['outcome']=='ACCEPTED'
    assert runtime.uplink_groups.history[-1]['heartbeats']==3
    assert runtime.engine.state()['core']['commands_executed']==0
    assert len(runtime.engine.evidence(runtime.engine.state()['scenario_id'])['operations'])==2


@pytest.mark.parametrize('change',[{'count':0},{'count':17},{'index':1},{'index':True},
    {'timeout_seconds':0},{'timeout_seconds':float('inf')},{'id':'wrong-plan'}])
def test_invalid_group_has_no_command_effect(runtime,change):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner:
            body=member(runtime);body['uplink_group'].update(change)
            with pytest.raises((ValueError,EOFError,OSError)):send(owner,body)
    assert runtime.engine.state()['core']['loaded_commands_count']==0


@pytest.mark.parametrize('stage',['GROUP_HOLD','GROUP_END'])
def test_foreign_connection_cannot_control_owners_group(runtime,stage):
    with serving(TcServer(('127.0.0.1',0),runtime)) as address:
        with socket.create_connection(address,timeout=3) as owner,socket.create_connection(address,timeout=3) as foreign:
            assert send(owner,member(runtime))['outcome']=='ACCEPTED'
            with pytest.raises(PacketError,match='TCP closed before a complete Space Packet'):
                send(foreign,member(runtime,stage=stage))
            assert send(owner,member(runtime,1))['outcome']=='ACCEPTED'
            assert send(owner,member(runtime,1,'GROUP_END'))['outcome']=='ACCEPTED'


def test_group_metadata_is_bound_to_persisted_command_definition(runtime):
    first=member(runtime);runtime.engine.process_tc(first,encode_tc(first))
    changed=member(runtime,stage='RELEASE');changed.pop('uplink_group')
    with pytest.raises(ValueError,match='definition changed'):
        runtime.engine.process_tc(changed,encode_tc(changed))
    assert runtime.engine.state()['core']['commands_executed']==0
