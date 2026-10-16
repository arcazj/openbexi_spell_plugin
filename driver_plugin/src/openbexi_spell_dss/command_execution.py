"""Individual GENERIC command stages, ground delays and onboard timetags.

The caller owns request journaling and supplies a live authority check.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
import hashlib
import math
import socket
import time

from dss.catalog import canonical
from dss.packets import decode_packet, decode_tm, encode_tc, recv_packet
from .journal import UncertainEffect


@dataclass(frozen=True)
class Plan:
    name: str
    arguments: list
    timeout: float = 5
    execution_time: float | None = None
    release_time: float | None = None
    send_delay: float = 0
    load_only: bool = False
    additional_info: dict | None = None


def number(value, name, lower, upper, *, positive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or not lower <= value <= upper or (positive and value==0):
        raise ValueError('Invalid command '+name)
    return value


def plan(transport, name, arguments, options):
    if type(options) is not dict or set(options)-{'Timeout','Time','ReleaseTime','SendDelay','LoadOnly','addInfo'}:
        raise ValueError('Unsupported individual command modifier')
    transport.database.command(name)
    converted = transport.arguments(name,arguments)
    timeout = number(options.get('Timeout',5),'timeout',0,3600,positive=True)
    delay = number(options.get('SendDelay',0),'send delay',0,86400)
    load = options.get('LoadOnly',False)
    if type(load) is not bool:
        raise ValueError('LoadOnly must be boolean')
    times = [options.get(key) for key in ('Time','ReleaseTime')]
    for key,value in zip(('Time','ReleaseTime'),times):
        if key in options:
            number(value,'absolute time',0,(1<<63)/1e9-1)
    info = options.get('addInfo')
    if 'addInfo' in options and (type(info) is not dict or len(canonical(info))>8192):
        raise ValueError('Command additional information must be a bounded dictionary')
    return Plan(name,converted,timeout,*times,delay,load,info)


class CommandExecution:
    def __init__(self, transport):
        self.transport = transport

    def state(self):
        if self.transport.stop.is_set():
            raise RuntimeError('DSS transport is closed')
        state = self.transport.get('state')
        if state['epoch']!=self.transport.epoch or state['scenario_id']!=self.transport.scenario:
            raise ValueError('DSS epoch changed; explicit rebinding required')
        return state

    @staticmethod
    def utc_ns(state):
        return state['clock_epoch_unix_ns']+state['core']['sim_time_ns']

    def wait_until(self, target, deadline, check):
        while True:
            check()
            if self.utc_ns(self.state())>=target:
                return
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise TimeoutError('Scheduled command did not become due before deadline')
            if self.transport.stop.wait(min(.025,remaining)):
                raise RuntimeError('DSS transport closed')

    def validate(self, commands):
        now = self.utc_ns(self.state())
        for command in commands:
            for target in (command.execution_time,command.release_time):
                if target is not None and round(target*1e9)>now+86_400_000_000_000:
                    raise ValueError('Scheduled command exceeds one-day horizon')

    def execute(self, command, identity, operation, check):
        state=self.state();now=self.utc_ns(state)
        execution_time=None if command.execution_time is None else round(command.execution_time*1e9)
        release_time=None if command.release_time is None else round(command.release_time*1e9)
        for target in (execution_time,release_time):
            if target is not None and target>now+86_400_000_000_000:
                raise ValueError('Scheduled command exceeds one-day horizon')
        ground_due=max(now,release_time if release_time is not None else now)+round(command.send_delay*1e9)
        completion_due=max(ground_due,execution_time if execution_time is not None and not command.load_only else ground_due)
        deadline=time.monotonic()+max(0,completion_due-now)/1e9+command.timeout
        # A request is already in the caller's GCS journal while this delay runs.
        # No spacecraft command frame is sent before ground release becomes due.
        self.wait_until(ground_due,deadline,check)
        digest=hashlib.sha256(canonical(dict(command_name=command.name,arguments=command.arguments,
                                             database_digest=self.transport.database.digest))).hexdigest()
        base=dict(schema_version='openbexi.dss.tc/1',satellite_id='GENERIC',
            database_revision=self.transport.database.revision,database_digest=self.transport.database.digest,
            satellite_epoch=self.transport.epoch,scenario_id=self.transport.scenario,
            operation_id=operation,procedure_id=identity['definition'],execution_id=identity['procedure'],
            plan_id=operation,element_id='command-1',command_name=command.name,
            arguments=command.arguments,command_digest=digest)
        if execution_time is not None:
            base['execution_time_unix_ns']=execution_time
        if command.additional_info is not None:
            base['additional_info']=command.additional_info
        stages=[('TRANSPORT','ACCEPTED'),('LOADING','LOADED')]
        if not command.load_only:
            stages += [('RELEASE','RELEASED'),('ACKNOWLEDGEMENT','ACKNOWLEDGED'),('ONBOARD_EXECUTION','SUCCEEDED')]
        receipts=[];sent=False
        try:
            # Reconnect before each stage: GCS/onboard waits can exceed the
            # server's idle-connection bound. Reconnection never repeats a stage.
            for sequence,(stage,expected) in enumerate(stages):
                if stage=='ONBOARD_EXECUTION' and execution_time is not None:
                    self.wait_until(execution_time,deadline,check)
                check()
                self.state()
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise TimeoutError('Command execution deadline expired')
                with socket.create_connection(self.transport.tc_address,timeout=min(2,remaining)) as connection:
                    check()  # Authority is rechecked after connection, before every write.
                    remaining=deadline-time.monotonic()
                    if remaining<=0:
                        raise TimeoutError('Command execution deadline expired')
                    connection.settimeout(min(3,remaining))
                    sent=True
                    connection.sendall(encode_tc(dict(base,stage=stage),sequence))
                    raw=recv_packet(connection,timeout=min(3,max(.001,deadline-time.monotonic())))
                packet=decode_packet(raw);answer=decode_tm(raw)
                required=('satellite_id','database_revision','database_digest','satellite_epoch','scenario_id',
                          'operation_id','procedure_id','execution_id','plan_id','element_id','command_name','command_digest')
                if (packet.apid!=102 or answer.get('schema_version')!='openbexi.dss.ack/1'
                        or any(answer.get(key)!=base[key] for key in required) or answer.get('stage')!=stage):
                    raise ValueError('DSS acknowledgement binding differs')
                receipts.append(answer)
                if answer.get('outcome')!=expected:
                    if answer.get('outcome') in {'MISSING','UNCERTAIN','INDETERMINATE','PENDING'}:
                        raise UncertainEffect('DSS command outcome requires reconciliation')
                    return False,receipts
            return True,receipts
        except BaseException as error:
            if sent:
                raise UncertainEffect('DSS command may have taken effect; no automatic replay') from error
            raise
