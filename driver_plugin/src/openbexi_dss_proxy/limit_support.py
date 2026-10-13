# SPDX-License-Identifier: GPL-3.0-or-later
"""Map the driver's single persistent engineering threshold set to SPELL limits.

GENERIC is the identifier of the actual ground database record, always active.
This profile implements HARDSOFT only; it has no inactive definitions, activation
algorithms, status/spike/step limits, or alarm-enable switch. Partial updates are
read/merge/write operations, not a concurrent multi-writer transaction.
"""
import math

from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue, UnpackValue
from .connection import call


IDENTIFIER = 'GENERIC'
THRESHOLDS = ('LoRed', 'LoYel', 'HiYel', 'HiRed')


def engineering(config):
    if config.get('ValueFormat', 'Eng format') not in ('Eng format', 'Default format'):
        raise DriverException('This profile applies engineering limits only')


def selected(config, default):
    choice = config.get('Select', default)
    if type(choice) is not str or choice not in ('ALL', 'ACTIVE', IDENTIFIER):
        raise DriverException('Unknown limit definition selector')
    return choice


def read(item):
    return UnpackValue(call('TM', 'GetLimits', p.TmItemValue(
        item=p.TmItemDesc(mnemonic=item.name()))).limitset)


def get_limits(item, config):
    engineering(config)
    choice = selected(config, 'ALL')
    if 'Value' in config and choice != IDENTIFIER:
        raise DriverException('Value requires a specific limit definition identifier')
    value = config.get('Value')
    if 'Value' in config and (type(value) is not str or value not in THRESHOLDS + ('Type', 'Active')):
        raise DriverException('Unavailable limit definition property')
    definition = read(item)
    if not definition:
        raise DriverException('No limit definitions are configured for ' + item.name())
    definition.update(Type='HARDSOFT', Active=True)
    if 'Value' in config:
        return definition[value]
    return definition if choice == IDENTIFIER else {IDENTIFIER: definition}


def set_limits(item, config):
    engineering(config)
    selected(config, 'ACTIVE')
    if config.get('Type', 'HARDSOFT') != 'HARDSOFT':
        raise DriverException('This profile implements HARDSOFT limits only')
    if 'Limits' in config:
        definitions = config['Limits']
        if type(definitions) is not dict or set(definitions) != {IDENTIFIER}:
            raise DriverException('This profile has one limit definition: ' + IDENTIFIER)
        definition = definitions[IDENTIFIER]
    else:
        definition = config.get('Definition')
    if type(definition) is not dict or not definition:
        raise DriverException('A nonempty HARDSOFT definition is required')
    if set(definition) - set(THRESHOLDS) - {'Type', 'Active'}:
        raise DriverException('Unsupported limit definition fields')
    if definition.get('Type', 'HARDSOFT') != 'HARDSOFT' or definition.get('Active', True) is not True:
        raise DriverException('This profile supports an active HARDSOFT definition only')
    updates = {key: definition[key] for key in THRESHOLDS if key in definition}
    if not updates:
        raise DriverException('At least one threshold is required')
    for value in updates.values():
        if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
            raise DriverException('Thresholds must be finite numbers')
    limits = {} if len(updates) == len(THRESHOLDS) else read(item)
    limits.update(updates)
    if set(limits) != set(THRESHOLDS):
        raise DriverException('An initial HARDSOFT definition needs all four thresholds')
    if not all(limits[a] <= limits[b] for a, b in zip(THRESHOLDS, THRESHOLDS[1:])):
        raise DriverException('Thresholds must be ordered LoRed <= LoYel <= HiYel <= HiRed')
    # Original Any encoding carries integers as signed Int64 values. Reject
    # values the original schema cannot represent through SPELL failure policy.
    try:
        payload = PackValue(limits)
    except (ValueError, OverflowError, TypeError, SyntaxError) as error:
        raise DriverException('Thresholds cannot be represented by the original driver schema') from error
    # Original schema and server perform the persistent, journalled effect.
    return call('TM', 'SetLimits', p.LimitSetRequest(
        item=p.TmItemDesc(mnemonic=item.name()), set=p.LimitSet(limitset=payload))).value
