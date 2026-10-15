"""Checked ranging helper corrections and RNG-only local policy filtering.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES={
    'spell/lang/helpers/rnghelper.py':'8a892776f286c2cc3230d45bebd871da39dca3e4d67ee4af1093afd1b1c09a61',
    'openbexi_dss_proxy/ranging.py':'7c962da4fae3a08d5b13d7a7ab72573b3061196c8be1d123258ded6aece1937a',
}


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:
        raise ValueError('Unexpected ranging source preimage: '+name)
    source=raw.decode('utf-8')
    if name=='spell/lang/helpers/rnghelper.py':
        for helper,following in (('EnableRanging','DisableRanging'),('DisableRanging','StartRanging')):
            start=source.index('class '+helper+'_Helper(')
            end=source.index('class '+following+'_Helper(',start)
            section=source[start:end]
            before='    def _doPreOperation(self, *args, **kargs):\n        pass\n'
            assert section.count(before)==1
            section=section.replace(before,
                '    def _doPreOperation(self, *args, **kargs):\n'
                '        # WrapperHelper already consumed a trailing modifier dictionary.\n'
                '        # LRM 2.4.4 p93: schedule enable/disable takes no names.\n'
                '        if len(args)!=0:\n'
                '            raise SyntaxException("Expected no arguments")\n')
            source=source[:start]+section+source[end:]
        before="REGISTRY['RNG'].startRangingCalibration("
        assert source.count(before)==1
        source=source.replace(before,"REGISTRY['RNG'].startCalibration(")
    else:
        before='from .common import settings\n'
        assert source.count(before)==1
        source=source.replace(before,'''from .common import settings
from spell.lib.exception import DriverException


def ranging_settings(config):
    # WrapperHelper owns interruption policy; no ground option is implied.
    config=dict(config or {})
    if 'AllowInterrupt' in config:
        if type(config.pop('AllowInterrupt')) is not bool:
            raise DriverException('AllowInterrupt must be a boolean')
    return settings(config)
''')
        start=source.index('class Ranging(')
        section=source[start:]
        assert section.count('settings(config)')==12
        source=source[:start]+section.replace('settings(config)','ranging_settings(config)')
    result=source.encode('utf-8')
    compile(result,name,'exec')
    return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence)
    result={}
    for name,expected in PREIMAGES.items():
        target=site/name
        original=target.read_bytes()
        patched=apply(name,original)
        for label,content in (('original',original),('patched',patched)):
            retained=evidence/label/name
            retained.parent.mkdir(parents=True,exist_ok=True)
            retained.write_bytes(content)
        target.write_bytes(patched)
        result[name]=dict(preimage_sha256=expected,sha256=hashlib.sha256(patched).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    apply_tree(sys.argv[1],sys.argv[2])
