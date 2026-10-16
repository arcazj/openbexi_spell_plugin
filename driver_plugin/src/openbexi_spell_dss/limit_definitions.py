"""Bounded GENERIC limit definitions, independent of RPC and mutable telemetry.

Each modification returns a new validated dictionary. The RPC layer must commit
the complete result atomically and retain the actual before/after evidence.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
import math

THRESHOLDS = ('LoRed', 'LoYel', 'HiYel', 'HiRed')
STATUSES = ('Nominal', 'Warning', 'Error', 'Ignore')
METADATA = ('Type', 'Active', 'Name', 'Algorithm', 'Hysteresis')
TYPES = ('HARDSOFT', 'STATUS', 'SPIKE', 'STEP')
MAX_DEFINITIONS = 16


def number(value):
    if type(value) not in (int, float):
        raise ValueError('Limit values must be finite numbers')
    if type(value) is int and not -(2**63) <= value < 2**63:
        raise ValueError('Limit integer is outside the original Int64 schema')
    if type(value) is float and not math.isfinite(value):
        raise ValueError('Limit values must be finite numbers')
    return value


def text(value, size, label):
    if type(value) is not str or len(value.encode('utf-8')) > size or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid '+label)
    return value


def identifier(value):
    text(value, 96, 'limit identifier')
    if not value or value in ('ALL', 'ACTIVE'):
        raise ValueError('Reserved or empty limit identifier')
    return value


def definition(patch, previous=None, requested_type=None):
    """Merge one definition without mutating the caller or losing string states."""
    if type(patch) is not dict or not patch:
        raise ValueError('A nonempty limit definition is required')
    if set(patch) - set(THRESHOLDS+STATUSES+METADATA+('Delta', 'Midpoint', 'Tolerance', 'LoBoth', 'HiBoth')):
        raise ValueError('Unknown limit definition field')
    update = deepcopy(patch)
    for both, lower, upper in (('LoBoth', 'LoRed', 'LoYel'), ('HiBoth', 'HiYel', 'HiRed')):
        if both in update:
            if lower in update or upper in update:
                raise ValueError('Paired and individual thresholds conflict')
            update[lower] = update[upper] = number(update.pop(both))
    midpoint = 'Midpoint' in update or 'Tolerance' in update
    if midpoint:
        if not {'Midpoint', 'Tolerance'} <= set(update) or set(update) & set(THRESHOLDS):
            raise ValueError('Midpoint and tolerance must be provided together without thresholds')
        middle, tolerance = number(update.pop('Midpoint')), number(update.pop('Tolerance'))
        if tolerance < 0:
            raise ValueError('Tolerance must not be negative')
        update.update(LoRed=number(middle-tolerance), LoYel=number(middle-tolerance),
                      HiYel=number(middle+tolerance), HiRed=number(middle+tolerance))
    supplied = update.get('Type', requested_type)
    if requested_type is not None and update.get('Type', requested_type) != requested_type:
        raise ValueError('Conflicting requested limit types')
    inferred = ('STATUS' if set(update) & set(STATUSES) else
                'HARDSOFT' if set(update) & set(THRESHOLDS) else
                ('STEP' if type(update['Delta']) is list else 'SPIKE') if 'Delta' in update else None)
    kind = supplied or (previous or {}).get('Type') or inferred
    if kind not in TYPES or inferred is not None and inferred != kind:
        raise ValueError('Limit values differ from the selected type')
    if previous is not None and previous['Type'] != kind:
        raise ValueError('A partial update cannot change an existing definition type')
    result = deepcopy(previous) if previous is not None else {}
    result.update(update)
    result.setdefault('Active', True)
    result['Type'] = kind
    if type(result['Active']) is not bool:
        raise ValueError('Active must be Boolean')
    if 'Hysteresis' in result and (type(result['Hysteresis']) is not int or not 0 <= result['Hysteresis'] <= 1024):
        raise ValueError('Hysteresis must be an integer from zero to 1024')
    for key, size in (('Name', 256), ('Algorithm', 1024)):
        if key in result:text(result[key], size, key)
    values = set(result)-set(METADATA)
    if kind == 'HARDSOFT':
        if values != set(THRESHOLDS):
            raise ValueError('HARDSOFT requires all four thresholds')
        for key in THRESHOLDS:number(result[key])
        if any(result[a] > result[b] for a,b in zip(THRESHOLDS, THRESHOLDS[1:])):
            raise ValueError('Thresholds must be ordered LoRed <= LoYel <= HiYel <= HiRed')
    elif kind == 'STATUS':
        if values - set(STATUSES):
            raise ValueError('STATUS accepts named status lists only')
        all_states = set()
        for status in STATUSES:
            states = result.get(status, [])
            if type(states) is str:states = [states]
            if type(states) is not list or len(states) > 128:
                raise ValueError('A status needs a string or at most 128 string values')
            for state in states:
                text(state, 256, 'status value')
                if state in all_states:
                    raise ValueError('A status value must belong to exactly one class')
                all_states.add(state)
            result[status] = list(states)
    else:
        if values != {'Delta'}:
            raise ValueError('STEP and SPIKE accept Delta only')
        delta = result['Delta']
        if kind == 'STEP':
            if type(delta) is not list or len(delta) != 2:
                raise ValueError('STEP requires [down_delta, up_delta]')
            deltas = delta
        else:
            deltas = [delta]
        if any(number(d) < 0 for d in deltas):
            raise ValueError('Delta must not be negative')
    return result


def selected(definitions, selector, applies=lambda row: row['Active']):
    if type(definitions) is not dict or len(definitions) > MAX_DEFINITIONS:
        raise ValueError('Invalid limit definition collection')
    if selector == 'ALL':return list(definitions)
    if selector == 'ACTIVE':return [name for name,row in definitions.items() if applies(row)]
    identifier(selector)
    if selector not in definitions:raise ValueError('Unknown limit definition: '+selector)
    return [selector]


def modify(current, *, updates=None, patch=None, selector='ACTIVE', requested_type=None,
           applies=lambda row: row['Active']):
    """Validate all members before publishing a multi-definition replacement."""
    if (updates is None) == (patch is None):
        raise ValueError('Provide either named definitions or one selected patch')
    if type(current) is not dict or len(current) > MAX_DEFINITIONS:
        raise ValueError('Invalid existing limit definitions')
    result = deepcopy(current)
    if updates is not None:
        if type(updates) is not dict or not updates or len(updates) > MAX_DEFINITIONS:
            raise ValueError('Expected one to sixteen named definitions')
        for key, value in updates.items():
            identifier(key)
            result[key] = definition(value, result.get(key), requested_type)
    else:
        names = selected(result, selector, applies)
        # The GENERIC simulator initially has no configured OOL definitions.
        # Preserve its existing first-definition behavior for ordinary callers.
        if not result and selector in ('ALL', 'ACTIVE'):
            names = ['GENERIC']
        if not names:raise ValueError('No selected active limit definitions')
        for key in names:
            result[key] = definition(patch, result.get(key), requested_type)
    if len(result) > MAX_DEFINITIONS:
        raise ValueError('Limit definition capacity exceeded')
    return result


def property_value(row, key):
    if key in row:return deepcopy(row[key])
    if key in ('Midpoint', 'Tolerance') and row['Type'] == 'HARDSOFT':
        low, high = row['LoYel'], row['HiYel']
        return low/2+high/2 if key == 'Midpoint' else high/2-low/2
    raise ValueError('Unavailable property for this limit type: '+str(key))


def classify(row, value, previous_value=None):
    """Pure severity calculation; sample deduplication/hysteresis live in storage."""
    kind = row['Type']
    if kind == 'STATUS':
        if type(value) is not str:raise ValueError('STATUS requires string telemetry')
        for state in STATUSES:
            if value in row[state]:return state
        return 'Error'  # Unlisted values are outside the declared status domain.
    number(value)
    if kind == 'HARDSOFT':
        if value < row['LoRed'] or value > row['HiRed']:return 'Error'
        if value < row['LoYel'] or value > row['HiYel']:return 'Warning'
        return 'Nominal'
    if previous_value is None:return 'Nominal'
    number(previous_value)
    change = value-previous_value
    if kind == 'SPIKE':return 'Error' if abs(change) > row['Delta'] else 'Nominal'
    down, up = row['Delta']
    return 'Error' if change < -down or change > up else 'Nominal'
