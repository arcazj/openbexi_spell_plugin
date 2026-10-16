"""Keep Send limit adjustment isolated from command and verification policy."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES={'spell/lang/helpers/tchelper.py':'5ed1798b28ec307e2e007d85243b4461725b0d89acf4568e95c042cbac7ddc51'}


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Send preimage differs')
    source=raw.decode('utf-8')
    before='''                config = self.getConfig()
                config.update(limits)
                if Select not in config:
                    config[Select] = ACTIVE
                SetLimits( paramName, config )'''
    after='''                # Internal limit changes must not inherit Send/Verify actions.
                # Propagate failure to the enclosing Send operation for handling.
                selection = self.getConfig(Select) if self.hasConfig(Select) else ACTIVE
                SetLimits(paramName, Definition=limits, Select=selection,
                          HandleError=False, PromptUser=False)'''
    if source.count(before)!=2:raise ValueError('Send limit call anchors differ')
    source=source.replace(before,after)
    before='''                    limits[Nominal] = paramValue # expected by the verify
                    limits[Error] = currentValue'''
    after='''                    limits[Nominal] = [paramValue] # expected by the verify
                    limits[Error] = [currentValue] if currentValue != paramValue else []'''
    if source.count(before)!=1:raise ValueError('Send status anchor differs')
    source=source.replace(before,after)
    if source.count('                    if conditionTolerance:')!=1:raise ValueError('Send tolerance anchor differs')
    source=source.replace('                    if conditionTolerance:','                    if conditionTolerance is not None:')
    result=source.encode('utf-8');compile(result,name,'exec');return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    outputs={name:apply(name,(site/name).read_bytes()) for name in PREIMAGES}
    report={}
    for name,output in outputs.items():
        for stage,data in (('original',(site/name).read_bytes()),('patched',output)):
            target=evidence/stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        (site/name).write_bytes(output)
        report[name]=dict(preimage_sha256=PREIMAGES[name],sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__=='__main__':
    import sys
    apply_tree(sys.argv[1],sys.argv[2])
