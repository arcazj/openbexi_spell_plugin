"""Restore original memory helpers and bind GENERIC binary reference images."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import re

PREIMAGES={
 'openbexi_spell_dss/rpc.py':'66857b791edcdf1b07787bee31c023c4b883d5148d6f41eff5b3673312083743',
 'openbexi_spell_dss/ground.py':'e2a72ed8b333499892c9cf456317ac1dec23da641af7999a0358600ce9811461',
 'openbexi_dss_proxy/tm.py':'4ddaeacbeb5d400fa8750e01a56f936f290d5f59ac76e40a93649c82ddda2dfd',
 'openbexi_dss_proxy/memory.py':'3efb17ca7600f7b99c849dd3870ad516eb8079c1d2bf4890d88e30abb715f5f7',
 'spell/lang/helpers/memhelper.py':'514a99e1dce2f7a92426295425a9ee8de718a35a4b933d0829348a67325436e5',
}


def replace(source,old,new):
    if source.count(old)!=1:raise ValueError('Memory patch anchor differs: '+old[:90])
    return source.replace(old,new)


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Memory source preimage differs: '+name)
    source=raw.decode('utf-8')
    if name=='openbexi_spell_dss/ground.py':
        source=replace(source,"        if family == 'MEM':\n", """        if family == 'MEM':
            from .memory_images import prepare
            operation=prepare(self,method,request,settings,check)
            if operation is not None:return operation
""")
    elif name=='openbexi_spell_dss/rpc.py':
        start=source.index("        if family == 'TM' and method == 'DatabaseLookup':")
        end=source.index("        if family == 'TM' and method == 'RefreshItem':",start)
        source=source[:start]+"""        if family == 'TM' and method == 'DatabaseLookup':
            from .memory_images import database_lookup
            item=database_lookup(database,request,command_lookup)
            return lambda:p.LookupAnswer(lookup=pack(item))
"""+source[end:]
    elif name=='openbexi_dss_proxy/tm.py':
        source=replace(source,"        return UnpackValue(call('TM','DatabaseLookup',p.LookupRequest(name=name,type=resource_type,source=source)).lookup)",
            "        from .memory_support import database\n        return database(name,resource_type,source,config)")
    elif name=='openbexi_dss_proxy/memory.py':
        source=replace(source,'from .common import settings','from .common import settings\nfrom . import memory_support as support')
        start=source.index('    def _generateReport(');end=source.index('    def _dataObjectLookup(',start)
        source=source[:start]+'''    def _generateReport(self,image,report_type,begin,end,source,config=None):
        return support.generate(self,image,report_type,begin,end,source,config)

    def _compareImages(self,image1,image2,report_type,begin,end,source,config=None):
        return support.compare(image1,image2,report_type,begin,end,source,config)

    def _createGoldenImage(self,scp,filename,config=None):
        return support.capture(scp,filename,config)

    def _memoryLookup(self,name,address,image,report_type,source,config=None):
        return support.lookup(name,address,image,report_type,source,config)

'''+source[end:]
        source=replace(source,"p.DataObjectLookupRequest(name=name,type=ltype,config=settings(config))",
            "p.DataObjectLookupRequest(name=name,type=ltype,config=settings(support.options(config,{'Name','Type'})))")
        source=replace(source,"source=source,valformat=valueFormat,config=settings(config))",
            "source=source,valformat=valueFormat,config=settings(support.options(config,{'Name','Type','Source','ValueFormat'})))")
    else:
        split=source.index('class DataObjectLookup_Helper')
        head,tail=source[:split],source[split:]
        for modifier,field,default,count in (('Type','type',"''",3),('Source','source',"'GENERIC'",3),
                                              ('Begin','begin',"''",2),('End','end',"''",2)):
            pattern=r'        if not self\.hasConfig\('+modifier+r'\):\n            raise SyntaxException\([^\n]+\)\n        self\.__'+field+r' = self\.getConfig\('+modifier+r'\)'
            head,total=re.subn(pattern,'        self.__'+field+' = self.getConfig('+modifier+') if self.hasConfig('+modifier+') else '+default,head)
            if total!=count:raise ValueError('Original memory filter anchors differ: '+modifier)
        lookup=head.index('class MemoryLookup_Helper')
        head=head[:lookup]+replace(head[lookup:], '        return [False, True]', '        return [False, None]')
        source=head+tail
    result=source.encode('utf-8');compile(result,name,'exec');return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    outputs={name:apply(name,(site/name).read_bytes()) for name in PREIMAGES}
    report={}
    for name,output in outputs.items():
        for stage,data in (('original',(site/name).read_bytes()),('patched',output)):
            path=evidence/stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        (site/name).write_bytes(output)
        report[name]=dict(preimage_sha256=PREIMAGES[name],sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    import sys
    apply_tree(sys.argv[1],sys.argv[2])
