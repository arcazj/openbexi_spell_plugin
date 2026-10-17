"""Replay the reviewed driver-only sequence/memory dispatch correction."""
import hashlib

SOURCE = 'openbexi_spell_dss/memory_images.py'
PREIMAGE = '588ebd0a759ee0bd68d7492dc22920f590097c16a57f620e5801931eb4d90f82'


def apply(before):
    assert hashlib.sha256(before).hexdigest() == PREIMAGE
    edits = (
        (b'    if mnemonic.startswith(LOOKUP_PREFIX):\n',
         b'    bounded=mnemonic.startswith(LOOKUP_PREFIX)\n    if bounded:\n'),
        (b"        key='item_code' if request.type=='TM' else 'command_code'\n",
         b'        # Native command expansion uses this original-schema endpoint too.\n'
         b'        # A sequence has no address; only an unbounded catalog lookup selects it.\n'
         b"        if request.type=='TC' and item.get('kind')=='SEQUENCE' and not bounded:\n"
         b'            return item\n'
         b"        key='item_code' if request.type=='TM' else 'command_code'\n"),
    )
    result = before
    for old, new in edits:
        assert result.count(old) == 1
        result = result.replace(old, new)
    return result
