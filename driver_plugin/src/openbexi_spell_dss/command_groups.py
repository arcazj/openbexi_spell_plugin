"""Grouped binary uplinks with per-member receipts and deferred onboard checks."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import socket
import time
from types import SimpleNamespace

from dss.catalog import canonical
from dss.packets import decode_packet,decode_tm,encode_tc,recv_packet
from .command_execution import CommandExecution
from .journal import UncertainEffect


class GroupExecution(CommandExecution):
    def __init__(self,transport):
        super().__init__(transport)
        self.connection=None
        self.sent=False
        self.last_traffic=0
        self.control_body=None
        self.receipts=[]
        self.control_receipts=[]
        self.member_results=[]
        self.attempted_elements=set()

    def wire(self,body,deadline,check,expected,*,control=False):
        check();self.state()
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Grouped command deadline expired')
        if self.connection is None:
            self.connection=socket.create_connection(self.transport.tc_address,timeout=min(2,remaining))
            check();self.state()
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Grouped command deadline expired')
        self.connection.settimeout(min(3,remaining))
        encoded=encode_tc(body,(len(self.receipts)+len(self.control_receipts))&0x3fff)
        if body['stage']=='TRANSPORT':
            self.attempted_elements.update(element['element_id'] for element in body.get('elements',[body]))
        self.sent=True
        self.connection.sendall(encoded)
        raw=recv_packet(self.connection,timeout=min(3,max(.001,deadline-time.monotonic())))
        answer=decode_tm(raw)
        if decode_packet(raw).apid!=102:raise ValueError('Grouped ACK APID differs')
        if control:
            group=body['uplink_group']
            if (answer.get('schema_version')!='openbexi.dss.uplink-group-ack/1'
                    or answer.get('stage')!=body['stage'] or answer.get('group_id')!=group['id']
                    or answer.get('index')!=group['index'] or answer.get('count')!=group['count']):
                raise ValueError('Uplink control acknowledgement binding differs')
            self.control_receipts.append(answer)
        else:
            keys=('satellite_id','database_revision','database_digest','satellite_epoch','scenario_id',
                  'operation_id','procedure_id','execution_id','plan_id','element_id','command_name','command_digest','stage')
            if answer.get('schema_version')!='openbexi.dss.ack/1' or any(answer.get(k)!=body[k] for k in keys):
                raise ValueError('Grouped command acknowledgement binding differs')
            self.receipts.append(answer)
            if body['stage']=='TRANSPORT' and answer.get('outcome')=='ACCEPTED' and 'uplink_group' in body:
                self.control_body=dict(body)
        self.last_traffic=time.monotonic()
        if answer.get('outcome')!=expected:
            if answer.get('outcome') in {'MISSING','UNCERTAIN','INDETERMINATE','PENDING'}:
                raise UncertainEffect('Grouped command requires reconciliation')
            return False
        return True

    def wait_due(self,target,deadline,check):
        while True:
            check()
            if self.utc_ns(self.state())>=target:return
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Grouped command did not become due')
            if self.control_body is not None and time.monotonic()-self.last_traffic>=1:
                if not self.wire(dict(self.control_body,stage='GROUP_HOLD'),deadline,check,'ACCEPTED',control=True):
                    raise UncertainEffect('Uplink group heartbeat was rejected')
            if self.transport.stop.wait(min(.025,remaining)):
                raise RuntimeError('DSS transport closed')

    def prepare_member(self,command,identity,operation,index,count,budget,outer_deadline):
        state=self.state();now=self.utc_ns(state)
        execution=None if command.execution_time is None else round(command.execution_time*1e9)
        release=None if command.release_time is None else round(command.release_time*1e9)
        for target in (execution,release):
            if target is not None and target>now+86_400_000_000_000:
                raise ValueError('Grouped command exceeds one-day scheduling horizon')
        due=max(now,release if release is not None else now)+round(command.send_delay*1e9)
        complete=max(due,execution if execution is not None and not command.load_only else due)
        deadline=min(outer_deadline,time.monotonic()+max(0,complete-now)/1e9+command.timeout)
        digest=hashlib.sha256(canonical(dict(command_name=command.name,arguments=command.arguments,
                                           database_digest=self.transport.database.digest))).hexdigest()
        base=dict(schema_version='openbexi.dss.tc/1',satellite_id='GENERIC',
            database_revision=self.transport.database.revision,database_digest=self.transport.database.digest,
            satellite_epoch=self.transport.epoch,scenario_id=self.transport.scenario,
            operation_id=operation,procedure_id=identity['definition'],execution_id=identity['procedure'],
            plan_id=operation,element_id='command-'+str(index),command_name=command.name,
            arguments=command.arguments,command_digest=digest,
            uplink_group=dict(id=operation,index=index,count=count,timeout_seconds=budget))
        if execution is not None:base['execution_time_unix_ns']=execution
        if command.additional_info is not None:base['additional_info']=command.additional_info
        return SimpleNamespace(base=base,due=due,execution=execution,deadline=deadline,load_only=command.load_only,index=index)

    def preflight(self,commands,identity,operation):
        self.validate(commands)
        if not 1<=len(commands)<=16:raise ValueError('Group size outside bounds')
        if any(type(identity[key]) is not str or not 1<=len(identity[key])<=256 for key in ('definition','procedure')):
            raise ValueError('Binary command identity exceeds bounds')
        budget=max(30,sum(command.timeout+command.send_delay+
            (86400 if command.execution_time is not None or command.release_time is not None else 0) for command in commands))
        members=[self.prepare_member(command,identity,operation,i,len(commands),budget,time.monotonic()+budget)
                 for i,command in enumerate(commands)]
        for member in members:encode_tc(dict(member.base,stage='TRANSPORT'))
        return members

    def execute(self,commands,identity,operation,check):
        if self.sent or self.connection is not None:
            raise ValueError('A grouped execution cannot be replayed')
        if not 1<=len(commands)<=16:raise ValueError('Group size outside bounds')
        self.validate(commands)
        budget=max(30,sum(command.timeout+command.send_delay+
            (86400 if command.execution_time is not None or command.release_time is not None else 0) for command in commands))
        outer_deadline=time.monotonic()+budget
        pending=[]
        self.member_results=[dict(index=i,name=command.name,state='NOT_SENT',receipts=[]) for i,command in enumerate(commands)]

        def stage(member,name,expected):
            before=len(self.receipts)
            passed=self.wire(dict(member.base,stage=name),member.deadline,check,expected)
            row=self.member_results[member.index]
            row['receipts'].extend(self.receipts[before:])
            row['state']=expected if passed else self.receipts[-1]['outcome']
            return passed

        try:
            for index,command in enumerate(commands):
                member=self.prepare_member(command,identity,operation,index,len(commands),budget,outer_deadline)
                self.wait_due(member.due,member.deadline,check)
                if not stage(member,'TRANSPORT','ACCEPTED') or not stage(member,'LOADING','LOADED'):
                    return False,self.receipts
                if member.load_only:continue
                if not stage(member,'RELEASE','RELEASED') or not stage(member,'ACKNOWLEDGEMENT','ACKNOWLEDGED'):
                    return False,self.receipts
                if member.execution is not None and member.execution>self.utc_ns(self.state()):
                    pending.append(member)
                elif not stage(member,'ONBOARD_EXECUTION','SUCCEEDED'):
                    return False,self.receipts
            for member in pending:
                self.wait_due(member.execution,member.deadline,check)
                if not stage(member,'ONBOARD_EXECUTION','SUCCEEDED'):
                    return False,self.receipts
            if not self.wire(dict(self.control_body,stage='GROUP_END'),outer_deadline,check,'ACCEPTED',control=True):
                raise UncertainEffect('Uplink group completion acknowledgement rejected')
            return True,self.receipts
        except BaseException as error:
            if self.sent:
                raise UncertainEffect('Grouped command may have taken effect; no automatic replay') from error
            raise
        finally:
            if self.connection is not None:
                self.connection.close()
                self.connection=None
