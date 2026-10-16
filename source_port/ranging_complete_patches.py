"""Checked original helper, constants and driver changes for complete ranging."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib,json
from pathlib import Path

PREIMAGES={
 'spell/lang/helpers/rnghelper.py':'12a95ccbf1bdd3857a6d6e8bced9222af0fc6d67318e4c3412546d166b20bd18',
 'spell/lang/constants.py':'2497936cae1dda6540a7d85e3a956f646a56779c65d8789e0f9582b6bba89063',
 'openbexi_dss_proxy/ranging.py':'c8586f47b47dbaa5f1d3fb411a33c8f2f4746bdaa0276fa80de61e004b716388',
 'openbexi_spell_dss/ground.py':'e2a72ed8b333499892c9cf456317ac1dec23da641af7999a0358600ce9811461',
}


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Ranging source preimage differs: '+name)
    source=raw.decode('utf-8')
    def once(before,after):
        nonlocal source
        if source.count(before)!=1:raise ValueError('Ranging patch anchor differs: '+before[:80])
        source=source.replace(before,after)
    if name=='spell/lang/constants.py':
        assert all(('\n'+key+' ') not in source for key in ('IDLE','RANGING','CALIBRATING'))
        source+='\n# LRM 2.4.4 ranging statuses. Preserve the existing shared ERROR=2.\nIDLE = 0\nRANGING = 1\nCALIBRATING = 3\n'
    elif name=='spell/lang/helpers/rnghelper.py':
        start=source.index('class StartRanging_Helper(')
        begin=source.index('    def _doPreOperation(',start)
        end=source.index('    #===========================================================================',begin)
        source=source[:begin]+'''    def _doPreOperation(self, *args, **kargs):
        if len(args)!=2:
            raise SyntaxException("Expected a baseband/antenna pair or two path lists")
        if all(type(item) is str for item in args):
            self.__bbe,self.__antenna=args
        elif all(type(item) is list and len(item)==2 and
                 all(type(value) is str for value in item) for item in args):
            self.__bbe=[item[0] for item in args]
            self.__antenna=[item[1] for item in args]
        else:
            raise SyntaxException("Expected two complete baseband/antenna lists")

'''+source[end:]
    elif name=='openbexi_dss_proxy/ranging.py':
        once("        return call('RNG','StartRanging',p.Ranging(bbe=bbe,antenna=antenna,config=ranging_settings(config))).value",
             "        from .ranging_complete import operation\n        return operation('StartRanging',bbe,antenna,config)")
        once("        return call('RNG','StartCalibration',p.Ranging(bbe=bbe,antenna=antenna,config=ranging_settings(config))).value",
             "        from .ranging_complete import operation\n        return operation('StartCalibration',bbe,antenna,config)")
        once("        return call('RNG','SetBasebandConfig',p.BaseBandConfig(bbe=bbe,param=param,value=str(value),config=ranging_settings(config))).value",
             "        from .ranging_complete import configure\n        return configure(bbe,param,value,config)")
        once("        return call('RNG','GetRangingStatus',ranging_settings(config)).value",
             "        from .ranging_complete import status\n        return status(call('RNG','GetRangingStatus',ranging_settings(config)).value)")
    else:
        once("or type(activity) is not str or activity not in {'READY','RANGING','CALIBRATING'}):",
             "or type(activity) is not str or activity not in {'READY','RANGING','CALIBRATING','ERROR'}):")
        once("                raise ValueError('Invalid separate ranging schedule/activity state')",
             "                raise ValueError('Invalid separate ranging schedule/activity state')\n            from .ranging_complete import initialize\n            initialize(state)\n            journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(canonical(state),self.namespace))")
        begin=source.index("        if family == 'RNG':")
        end=source.index("        raise NotImplementedError(family+'.'+method)",begin)
        source=source[:begin]+"        if family == 'RNG':\n            from .ranging_complete import prepare\n            return prepare(self,method,request,settings,check)\n"+source[end:]
    output=source.encode('utf-8');compile(output,name,'exec');return output


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence);manifest={}
    outputs={name:apply(name,(site/name).read_bytes()) for name in PREIMAGES}
    for name,output in outputs.items():
        for stage,content in (('original',(site/name).read_bytes()),('patched',output)):
            target=evidence/stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        (site/name).write_bytes(output)
        manifest[name]=dict(preimage_sha256=PREIMAGES[name],sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    import sys
    apply_tree(sys.argv[1],sys.argv[2])
