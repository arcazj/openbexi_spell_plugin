"""Connection-owned uplink groups; competing sources receive a definitive busy ACK.

The runtime's admission lock protects this state together with engine admission.
A lost socket or expired finite deadline releases the reservation. Resumption
never reacquires a partially sent group: the next owner must begin at member 0.
"""
from collections import deque
import hashlib
import math
import time

from .catalog import canonical

MAX_GROUP_SECONDS = 16 * (2 * 86400 + 3600)
CONTROLS = {'GROUP_HOLD','GROUP_END'}


class UplinkGroups:
    def __init__(self):
        self.owner = None
        self.group = None
        self.history = deque(maxlen=128)

    @staticmethod
    def descriptor(body):
        group=body.get('uplink_group')
        if group is None:return None
        if type(group) is not dict or set(group)!={'id','index','count','timeout_seconds'}:
            raise ValueError('Uplink group schema differs')
        if (type(group['id']) is not str or group['id']!=body.get('plan_id')
                or not 1<=len(group['id'])<=256 or type(group['index']) is not int
                or type(group['count']) is not int or not 1<=group['count']<=16
                or not 0<=group['index']<group['count']):
            raise ValueError('Uplink group identity/member bounds differ')
        duration=group['timeout_seconds']
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=MAX_GROUP_SECONDS:
            raise ValueError('Uplink group deadline exceeds bounds')
        return group

    @staticmethod
    def binding(body):
        return tuple(body[key] for key in ('scenario_id','satellite_epoch','procedure_id','execution_id','plan_id'))

    def close(self,owner,*,reason='DISCONNECTED'):
        if self.owner is not None and self.owner is owner:
            self.history.append(dict(self.group,ended=time.monotonic(),reason=reason))
            self.owner,self.group=None,None

    def before(self,owner,body):
        group=self.descriptor(body)
        if self.owner is not None and time.monotonic()>=self.group['deadline']:
            self.close(self.owner,reason='EXPIRED')
        control=body.get('stage') in CONTROLS
        if self.owner is not None:
            if self.owner is not owner:
                if control:raise ValueError('Uplink control is not owned by this connection')
                return 'BUSY'
            current=self.group
            if (group is None or self.binding(body)!=current['binding'] or group['id']!=current['id']
                    or group['count']!=current['count'] or group['timeout_seconds']!=current['timeout_seconds']):
                raise ValueError('Uplink group binding changed')
            if body.get('stage')=='TRANSPORT':
                repeated=(group['index']<=current['index'] and
                    hashlib.sha256(canonical(body)).hexdigest()==current['transports'][group['index']])
                valid_index=group['index']==current['index']+1 or repeated
            else:
                valid_index=group['index']==current['index'] if control else group['index']<=current['index']
            if not valid_index:
                raise ValueError('Uplink group member order changed')
            if control:
                if body['stage']=='GROUP_END' and current['index']!=current['count']-1:
                    raise ValueError('Cannot finish an incomplete uplink group')
                return body['stage']
        elif control:
            raise ValueError('Uplink control has no live reservation')
        elif group is not None and (group['index']!=0 or body.get('stage')!='TRANSPORT'):
            raise ValueError('Uplink group must start at its first transport frame')
        return 'ADMIT'

    def accepted(self,owner,body,answer):
        group=body.get('uplink_group')
        if group is None:return
        if body['stage']=='TRANSPORT' and answer['outcome']=='ACCEPTED':
            if self.owner is None:
                self.owner=owner
                self.group=dict(id=group['id'],count=group['count'],index=0,
                    timeout_seconds=group['timeout_seconds'],binding=self.binding(body),
                    deadline=time.monotonic()+group['timeout_seconds'],heartbeats=0,
                    frame_chain='0'*64,frames=0,transports=[])
            else:self.group['index']=max(self.group['index'],group['index'])
            if len(self.group['transports'])==group['index']:
                self.group['transports'].append(hashlib.sha256(canonical(body)).hexdigest())
        if self.owner is owner:
            self.group['frame_chain']=hashlib.sha256(bytes.fromhex(self.group['frame_chain'])+canonical(body)).hexdigest()
            self.group['frames']+=1

    def control(self,owner,body):
        action=self.before(owner,body)
        if action not in CONTROLS:raise ValueError('Expected an uplink control')
        result=dict(schema_version='openbexi.dss.uplink-group-ack/1',stage=action,
            group_id=self.group['id'],index=self.group['index'],count=self.group['count'],outcome='ACCEPTED')
        if action=='GROUP_END':self.close(owner,reason='COMPLETED')
        else:self.group['heartbeats']+=1
        return result
