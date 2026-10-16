"""Exact original-schema Group/Block integration, preserving native result status."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES={'spell/lang/modifiers.py': 'bc28c8155ff0d9cc1690cd054588738658d95339b74baa473a52a220c8699558', 'spell/lang/helpers/tchelper.py': '551c3990be8393c8eead143ab4da509e368418b72425e573370d22f910630c58', 'openbexi_spell_dss/rpc.py': 'f063450c2eeeb2ea716d2595c0dc6acef499a7aef0b151d91386a109fd29f251', 'openbexi_dss_proxy/tc.py': 'e2eeb2e4ec6ba259e65a8f0c98105d5352ed73a0c7e2301233c6ba248d712ae7', 'openbexi_dss_proxy/command_settings.py': 'a5b1a3837a6f33a78a4424c061d0aad8efae5befc3afbdb4ade8840b814f11eb'}


def replace(source,old,new):
    if source.count(old)!=1:raise ValueError('Group patch anchor differs: '+old[:80])
    return source.replace(old,new)


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Group patch preimage differs: '+name)
    source=raw.decode('utf-8')
    if name=='spell/lang/modifiers.py':
        source+="\n# LRM2.4.4 section4.5.10, noninterleaved command uplinks.\nGroup = 'Group'\n"
    elif name=='spell/lang/helpers/tchelper.py':
        source=replace(source,'                        Block, ReleaseTime):',
            "                        Block, ReleaseTime, 'Group', 'LoadOnly', 'addInfo'):")
    elif name=='openbexi_dss_proxy/command_settings.py':
        source=replace(source,"                    raise DriverException('Grouped command protocol is not qualified yet')",
            '                    result[key] = True')
    elif name=='openbexi_spell_dss/rpc.py':
        source=replace(source,'            from .command_rpc import prepare','            from .command_group_rpc import prepare')
        source=replace(source,"        if family == 'TM' and method == 'DatabaseLookup':",'''        if family == 'TM' and method == 'DatabaseLookup':
            from .command_results import Results,SOURCE
            if request.source == SOURCE:
                if request.type != 'TC':
                    raise ValueError('Command result lookup type differs')
                result = Results(self.journal,self.ground.namespace).read(identity,request.name)
                return lambda:p.LookupAnswer(lookup=pack(result))''')
    elif name=='openbexi_dss_proxy/tc.py':
        source=replace(source,'from .command_catalog import create, check_critical, send_sequence',
            'from .command_catalog import create, check_critical, send_sequence\nfrom .command_group import requested as group_requested, send as send_group, settings as group_settings')
        source=replace(source,'    def _sendCommand(self,item,config=None):', '''    def _sendCommand(self,item,config=None):
        if group_requested([item],config):
            return send_group(self,[item],config,blocked=group_settings(item,config).get('Block',False))''')
        source=replace(source,'    def _sendList(self,items,config=None):', '''    def _sendList(self,items,config=None):
        if group_requested(items,config):
            return send_group(self,items,config,blocked=any(group_settings(item,config).get('Block',False) for item in items))''')
        source=replace(source,"        raise DriverException('Atomic command blocks are not qualified in this driver profile')",
            '        return send_group(self,items,config,blocked=True)')
    else:raise ValueError('Unknown grouped command source')
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
