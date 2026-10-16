"""Preserve valid persisted ranging bytes when reopening needs no migration."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib

PREIMAGES={'openbexi_spell_dss/ground.py':'b79417982509774022c11ae2ad403e47a32e0cf4e6536d2beb4d3b413d766a7f'}
BEFORE="            initialize(state)\n            journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(canonical(state),self.namespace))"
AFTER="            initialize(state)\n            if state != json.loads(encoded):\n                journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(canonical(state),self.namespace))"


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Ranging reopen preimage differs')
    text=raw.decode('utf-8')
    if text.count(BEFORE)!=1:raise ValueError('Ranging reopen anchor differs')
    result=text.replace(BEFORE,AFTER).encode('utf-8');compile(result,name,'exec');return result
