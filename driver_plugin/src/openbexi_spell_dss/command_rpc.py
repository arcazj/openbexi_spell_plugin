"""Original TC messages translated into individually receipted command plans."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from google.protobuf.wrappers_pb2 import BoolValue
from .codec import unpack
from .command_execution import CommandExecution, plan


def options(message):
    value = unpack(message) if message.type_url else {}
    if type(value) is not dict:
        raise ValueError('Command configuration must be a dictionary')
    return value


def prepare(dispatcher, method, request, identity, request_id, check):
    if method == 'SendBlock':
        raise NotImplementedError('Atomic command block protocol is not qualified yet')
    common = options(request.config)
    rows = [request] if method == 'SendCommand' else list(request.commands)
    if not 1 <= len(rows) <= 16:
        raise ValueError('TC list size outside bounds')
    commands = []
    for row in rows:
        settings = dict(common, **options(row.config))
        critical = settings.pop('ConfirmCritical', True)
        if type(critical) is not bool:
            raise ValueError('ConfirmCritical must be boolean')
        name = row.command.mnemonic
        if dispatcher.transport.database.command(name)['critical'] and critical:
            raise PermissionError('Critical TC requires native confirmation or explicit ConfirmCritical=False')
        arguments = unpack(row.args) if row.args.type_url else []
        commands.append(plan(dispatcher.transport, name, arguments, settings))
    executor = CommandExecution(dispatcher.transport)

    def permitted():
        check()
        if not dispatcher.ground.state()['links']['TC']:
            raise PermissionError('Simulator TC link is disabled')

    def send():
        for index, command in enumerate(commands):
            operation = hashlib.sha256((identity['session'] + identity['procedure'] + request_id + ':' + str(index)).encode()).hexdigest()
            success, receipts = executor.execute(command, identity, operation, permitted)
            if not success:
                return BoolValue(value=False)
        return BoolValue(value=True)
    send.validate = lambda: executor.validate(commands)
    return send
