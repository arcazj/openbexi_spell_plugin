"""Original native TC item expansion and interactive critical confirmation."""
# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.tc_item import TcItemClass
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import UnpackValue
from .connection import call


def lookup(name):
    row=UnpackValue(call('TM','DatabaseLookup',p.LookupRequest(name=name,type='TC',source='GENERIC')).lookup)
    if type(row) is not dict or row.get('name')!=name or row.get('kind') not in ('COMMAND','SEQUENCE'):
        raise DriverException('Invalid original command catalog response')
    return row


def create(interface,mnemonic,description=''):
    row=call('TC','CreateTcItem',p.TcItemDesc(mnemonic=mnemonic,description=description))
    item=TcItemClass(interface,row.mnemonic,row.description)
    if row.id=='SEQUENCE':
        definition=lookup(mnemonic)
        if definition['kind']!='SEQUENCE':
            raise DriverException('Command sequence identity differs')
        item._setElements([member['command'] for member in definition['members']])
    return item


def check_critical(items,config):
    critical=[]
    for item in items:
        settings=dict(config or {},**item.getConfig())
        enabled=settings.get('ConfirmCritical',False)
        if type(enabled) is not bool:
            raise DriverException('ConfirmCritical must be boolean')
        definition=lookup(item.name())
        if enabled and definition['critical']:
            critical.append(item.name())
    if critical:
        from spell.lang.functions import Prompt
        from spell.lang.constants import OK_CANCEL
        accepted=Prompt('Confirm critical command execution: '+', '.join(critical),
                        Type=OK_CANCEL,HandleError=False)
        if accepted is not True:
            raise DriverException('Critical command execution cancelled')


def send_sequence(interface,item,config):
    definition=lookup(item.name())
    if definition['kind']!='SEQUENCE' or item._getParams():
        raise DriverException('GENERIC sequence arguments must come from its catalog')
    members=definition['members']
    if item.getElements()!=[item.name()]+[str(index)+'@'+row['command'] for index,row in enumerate(members)]:
        raise DriverException('Native sequence elements differ from the authoritative catalog')
    settings=dict(config or {},**item.getConfig())
    children=[]
    for row in members:
        child=create(interface,row['command'])
        child.setConfig(dict(settings,**row['modifiers']))
        for name,value in row['args'].items():child[name]=[value]
        # Validate every member's native representation before the first write.
        from .tc import descriptor
        descriptor(child,settings)
        children.append(child)
    for index,child in enumerate(children):
        success=interface._sendCommand(child,settings)
        element=item.getElements()[index+1]
        stage,status=child.getExecutionStageStatus()
        item._setExecutionStageStatus(stage,status,elementId=element)
        item._setCompleted(success,elementId=element)
        if not success:
            item._setExecutionStageStatus('DSS_REJECTED','FAILED')
            item._setCompleted(False)
            return False
    load_only=settings.get('LoadOnly',False)
    item._setExecutionStageStatus('LOADING' if load_only else 'ONBOARD_EXECUTION','LOADED' if load_only else 'SUCCEEDED')
    item._setCompleted(True)
    return True
