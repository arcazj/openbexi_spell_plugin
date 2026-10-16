"""Original-schema transport for the explicit OPENBEXI_LIMITS_1 profile."""
# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue, UnpackValue
from .connection import call

PROFILE = 'OPENBEXI_LIMITS_1'
CONTROL = 'LimitProfile'


def engineering(config):
    if config.get('ValueFormat', 'Eng format') not in ('Eng format', 'Default format'):
        raise DriverException('This profile applies engineering limits only')


def encoded(value):
    try:return PackValue(value)
    except (ValueError, OverflowError, TypeError, SyntaxError) as error:
        raise DriverException('Limit request cannot be represented by the original schema') from error


def operation(name, verb, settings):
    return call('TM', 'SetLimits', p.LimitSetRequest(item=p.TmItemDesc(mnemonic=name),
        set=p.LimitSet(limitset=encoded({CONTROL: PROFILE, 'Operation': verb, 'Settings': settings})))).value


def get_limits(item, config):
    engineering(config)
    settings = {key: config[key] for key in ('Select', 'Value') if key in config}
    return UnpackValue(call('TM', 'GetLimits', p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()),
        config=encoded({CONTROL: PROFILE, **settings}))).limitset)


def set_limits(item, config):
    engineering(config)
    settings = {key: config[key] for key in ('Definition', 'Limits', 'Select', 'Type') if key in config}
    return operation(item.name(), 'Modify', settings)


def alarm(item, enabled, config):
    engineering(config)
    return operation(item.name(), 'Alarm', {'Enabled': enabled})


def load(uri, config):
    engineering(config)
    return operation('', 'Load', {'File': uri})


def adjust(conditions, config, equality):
    engineering(config)
    rows = []
    for condition in conditions:
        if type(condition) not in (list, tuple) or len(condition) not in (3, 4):
            raise DriverException('Expected a three/four-item telemetry condition')
        name, comparison, value = condition[:3]
        if comparison != equality:continue
        options = condition[3] if len(condition) == 4 else {}
        if type(options) is not dict:raise DriverException('Condition options must be a dictionary')
        rows.append({'Parameter': name.name() if hasattr(name, 'name') else name, 'Value': value,
                     'Tolerance': options.get('Tolerance', config.get('Tolerance', 0)),
                     'Select': options.get('Select', config.get('Select', 'ACTIVE'))})
    if not rows:return False
    return operation('', 'Adjust', {'Conditions': rows})
