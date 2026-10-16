"""Pure normalization of original limit helper syntax, without lossy strings."""
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy

FIELDS = ('LoRed', 'LoYel', 'HiYel', 'HiRed', 'LoBoth', 'HiBoth', 'Midpoint',
          'Nominal', 'Warning', 'Error', 'Ignore', 'Delta', 'Active', 'Name',
          'Algorithm', 'Hysteresis')


def normalize(options):
    direct = {key: deepcopy(options[key]) for key in FIELDS if key in options}
    if 'Midpoint' in direct:
        if 'Tolerance' not in options:raise ValueError('Midpoint requires Tolerance')
        direct['Tolerance'] = deepcopy(options['Tolerance'])
    if sum((bool(direct), 'Definition' in options, 'Limits' in options, 'Expected' in options)) != 1:
        raise ValueError('Provide exactly one limit definition form')
    if 'Expected' in options:raise ValueError('Use Nominal or Midpoint instead of Expected')
    if 'Limits' in options:
        limits = deepcopy(options['Limits'])
        if type(limits) is dict:
            if not limits or any(type(row) is not dict or not row for row in limits.values()):
                raise ValueError('Expected nonempty named limit definitions')
            if 'Select' in options:raise ValueError('Select is not used with named definitions')
            return {'Limits': limits}
        if type(limits) is not list or len(limits) not in (2, 4):
            raise ValueError('Expected named definitions or a legacy two/four-value list')
        # Preserve the original legacy order: LoRed, LoYel, HiRed, HiYel.
        direct = dict(zip(('LoRed', 'LoYel', 'HiRed', 'HiYel'), limits)) if len(limits) == 4 else dict(
            LoRed=limits[0], LoYel=limits[0], HiYel=limits[1], HiRed=limits[1])
    elif 'Definition' in options:
        direct = deepcopy(options['Definition'])
    if type(direct) is not dict or not direct:raise ValueError('Expected a nonempty limit definition')
    return {'Definition': direct}
