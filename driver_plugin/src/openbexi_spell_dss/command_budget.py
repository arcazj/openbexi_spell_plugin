"""Conservative finite RPC envelope for validated per-command scheduling bounds.

Scheduling follows simulator UTC, which may differ from host wall time. The
wire envelope therefore uses the one-day scheduling horizon rather than
subtracting host time from a spacecraft timestamp. Execution enforces the
actual, shorter deadline and live authority independently.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
from google.protobuf import message_factory
from .codec import unpack
from .stubs import SPELLDriver_pb2 as p


def command_budget(family, method, request):
    if (family, method) not in {('TC','SendCommand'), ('TC','SendList'),
                               ('TC','SendBlock'), ('PCS','SendPtcCommand'), ('PCS','SendPtcList')}:
        return 30
    def settings(message):
        value = unpack(message) if message.type_url else {}
        if type(value) is not dict:
            raise ValueError('Command configuration must be a dictionary')
        return value
    common = settings(request.config)
    rows = list(request.commands) if 'commands' in request.DESCRIPTOR.fields_by_name else [request]
    if not 1 <= len(rows) <= 16:
        raise ValueError('TC list size outside bounds')
    total = 0
    for row in rows:
        config = dict(common, **settings(row.config))
        timeout, delay = config.get('Timeout',5), config.get('SendDelay',0)
        for value, maximum in ((timeout,3600), (delay,86400)):
            if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError('Invalid command deadline')
        if timeout == 0:
            raise ValueError('Invalid command deadline')
        for key in ('Time','ReleaseTime'):
            if key in config and (type(config[key]) not in (int,float) or not math.isfinite(config[key])
                                  or not 0 <= config[key] <= (1<<63)/1e9-1):
                raise ValueError('Command absolute time must be normalized')
        total += timeout + delay + (86400 if 'Time' in config or 'ReleaseTime' in config else 0)
    return max(30,total)


def relay_budget(path, raw):
    service_name, method_name = path.rsplit('/',2)[1:]
    service = p.DESCRIPTOR.services_by_name.get(service_name.removeprefix('spell.driver.'))
    method = service.methods_by_name.get(method_name) if service else None
    if method is None:
        raise ValueError('Unknown original RPC method')
    request = message_factory.GetMessageClass(method.input_type).FromString(raw)
    family = service.name.removeprefix('SPELLDriverInterface').removeprefix('_')
    return command_budget(family,method_name,request)
