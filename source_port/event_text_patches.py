"""Preserve all protobuf event strings; severity/scope validation stays strict."""
import hashlib

PREIMAGES={'openbexi_spell_dss/rpc.py':'8254841864b829f8f1ded002bd75ba0ac541f41c8bd6c0f3e77f5428bdf89a27'}


def apply(name,source):
    if name not in PREIMAGES or hashlib.sha256(source).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Event text preimage differs: '+name)
    before=b"if (not 1 <= len(request.message) <= 8192 or set(settings)-{'Severity','Scope'}"
    after=b"if (set(settings)-{'Severity','Scope'}"
    if source.count(before)!=1:raise ValueError('Event validation anchor differs')
    return source.replace(before,after)
