"""Group/Block planning and durable per-member results over original RPC types."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from google.protobuf.wrappers_pb2 import BoolValue

from .command_rpc import options,prepare as individual_prepare
from .command_execution import plan
from .command_groups import GroupExecution
from .command_blocks import BlockExecution
from .command_results import Results,KEY,observation
from .codec import unpack


def prepare(dispatcher,method,request,identity,request_id,check):
    common=options(request.config)
    for key in ('Group','Block'):
        if key in common and type(common[key]) is not bool:
            raise ValueError(key+' must be boolean')
    blocked=method=='SendBlock' or common.get('Block',False)
    grouped=blocked or common.get('Group',False)
    if not grouped:
        return individual_prepare(dispatcher,method,request,identity,request_id,check)
    rows=[request] if method=='SendCommand' else list(request.commands)
    if not 1<=len(rows)<=16:raise ValueError('Command group size outside bounds')
    token=common.get(KEY)
    store=Results(dispatcher.journal,dispatcher.ground.namespace)
    store.key(identity,token)
    commands=[]
    for row in rows:
        settings=dict(common,**options(row.config))
        if settings.pop(KEY,None)!=token:raise ValueError('Command group token differs between members')
        for key in ('Group','Block'):
            value=settings.pop(key,False)
            if type(value) is not bool:raise ValueError(key+' must be boolean')
            if value and key=='Block' and not blocked:
                raise ValueError('Per-member Block cannot replace a group transport')
        critical=settings.pop('ConfirmCritical',True)
        if type(critical) is not bool:raise ValueError('ConfirmCritical must be boolean')
        name=row.command.mnemonic
        if dispatcher.transport.database.command(name)['critical'] and critical:
            raise PermissionError('Critical group member requires native confirmation or explicit False')
        arguments=unpack(row.args) if row.args.type_url else []
        commands.append(plan(dispatcher.transport,name,arguments,settings))
    operation=hashlib.sha256((identity['session']+identity['procedure']+request_id+':group').encode()).hexdigest()
    executor=(BlockExecution if blocked else GroupExecution)(dispatcher.transport)

    def permitted():
        check()
        if not dispatcher.ground.state()['links']['TC']:
            raise PermissionError('Simulator TC link is disabled')

    def validate():
        store.validate(identity,token,request_id)
        executor.preflight(commands,identity,operation)

    def send():
        try:
            success,receipts=executor.execute(commands,identity,operation,permitted)
        except BaseException:
            store.save(identity,token,request_id,observation(executor,commands,token,operation,False,True))
            raise
        store.save(identity,token,request_id,observation(executor,commands,token,operation,success,False))
        return BoolValue(value=success)
    send.validate=validate
    return send
