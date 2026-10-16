"""Compose the reviewed memory dispatch after the reviewed ranging corrections."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import memory_feature_patches as memory

PREIMAGES = dict(memory.PREIMAGES)
PREIMAGES['openbexi_spell_dss/ground.py'] = 'a19d6afae4df362a6c8850374a8a82e615dd47a4982d1a52a8a96924037abeb5'


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Memory/ranging composition preimage differs: '+name)
    if name != 'openbexi_spell_dss/ground.py':
        return memory.apply(name, raw)
    anchor = b"        if family == 'MEM':\n"
    if raw.count(anchor) != 1:
        raise ValueError('Memory dispatch anchor differs')
    result = raw.replace(anchor, anchor +
        b'            from .memory_images import prepare\n'
        b'            operation=prepare(self,method,request,settings,check)\n'
        b'            if operation is not None:return operation\n')
    compile(result, name, 'exec')
    return result
