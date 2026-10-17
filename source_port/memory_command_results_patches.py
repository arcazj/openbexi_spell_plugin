"""Preserve authenticated command-result lookups beside memory catalog lookup."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib

SOURCE = 'openbexi_spell_dss/rpc.py'
PREIMAGES = {SOURCE: 'e92aa6633b950fac7fc4a8f6213eddc5e9ec1d31c8e9b118655f79e789ede388'}
BEFORE = """        if family == 'TM' and method == 'DatabaseLookup':
            from .memory_images import database_lookup
"""
AFTER = """        if family == 'TM' and method == 'DatabaseLookup':
            from .command_results import Results,SOURCE
            if request.source == SOURCE:
                if request.type != 'TC':
                    raise ValueError('Command result lookup type differs')
                result = Results(self.journal,self.ground.namespace).read(identity,request.name)
                return lambda:p.LookupAnswer(lookup=pack(result))
            from .memory_images import database_lookup
"""


def apply(name, raw):
    if name not in PREIMAGES or hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Memory/command result preimage differs: '+name)
    source = raw.decode('utf-8')
    if source.count(BEFORE) != 1:
        raise ValueError('Memory catalog dispatch anchor differs')
    result = source.replace(BEFORE, AFTER).encode('utf-8')
    compile(result, name, 'exec')
    return result
