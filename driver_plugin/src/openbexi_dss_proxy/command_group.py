"""Native Group/Block calls with ordered results and truthful partial status."""
# SPDX-License-Identifier: GPL-3.0-or-later
import uuid
from google.protobuf.message_factory import GetMessageClass
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue,UnpackValue

from .connection import call
from .command_catalog import lookup,create
from .command_settings import normalize

KEY='_OpenBEXICommandGroup'
SOURCE='OPENBEXI_COMMAND_RESULTS'


def settings(item,config):
    local = item.getConfig()
    # TcInterface chooses its block path from the call configuration before
    # applying item overrides. Validate both sources so an item default cannot
    # hide a malformed flag that already selected a different transport path.
    for options in (config or {}, local):
        for name in ('Block', 'Group'):
            if name in options and type(options[name]) is not bool:
                raise DriverException(name+' must be boolean')
    return dict(config or {},**local)


def requested(items,config):
    values=[settings(item,config) for item in items]
    for value in values:normalize(value)
    return any(value.get('Group') or value.get('Block') for value in values)


def send(interface,items,config,*,blocked=False):
    from .tc import descriptor
    parents=[];flat=[];descriptors=[]
    for item in items:
        options=settings(item,config)
        normalize(options)  # Reject user-supplied private group tokens.
        children=[]
        if item.isComplex():
            definition=lookup(item.name())
            if definition['kind']!='SEQUENCE' or item._getParams():
                raise DriverException('Invalid catalog sequence group member')
            expected=[item.name()]+[str(i)+'@'+r['command'] for i,r in enumerate(definition['members'])]
            if item.getElements()!=expected:raise DriverException('Native sequence elements differ')
            for row in definition['members']:
                child=create(interface,row['command'])
                child.setConfig(dict(options,**row['modifiers']))
                for name,value in row['args'].items():child[name]=[value]
                children.append(child)
        else:children=[item]
        indices=[]
        for child in children:
            desc=descriptor(child,options)
            wire=UnpackValue(desc.config)
            wire['ConfirmCritical']=False  # Native TcInterface hook already consumed this policy.
            desc.config.CopyFrom(PackValue(wire))
            indices.append(len(flat));flat.append(child);descriptors.append(desc)
        parents.append((item,indices))
    if not 1<=len(flat)<=16:raise DriverException('Expanded group exceeds sixteen command members')
    token=uuid.uuid4().hex
    method='SendBlock' if blocked else 'SendList'
    shape=p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TC'].methods_by_name[method].input_type
    request=GetMessageClass(shape)(commands=descriptors,config=PackValue({KEY:token,'Block' if blocked else 'Group':True}))
    success=False;error=None
    try:success=call('TC',method,request).value
    except DriverException as failure:error=failure
    try:
        result=UnpackValue(call('TM','DatabaseLookup',p.LookupRequest(name=token,type='TC',source=SOURCE)).lookup)
    except DriverException:
        if error is not None:raise error
        raise
    if (result.get('schema')!='openbexi.command-group-result/1' or result.get('token')!=token
            or len(result.get('members',[]))!=len(flat)
            or (error is None and (result['outcome']=='SUCCEEDED')!=success)):
        raise DriverException('Command group result binding differs')
    completed=[]
    for index,(item,row) in enumerate(zip(flat,result['members'])):
        if row['index']!=index or row['name']!=item.name():
            raise DriverException('Command group member order differs')
        state=row['state'];done=None
        if row['uncertain']:
            stage,status='OUTCOME_UNCERTAIN','UNKNOWN'
        elif state=='SUCCEEDED':
            stage,status,done='ONBOARD_EXECUTION','SUCCEEDED',True
        elif state=='LOADED' and row['load_only']:
            stage,status,done='LOADING','LOADED',True
        elif state in ('FAILED','REJECTED','NACKED'):
            stage=row['stages'][-1][0] if row['stages'] else 'DSS_REJECTED'
            status,done=state,False
        else:
            stage=row['stages'][-1][0] if row['stages'] else 'LOADING' if state=='LOADED' else 'NOT_SENT'
            status=state
        item._setExecutionStageStatus(stage,status)
        if done is not None:item._setCompleted(done)
        completed.append((stage,status,done))
    for parent,indices in parents:
        if not parent.isComplex():continue
        for offset,index in enumerate(indices):
            stage,status,done=completed[index]
            element=parent.getElements()[offset+1]
            parent._setExecutionStageStatus(stage,status,elementId=element)
            if done is not None:parent._setCompleted(done,elementId=element)
        outcomes=[completed[i][2] for i in indices]
        if all(value is True for value in outcomes):
            stages={completed[i][0] for i in indices}
            parent._setExecutionStageStatus(next(iter(stages)) if len(stages)==1 else 'COMPLETED','SUCCEEDED')
            parent._setCompleted(True)
        elif any(value is False for value in outcomes):
            parent._setExecutionStageStatus('GROUP_STOPPED','FAILED');parent._setCompleted(False)
        else:parent._setExecutionStageStatus('GROUP_INCOMPLETE','UNKNOWN')
    if error is not None:raise error
    return success
