"""Catalog-owned command sequences with ordered, duplicate-preserving members."""
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy


def lookup(database,name):
    for command in database.commands:
        if command['name']==name:
            return dict(command,kind='COMMAND')
    matches=[row for row in database.material.get('command_sequences',[]) if row.get('name')==name]
    if len(matches)!=1:
        raise ValueError('Command or sequence is absent or ambiguous in the GENERIC database')
    members=matches[0].get('members')
    if type(members) is not list or not 1 <= len(members) <= 16:
        raise ValueError('Command sequence size exceeds bounds')
    for member in members:
        if type(member) is not dict or set(member)!={'command','args','modifiers'}:
            raise ValueError('Command sequence member schema differs')
        database.command(member['command'])  # Nested/cyclic sequences are not catalog commands.
        if type(member['args']) is not dict or type(member['modifiers']) is not dict:
            raise ValueError('Command sequence arguments/modifiers must be dictionaries')
    return dict(name=name,kind='SEQUENCE',members=deepcopy(members),
                critical=any(database.command(member['command'])['critical'] for member in members))
