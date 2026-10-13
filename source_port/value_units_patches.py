"""Checked native TC argument casting; original ValueClass/PCS semantics retained.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES={
    'spell/lib/adapter/tc_item.py':'26701dba2b1c218e5418dbcd9b1038bd0306670aa3ca98218f8d491e6ed401f7',
    'openbexi_dss_proxy/tc.py':'5b6784d0bd7ed7f5bc935e06a51f8b9d52fe27d30f53b139868cedaf84e40f97',
}


def replace(source,old,new):
    if source.count(old)!=1:
        raise ValueError('TC value patch occurrence changed: '+old[:100])
    return source.replace(old,new)


def apply(name,raw):
    if name not in PREIMAGES:
        return raw
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:
        raise ValueError('TC value patch preimage changed: '+name)
    source=raw.decode()
    if name=='openbexi_dss_proxy/tc.py':
        return replace(source,
            "    return p.CommandDesc(command=p.TcItemDesc(mnemonic=item.name(),description=item.desc()),args=PackValue(args),config=PackValue({'Timeout':timeout}))",
            """    try:
        return p.CommandDesc(command=p.TcItemDesc(mnemonic=item.name(),description=item.desc()),args=PackValue(args),config=PackValue({'Timeout':timeout}))
    except (ValueError, OverflowError, TypeError, SyntaxError) as error:
        raise DriverException('TC argument cannot be represented by the original driver schema') from error""").encode()
    source=replace(source,'from .value import *','from .value import *\nfrom .utctime import TIME')
    source=replace(source,'''    def __init__(self, name, value, format, radix = DEC, vtype = ENG, units = "" ):
        self.name = name
        self.value = ValueClass(value, format, radix, vtype, units )''','''    def __init__(self, name, value, format, radix = DEC, vtype = None, units = "" ):
        if type(units) is not str:
            raise SyntaxException("TC argument Units must be a string")
        # The absence of ValueType requests inference. An explicit value requests
        # an actual Python/SPELL cast, not only a driver metadata annotation.
        if vtype is None:
            inferred = {bool:BOOLEAN, int:LONG, float:FLOAT, str:STRING}
            if isinstance(value,TIME):
                vtype = DATETIME if value.isAbs() else RELTIME
            elif type(value) in inferred:
                vtype = inferred[type(value)]
            else:
                raise SyntaxException("Cannot infer TC argument type")
        else:
            try:
                if vtype == LONG:
                    value = int(value)
                elif vtype == FLOAT:
                    value = float(value)
                elif vtype == STRING:
                    value = str(value)
                elif vtype == BOOLEAN:
                    value = bool(value)
                elif vtype is TIME or vtype in (DATETIME,RELTIME):
                    value = TIME(value)
                    resolved = DATETIME if value.isAbs() else RELTIME
                    if vtype is not TIME and vtype != resolved:
                        raise ValueError("TC time kind differs from ValueType")
                    vtype = resolved
                else:
                    raise ValueError("Unknown TC argument ValueType")
            except Exception as error:
                raise SyntaxException("Failed casting TC argument",str(error)) from error
        self.name = name
        self.value = ValueClass(value, format, radix, vtype, units )
        # Original ValueClass re-infers only int/float/string. Preserve the
        # already resolved TC type, including bool and absolute/relative TIME.
        self.value.vtype(vtype)''')
    source=replace(source,'                vtype   = self.__extractConfig(argCfg,ValueType,LONG)',
        '''                if ValueType in argCfg and argCfg[ValueType] is None:
                    raise SyntaxException("TC argument ValueType cannot be None")
                vtype   = self.__extractConfig(argCfg,ValueType,None)''')
    return source.encode()


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    outputs={name:apply(name,(site/name).read_bytes()) for name in PREIMAGES}
    report={}
    for name,data in outputs.items():
        for label,raw in (('original',(site/name).read_bytes()),('patched',data)):
            target=evidence/label/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
        (site/name).write_bytes(data)
        report[name]=dict(preimage_sha256=PREIMAGES[name],sha256=hashlib.sha256(data).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__=='__main__':
    apply_tree(*sys.argv[1:])
