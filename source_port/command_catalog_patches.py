"""Checked native sequence copies, authoritative catalog lookup and confirmation."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {'spell/lib/adapter/tc_item.py': 'cdef60d1d2a6ac8757b9143b87e19382225d2cf5791bfab1ef94c7fc1cfbf634', 'spell/lib/adapter/tc.py': '9ba0622e243c97bdb59c263c30324b588b7d7025014cfaafdcbbb0a0e45b58c5', 'openbexi_spell_dss/rpc.py': '0f12406d766b060354ffdb9a0fddaaf5ad42038ad3a90ee28decf09bf8c4f438', 'openbexi_dss_proxy/tc.py': 'e60cbc882c47e98924faeeefe310c790b3f430a32c630e959cf84a227cb3b9af'}


def replace(source,old,new):
    if source.count(old)!=1:raise ValueError('Command catalog patch anchor differs: '+old[:80])
    return source.replace(old,new)


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Command catalog preimage differs: '+name)
    source=raw.decode('utf-8')
    if name=='spell/lib/adapter/tc_item.py':
        source=replace(source,'        itemCopy._setParams(self.__parameters)',
            '''        if self.isComplex():
            itemCopy._setElements([element.split('@',1)[1] for element in self.__elements[1:]])
        itemCopy._setParams(self.__parameters)''')
    elif name=='spell/lib/adapter/tc.py':
        source=replace(source,'        useConfig[Confirm] = True',
            '        if self.shouldForceTcConfirm():\n            useConfig[Confirm] = True')
    elif name=='openbexi_spell_dss/rpc.py':
        source=replace(source,'from .codec import pack, unpack','from .codec import pack, unpack\nfrom .command_catalog import lookup as command_lookup')
        source=replace(source,"            item = database.command(request.mnemonic)\n            return lambda:p.TcItemDesc(mnemonic=item['name'], description=item['effect'], id=str(item['command_code']))",
            """            item = command_lookup(database,request.mnemonic)
            return lambda:p.TcItemDesc(mnemonic=item['name'],description=item.get('effect','GENERIC command sequence'),
                id='SEQUENCE' if item['kind']=='SEQUENCE' else str(item['command_code']))""")
        source=replace(source,"item = database.item(request.name) if request.type == 'TM' else database.command(request.name)",
            "item = database.item(request.name) if request.type == 'TM' else command_lookup(database,request.name)")
    elif name=='openbexi_dss_proxy/tc.py':
        source=replace(source,'from .command_settings import normalize','from .command_settings import normalize\nfrom .command_catalog import create, check_critical, send_sequence')
        source=replace(source,"        row = call('TC','CreateTcItem',p.TcItemDesc(mnemonic=mnemonic,description=description))\n        return TcItemClass(self,row.mnemonic,row.description)",
            '''        return create(self,mnemonic,description)

    def _checkCriticalCommands(self,items,config=None):
        check_critical(items,config)''')
        source=replace(source,"        request = descriptor(item,config)",'''        if item.isComplex():
            return send_sequence(self,item,config)
        request = descriptor(item,config)
        # TcInterface has already called our critical-confirmation hook.
        # The original Boolean RPC cannot itself display a native prompt.
        from spell.utils.grpc_utils import UnpackValue
        options = UnpackValue(request.config)
        options['ConfirmCritical'] = False
        request.config.CopyFrom(PackValue(options))''')
    else:raise ValueError('Unknown catalog patch target')
    result=source.encode('utf-8');compile(result,name,'exec');return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence);manifest={}
    for name,expected in PREIMAGES.items():
        path=site/name;original=path.read_bytes();patched=apply(name,original)
        for label,content in (('original',original),('patched',patched)):
            target=evidence/label/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        path.write_bytes(patched)
        manifest[name]=dict(preimage_sha256=expected,sha256=hashlib.sha256(patched).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':apply_tree(*sys.argv[1:])
