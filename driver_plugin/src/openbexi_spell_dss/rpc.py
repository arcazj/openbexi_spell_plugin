"""Original-schema dispatch; authority comes from the owning service, never RPC data."""
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone
import hashlib
from google.protobuf import message_factory
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import BoolValue,StringValue
import math
import time
from .codec import pack, unpack
from .journal import authority
from .stubs import SPELLDriver_pb2 as p

PREFIX = 'spell.driver.SPELLDriverInterface'
READS = {
    '': {'GetDriverInfo', 'Ping'},
    'TM': {'DatabaseLookup','GetLimits','IsAlarmed','RefreshItem','CreateTmItem'},
    'TC': {'CreateTcItem'},
    'PCS': {'CreatePtcItem','PCS_GetStatus','PCS_IsArqEnabled','PCS_IsVerifyModeEnabled','PCS_ReadyToCommand'},
    'MEM': {'MemoryLookup','DataObjectLookup','DataItemLookup','CompareImages'},
    'RSC': {'CheckLink','GetResource','GetResources','GetResourceStatus','IsResourceOK'},
    'TASK': {'CheckTask'},
    'RNG': {'GetBasebandConfig','GetAntennaNames','GetRangingPaths','GetBasebandNames','GetRangingStatus'},
    'USER': {'IsLoggedIn'}, 'TIME': {'GetUTC'}, 'EV': set(),
}


def method_descriptor(path):
    parts = path.split('/')
    if len(parts) != 3 or parts[0] or not parts[1].startswith(PREFIX):
        raise ValueError('Invalid original driver RPC path')
    service = p.DESCRIPTOR.services_by_name.get(parts[1].removeprefix('spell.driver.'))
    method = service.methods_by_name.get(parts[2]) if service else None
    if not method or method.client_streaming or method.server_streaming:
        raise ValueError('Unknown or unused streaming driver method')
    return method


def config(message):
    if not message.type_url:
        return {}
    value = unpack(message)
    if type(value) is not dict:
        raise ValueError('Driver configuration must be a dictionary')
    return value


class Dispatcher:
    def __init__(self, transport, journal, *, users=None):
        self.transport, self.journal = transport, journal
        from .ground import Ground
        self.ground = Ground(transport,journal,users)

    def dispatch(self, path, raw, identity, request_id, check):
        authority(identity)
        check()
        method = method_descriptor(path)
        if type(raw) is not bytes or len(raw) > 65536:
            raise ValueError('Driver RPC request exceeds bounds')
        message = message_factory.GetMessageClass(method.input_type).FromString(raw)
        family = method.containing_service.name.removeprefix('SPELLDriverInterface').removeprefix('_')
        effect = method.name not in READS[family]
        if effect and identity['mode'] == 'Monitoring':
            raise PermissionError('Monitoring is read-only')
        # Validate supported behavior BEFORE persisting an effect intent.
        action = self.prepare(family, method.name, message, identity, request_id, check)
        if effect:
            cached = self.journal.begin(identity, request_id, path, raw)
            if cached is not None:
                return cached
        self.ground.snapshot()  # Never mutate an obsolete simulator epoch.
        check()
        result = action()
        if result.DESCRIPTOR.full_name != method.output_type.full_name or result.ByteSize() > 65536:
            raise ValueError('Invalid original driver response')
        receipt = result.SerializeToString(deterministic=True)
        if effect:
            self.journal.finish(identity, request_id, receipt)
        return receipt

    def prepare(self, family, method, request, identity, request_id, check):
        database = self.transport.database
        if family == '' and method == 'Ping':
            return Empty
        if method in {'Setup','Cleanup','Interrupt','Close'}:
            raise NotImplementedError('Lifecycle is owned by the private worker, not by procedure RPC')
        if family == '' and method == 'GetDriverInfo':
            return lambda:p.DriverInfo(driverName='openbexi_dss', interfaces=[value.number for value in p.Interfaces.DriverInterface.DESCRIPTOR.values if value.name != 'CONFIG'])
        if family == 'EV' and method == 'RaiseEvent':
            settings = config(request.config)
            severity,scope = settings.get('Severity',8),settings.get('Scope',1)
            if (not 1 <= len(request.message) <= 8192 or set(settings)-{'Severity','Scope'}
                    or type(severity) is not int or severity not in {1,2,4,8}
                    or type(scope) is not int or scope not in {1,2,4}):
                raise ValueError('Invalid original event message/severity/scope')
            def record():
                self.journal.event(identity,request_id,request.message,severity,scope)
                return Empty()
            return record
        if family == 'TC' and method == 'CreateTcItem':
            item = database.command(request.mnemonic)
            return lambda:p.TcItemDesc(mnemonic=item['name'], description=item['effect'], id=str(item['command_code']))
        if family == 'TM' and method == 'CreateTmItem':
            item = database.item(request.mnemonic)
            return lambda:p.TmItemDesc(mnemonic=item['item_id'], description=item.get('description', item['item_id']), id=str(item['item_code']))
        if family == 'TM' and method == 'DatabaseLookup':
            if request.source not in {'', 'GENERIC'} or request.type not in {'TM','TC'}:
                raise ValueError('Unsupported database lookup source/type')
            item = database.item(request.name) if request.type == 'TM' else database.command(request.name)
            return lambda:p.LookupAnswer(lookup=pack(item))
        if family == 'TM' and method == 'RefreshItem':
            settings = config(request.config)
            if set(settings) - {'Wait','Timeout','ValueFormat'}:
                raise ValueError('Unsupported telemetry refresh modifier')
            if settings.get('ValueFormat','Eng format') not in {'Raw format','Eng format','Default format'}:
                raise ValueError('Invalid telemetry value format')
            database.item(request.item.mnemonic)
            def refresh():
                ground = self.ground.state()
                if not ground['links']['TM']:
                    raise ValueError('Simulator TM link is disabled')
                injected = ground['injections'].get(request.item.mnemonic)
                if injected:
                    if settings.get('Wait'):
                        raise ValueError('Fresh-source acquisition is unavailable while a ground injection is active')
                    return p.TmItemValue(item=request.item,validity=injected['valid'],engValue=pack(injected['eng']),
                                         rawValue=pack(injected['raw']),timestamp=injected['time'],config=request.config)
                sample = self.transport.sample(request.item.mnemonic, wait=settings.get('Wait',False), timeout=settings.get('Timeout',3))
                stamp = datetime.fromtimestamp(sample['acquired_at_unix_ns']/1e9, timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
                fresh = -1 <= (time.time_ns()-sample['acquired_at_unix_ns'])/1e9 <= 5
                return p.TmItemValue(item=request.item, validity=sample['validity'] == 'VALID' and sample['quality'] == 'GOOD' and fresh and sample['synchronization_state'] == 'COMPLETE',
                    engValue=pack(sample['engineering']['value']), rawValue=pack(sample['raw']['value']), timestamp=stamp, config=request.config)
            return refresh
        if family == 'TM' and method in {'SetLimits','GetLimits','IsAlarmed','InjectItem','RestoreNormalLimits'}:
            if method == 'RestoreNormalLimits':
                if config(request):
                    raise ValueError('Only restore-all ground limits is available')
                def restore():
                    self.ground.update(lambda s:s['limits'].clear())
                    return BoolValue(value=True)
                return restore
            name = request.item.mnemonic
            definition = database.item(name)
            if method == 'SetLimits':
                limits = unpack(request.set.limitset)
                if (type(limits) is not dict or set(limits) != {'LoRed','LoYel','HiYel','HiRed'}
                        or any(type(v) not in {int,float} or not math.isfinite(v) for v in limits.values())
                        or not limits['LoRed'] <= limits['LoYel'] <= limits['HiYel'] <= limits['HiRed']):
                    raise ValueError('This simulator profile requires four ordered numeric limits')
                def set_limits():
                    self.ground.update(lambda s:s['limits'].__setitem__(name,limits))
                    return BoolValue(value=True)
                return set_limits
            if config(request.config):
                raise ValueError('Unsupported ground telemetry modifier')
            if method == 'GetLimits':
                return lambda:p.LimitSet(limitset=pack(self.ground.state()['limits'].get(name,{})))
            if method == 'InjectItem':
                injected = dict(raw=unpack(request.rawValue),eng=unpack(request.engValue),valid=request.validity,time=request.timestamp)
                try:
                    datetime.strptime(injected['time'], '%Y-%m-%d %H:%M:%S.%f' if '.' in injected['time'] else '%Y-%m-%d %H:%M:%S')
                except ValueError as error:
                    raise ValueError('Ground injection requires an original UTC timestamp') from error
                raw,eng,kind = injected['raw'],injected['eng'],definition['raw_type']
                valid = ((kind == 'UINT64' and type(raw) is int and 0 <= raw < 2**64)
                    or (kind == 'INT64' and type(raw) is int and -2**63 <= raw < 2**63)
                    or (kind == 'BOOLEAN' and type(raw) is bool)
                    or (kind == 'STRING' and type(raw) is str))
                expected = raw * definition['engineering_scale'] if type(raw) is int else raw
                if not valid or type(eng) is not type(expected) or eng != expected:
                    raise ValueError('Injected raw/engineering values differ from catalog calibration')
                def inject():
                    self.ground.update(lambda s:s['injections'].__setitem__(name,injected))
                    return BoolValue(value=True)
                return inject
            def alarm():
                ground = self.ground.state()
                limits = ground['limits'].get(name)
                if not limits:
                    return BoolValue(value=False)
                reading = self.prepare('TM','RefreshItem',p.TmItemValue(item=request.item),identity,request_id,check)()
                if not reading.validity:
                    raise ValueError('Cannot evaluate alarms on invalid or stale telemetry')
                value = unpack(reading.engValue)
                if type(value) not in {int,float}:
                    raise ValueError('Numeric limits require numeric telemetry')
                return BoolValue(value=value < limits['LoYel'] or value > limits['HiYel'])
            return alarm
        if family == 'TC' and method in {'SendCommand','SendList','SendBlock'}:
            settings = config(request.config)
            if set(settings) - {'Timeout'}:
                raise ValueError('TC modifiers are not qualified in this bridge profile')
            commands = [request] if method == 'SendCommand' else list(request.commands)
            if not 1 <= len(commands) <= 16:
                raise ValueError('TC list size outside bounds')
            plans = []
            for command in commands:
                command_settings = dict(settings, **config(command.config))
                timeout = command_settings.get('Timeout',5)
                if set(command_settings) - {'Timeout'} or type(timeout) not in {int,float} or not 0 < timeout <= 30:
                    raise ValueError('TC modifiers are not qualified in this bridge profile')
                name = command.command.mnemonic
                if database.command(name)['critical']:
                    raise PermissionError('Critical TC requires a separately qualified confirmation contract')
                args = unpack(command.args) if command.args.type_url else []
                self.transport.arguments(name, args)
                plans.append((name, args, timeout))
            def send():
                deadline = time.monotonic() + 30
                for index, (name, args, timeout) in enumerate(plans):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Command group deadline expired; preceding receipts retained')
                    operation = hashlib.sha256((identity['session'] + identity['procedure'] + request_id + ':' + str(index)).encode()).hexdigest()
                    def permitted():
                        check()
                        if not self.ground.state()['links']['TC']:
                            raise PermissionError('Simulator TC link is disabled')
                    success, receipts = self.transport.command(name, args, identity, operation, permitted,timeout=min(timeout,remaining))
                    # DSS retains full stage receipts in its immutable evidence journal.
                    if not success:
                        return BoolValue(value=False)
                return BoolValue(value=True)
            return send
        if family == 'PCS':
            if method == 'CreatePtcItem':
                row = database.command(request.mnemonic)
                return lambda:p.PtcItemDesc(mnemonic=row['name'],description=row['effect'],id=str(row['command_code']))
            if method in {'PCS_GetStatus','PCS_IsArqEnabled','PCS_IsVerifyModeEnabled','PCS_ReadyToCommand','PCS_AbortPtc'}:
                if config(request):
                    raise ValueError('Unsupported GENERIC PCS modifier')
                if method == 'PCS_GetStatus':
                    return lambda:pack(dict(profile='GENERIC synchronous binary TC',ready=self.ground.state()['links']['TC']))
                if method == 'PCS_ReadyToCommand':
                    return lambda:StringValue(value='READY' if self.ground.state()['links']['TC'] else 'DISABLED')
                return lambda:BoolValue(value=method == 'PCS_IsVerifyModeEnabled')
            if method in {'SendPtcCommand','SendPtcList'}:
                rows = [request] if method == 'SendPtcCommand' else list(request.commands)
                if not 1 <= len(rows) <= 16:
                    raise ValueError('PCS list outside bounds')
                plans = []
                for index,row in enumerate(rows):
                    command = p.CommandDesc(command=p.TcItemDesc(mnemonic=row.command.mnemonic),args=row.args,config=row.config)
                    plans.append(self.prepare('TC','SendCommand',command,identity,
                        hashlib.sha256((request_id+':'+str(index)).encode()).hexdigest()[:32],check))
                def send_ptc():
                    result = p.PtcResult()
                    for action in plans:
                        success = action().value
                        result.code.append(0 if success else 1)
                        result.success.append(success)
                        result.stage.append('ONBOARD_EXECUTION' if success else 'DSS_REJECTED')
                        result.data.append('GENERIC DSS command receipt')
                        result.error.append('' if success else 'DSS rejected command')
                        if not success:
                            break
                    return result
                return send_ptc
        if family == 'TIME' and method == 'GetUTC':
            if config(request):
                raise ValueError('Unsupported GCS time modifier')
            def utc():
                state = self.transport.get('state')
                if state['epoch'] != self.transport.epoch:
                    raise ValueError('DSS time epoch changed')
                nanos = state['clock_epoch_unix_ns'] + state['core']['sim_time_ns']
                return p.Time(timeMsg=datetime.fromtimestamp(nanos/1e9, timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))
            return utc
        if family in {'RSC','TASK','MEM','RNG','USER'}:
            settings = config(request.config) if 'config' in request.DESCRIPTOR.fields_by_name else config(request)
            return self.ground.prepare(family,method,request,settings,check)
        raise NotImplementedError('Unqualified original driver method: ' + family + '.' + method)
