"""One encoded TRANSPORT frame, with distinct member loading/execution receipts."""
# SPDX-License-Identifier: GPL-3.0-or-later
import time

from .command_groups import GroupExecution
from .journal import UncertainEffect


class BlockExecution(GroupExecution):
    def wire(self,*args,**kwargs):
        # The one shared frame is admitted atomically by the simulator. Later
        # receipt queries can reconnect after any ground/onboard wait.
        try:return super().wire(*args,**kwargs)
        finally:
            if self.connection is not None:
                self.connection.close()
                self.connection=None

    def execute(self,commands,identity,operation,check):
        if self.sent:raise ValueError('A blocked execution cannot be replayed')
        if not 1<=len(commands)<=16:raise ValueError('Block size outside bounds')
        self.validate(commands)
        budget=max(30,sum(command.timeout+command.send_delay+
            (86400 if command.execution_time is not None or command.release_time is not None else 0) for command in commands))
        outer=time.monotonic()+budget
        members=[self.prepare_member(command,identity,operation,i,len(commands),budget,outer)
                 for i,command in enumerate(commands)]
        due=max(member.due for member in members)
        now=self.utc_ns(self.state())
        for member,command in zip(members,commands):
            member.base.pop('uplink_group')
            complete=max(due,member.execution if member.execution is not None and not member.load_only else due)
            member.deadline=min(outer,time.monotonic()+max(0,complete-now)/1e9+command.timeout)
        frame=dict(members[0].base,element_id='block-frame',stage='TRANSPORT')
        frame.pop('execution_time_unix_ns',None);frame.pop('additional_info',None)
        frame['elements']=[{key:value for key,value in member.base.items() if key in
            {'element_id','command_name','arguments','command_digest','execution_time_unix_ns','additional_info'}}
            for member in members]
        self.member_results=[dict(index=i,name=command.name,state='NOT_SENT',receipts=[]) for i,command in enumerate(commands)]
        pending=[]

        def stage(member,name,expected):
            before=len(self.receipts)
            passed=self.wire(dict(member.base,stage=name),member.deadline,check,expected)
            row=self.member_results[member.index]
            row['receipts'].extend(self.receipts[before:])
            row['state']=expected if passed else self.receipts[-1]['outcome']
            return passed

        try:
            self.wait_due(due,min(member.deadline for member in members),check)
            if not self.wire(frame,min(member.deadline for member in members),check,'ACCEPTED'):
                return False,self.receipts
            # This DSS profile loads all shared-frame elements in one engine
            # transaction, independently of subsequent loading observations.
            for row in self.member_results:
                row.update(state='LOADED',shared_transport=self.receipts[0])
            for member in members:
                if not stage(member,'LOADING','LOADED'):return False,self.receipts
                if member.load_only:continue
                if not stage(member,'RELEASE','RELEASED') or not stage(member,'ACKNOWLEDGEMENT','ACKNOWLEDGED'):
                    return False,self.receipts
                if member.execution is not None and member.execution>self.utc_ns(self.state()):
                    pending.append(member)
                elif not stage(member,'ONBOARD_EXECUTION','SUCCEEDED'):
                    return False,self.receipts
            for member in pending:
                self.wait_due(member.execution,member.deadline,check)
                if not stage(member,'ONBOARD_EXECUTION','SUCCEEDED'):return False,self.receipts
            return True,self.receipts
        except BaseException as error:
            if self.sent:
                raise UncertainEffect('Blocked command may have taken effect; no automatic replay') from error
            raise
