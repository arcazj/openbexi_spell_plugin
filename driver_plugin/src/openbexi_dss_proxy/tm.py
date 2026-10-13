# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.tm import TmInterface
from spell.lib.adapter.tm_item import TmItemClass
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException
from datetime import datetime,timezone
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue, UnpackValue
from .connection import call
from .common import POLICY, timeout_seconds


def validate_settings(config, allowed=()):
    # Original acquisition/comparison defaults are consumed by TmInterface.
    known = POLICY | {'ValueFormat','Timeout','Retries','Tolerance','RelTolerance','Wait','IgnoreCase','AllowInterrupt','Delay','Extended','AdjLimits','Retry','Strict','STEP_ID'} | set(allowed)
    if set(config or {}) - known:
        raise DriverException('Unqualified telemetry modifier: '+','.join(sorted(set(config)-known)))
    # These are original verifier controls/notification metadata; they stay
    # inside the library and are never serialized as acquisition modifiers.
    for key in ('Retry', 'Strict'):
        if key in (config or {}) and type(config[key]) is not bool:
            raise DriverException(key + ' must be boolean')
    if 'STEP_ID' in (config or {}) and (type(config['STEP_ID']) is not int or config['STEP_ID'] < 0):
        raise DriverException('STEP_ID must be a nonnegative integer')


class Telemetry(TmInterface):
    def _createTmItem(self,mnemonic,description=''):
        row = call('TM','CreateTmItem',p.TmItemDesc(mnemonic=mnemonic,description=description))
        return TmItemClass(self,row.mnemonic,row.description)

    def _refreshItem(self,item,config=None):
        settings = config or {}
        validate_settings(settings)
        # Library-only policy modifiers have already been interpreted by the
        # original interface. Only acquisition controls belong on this RPC.
        wire = {k:v for k,v in settings.items() if k in {'Wait','Timeout','ValueFormat'}}
        if 'Timeout' in wire:
            wire['Timeout'] = timeout_seconds(wire['Timeout'])
        row = call('TM','RefreshItem',p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()),config=PackValue(wire)))
        raw,eng = UnpackValue(row.rawValue),UnpackValue(row.engValue)
        item._setRaw(raw)
        item._setEng(eng)
        item._setTime(TIME(row.timestamp))
        item._setStatus(row.validity)
        return [raw if wire.get('ValueFormat') == 'Raw format' else eng,row.validity]

    def _databaseLookup(self,name,resource_type,source,config):
        return UnpackValue(call('TM','DatabaseLookup',p.LookupRequest(name=name,type=resource_type,source=source)).lookup)

    def _setLimits(self,item,config):
        validate_settings(config, ('LoRed','LoYel','HiYel','HiRed'))
        if config.get('ValueFormat','Eng format') not in {'Eng format','Default format'}:
            raise DriverException('This profile applies engineering limits only')
        limits = {key:config[key] for key in ('LoRed','LoYel','HiYel','HiRed') if key in config}
        return call('TM','SetLimits',p.LimitSetRequest(item=p.TmItemDesc(mnemonic=item.name()),
                    set=p.LimitSet(limitset=PackValue(limits)))).value

    def _getLimits(self,item,config):
        validate_settings(config)
        return UnpackValue(call('TM','GetLimits',p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()))).limitset)

    def _isAlarmed(self,item,config):
        validate_settings(config)
        return call('TM','IsAlarmed',p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()))).value

    def _restoreNormalLimits(self,config=None):
        validate_settings(config)
        return call('TM','RestoreNormalLimits',PackValue({})).value

    def _injectItem(self,item,value,config=None):
        validate_settings(config)
        row = self._databaseLookup(item.name(),'TM','GENERIC',{})
        kind,scale = row['raw_type'],row['engineering_scale']
        fmt = (config or {}).get('ValueFormat','Eng format')
        if kind in {'INT64','UINT64'}:
            from decimal import Decimal
            numeric = Decimal(str(value)) / Decimal(str(scale)) if fmt != 'Raw format' else Decimal(str(value))
            if not numeric.is_finite() or numeric != numeric.to_integral_value():
                raise DriverException('Injection is not representable by the raw catalog type')
            raw = int(numeric)
            eng = raw * scale
        elif kind == 'BOOLEAN':
            if str(value).lower() not in {'true','false'}:
                raise DriverException('Boolean injection requires true or false')
            raw = eng = str(value).lower() == 'true'
        elif kind == 'STRING':
            raw = eng = str(value)
        else:
            raise DriverException('Unqualified injection type')
        return call('TM','InjectItem',p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()),rawValue=PackValue(raw),
            engValue=PackValue(eng),validity=True,timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))).value


TM = Telemetry()
