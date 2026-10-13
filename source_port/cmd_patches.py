"""Checked original command corrections, retaining original source and notices.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lang/helpers/tchelper.py': '3475464cbdc955e0321f77c54d50cc6ba99d94fa8248e1ff2772828f3840e6dd',
    'spell/lib/adapter/tc_item.py': '63c573d9c7f279a3bfc288db67acaec0afaa117e413922c231d4e57a0aa3cf64',
}


def replace(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old,new)


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    manifest = {}
    for name, expected in PREIMAGES.items():
        path = site/name
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, name
        original = evidence/'original'/name
        original.parent.mkdir(parents=True,exist_ok=True)
        original.write_bytes(raw)
        source = raw.decode()
        if name.endswith('tchelper.py'):
            source = replace(source,'                    if type(self._cmdDef)!=list:',
                '                    if type(self._cmdDef)!=list or not self._cmdDef:')
            source = replace(source,'        # Obtain the string representation of the entity being sent',
                '''            self._cmdDef = cpy

        # Obtain the string representation of the entity being sent''')
            source = replace(source,'        # 1. Obtain the command/sequence',
                '''        # Lowercase group is the structural keyword, not the Group modifier.
        self.delConfig('group')
        # 1. Obtain the command/sequence''')
            source = replace(source,'                tcIsSuccess = REGISTRY[\'TC\'].send(self._cmdDef, config = self.getConfig() )',
                '''                tcIsSuccess = REGISTRY['TC'].send(self._cmdDef, config = self.getConfig() )
                if not tcIsSuccess:
                    raise DriverException("Command execution failed")''')
            source = replace(source,'        self._obtainCommandArguments(*args,**kargs)\n        # Store information for possible failures',
                '''        self._obtainCommandArguments(*args,**kargs)
        if type(self._tcArguments) is not list:
            raise SyntaxException("Expected a list of command arguments")
        for argument in self._tcArguments:
            if (type(argument) is not list or len(argument) not in (2,3)
                    or type(argument[0]) is not str or not argument[0]
                    or (len(argument) == 3 and type(argument[2]) is not dict)):
                raise SyntaxException("Malformed TC argument")
        # Store information for possible failures''')
        else:
            source = replace(source,'from spell.lang.modifiers import *',
                'from spell.lang.modifiers import *\nfrom spell.lib.exception import SyntaxException')
            source = replace(source,'    def __setitem__(self, name, descList):\n',
                '''    def __setitem__(self, name, descList):
        if (type(name) is not str or not name
                or (type(descList) is list and (len(descList) not in (1,2)
                    or (len(descList) == 2 and type(descList[1]) is not dict)))):
            raise SyntaxException("Malformed TC argument")
''')
            source = replace(source,'                if not type(descList[1]==dict):',
                '                if type(descList[1]) is not dict:')
        patched = source.encode()
        path.write_bytes(patched)
        saved = evidence/'patched'/name
        saved.parent.mkdir(parents=True,exist_ok=True)
        saved.write_bytes(patched)
        manifest[name] = {'original_sha256':expected,'sha256':hashlib.sha256(patched).hexdigest()}
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return manifest


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
