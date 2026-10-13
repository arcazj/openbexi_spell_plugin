"""Checked LIMIT corrections applied after the frozen OBS composition.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys


PREIMAGES = {
    'spell/lang/helpers/limhelper.py': 'b846e59244b2649dad12d4294ddfee8817528e2dcc5bfee8cdb3c9ee0d85b511',
    'spell/lang/helpers/tmhelper.py': '04e6c2fec2cca7b71c10fd9158b19eba154a89fb49d23e9560c89ceb76b2c544',
    'openbexi_dss_proxy/tm.py': '468dc9ca3bd1a1646e97905f8fe6ee85e2c64427ed24e72b3b0cb455089d5aa8',
}


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('LIMIT patch occurrence count changed: ' + old[:100])
    return source.replace(old, new)


def apply(name, raw):
    if name not in PREIMAGES:
        return raw
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('LIMIT patch preimage changed: ' + name)
    source = raw.decode()
    if name.endswith('/limhelper.py'):
        for class_name, following in (('GetLimits_Helper', 'IsAlarmed_Helper'), ('IsAlarmed_Helper', 'EnableAlarm_Helper')):
            start = source.index('class ' + class_name)
            end = source.index('\nclass ', start + 6)
            body = source[start:end]
            body = replace(body, 'if len(args)==0:', 'if len(args)!=1:')
            source = source[:start] + body + source[end:]
        start = source.index('class RestoreNormalLimits_Helper')
        end = source.index('\nclass ', start + 6)
        body = source[start:end]
        body = replace(body, '        # Store information for possible failures',
            '        if args:\n            raise SyntaxException("RestoreNormalLimits takes no positional arguments")\n\n        # Store information for possible failures')
        body = replace(body, "REGISTRY['TM'].restoreNormalLimits()", "REGISTRY['TM'].restoreNormalLimits(config=self.getConfig())")
        source = source[:start] + body + source[end:]
        source = replace(source, '                limits = limitValues',
            '                from copy import deepcopy\n                limits = deepcopy(limitValues)')
        source = replace(source, '            definition = self.getConfig(Definition)',
            '            from copy import deepcopy\n            definition = deepcopy(self.getConfig(Definition))')
        source = replace(source, '        if not (bParameters ^ bDefinition ^ bLimits ^ bBackwardDef ^ bBackwardExp):',
            '        if sum((bParameters, bDefinition, bLimits, bBackwardDef, bBackwardExp)) != 1:')
    elif name.endswith('/tmhelper.py'):
        start = source.index('class SetGroundParameter_Helper')
        end = source.index('\nclass ', start + 6)
        body = source[start:end]
        body = replace(body, '        if len(args)==0:\n            raise SyntaxException("No parameters given")',
            '''        if len(args) not in (1, 2):
            raise SyntaxException("SetGroundParameter expects a name and value or an injection list")
        if len(args) == 2 and type(args[0]) is not str:
            raise SyntaxException("Ground parameter name must be a string")
        if len(args) == 1 and (type(args[0]) is not list or not args[0]
                or any(type(row) not in (list, tuple) or len(row) != 2
                       or type(row[0]) is not str for row in args[0])):
            raise SyntaxException("Expected a nonempty list of name/value pairs")''')
        source = source[:start] + body + source[end:]
    else:
        start = source.index('    def _setLimits(')
        end = source.index('    def _isAlarmed(', start)
        source = source[:start] + '''    def _setLimits(self,item,config):
        from .limit_support import set_limits
        validate_settings(config, ('Definition','Limits','Select','Type','LoRed','LoYel','HiYel','HiRed','Midpoint'))
        return set_limits(item, config)

    def _getLimits(self,item,config):
        from .limit_support import get_limits
        validate_settings(config, ('Select','Value'))
        return get_limits(item, config)

''' + source[end:]
        source = replace(source, "        fmt = (config or {}).get('ValueFormat','Eng format')", """        fmt = (config or {}).get('ValueFormat','Eng format')
        if fmt not in ('Raw format', 'Eng format', 'Default format'):
            raise DriverException('Unknown injection ValueFormat')""")
        source = replace(source,
            "            numeric = Decimal(str(value)) / Decimal(str(scale)) if fmt != 'Raw format' else Decimal(str(value))",
            """            from decimal import InvalidOperation
            try:
                numeric = Decimal(str(value)) / Decimal(str(scale)) if fmt != 'Raw format' else Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError, OverflowError) as error:
                raise DriverException('Injection requires a finite numeric value') from error""")
        source = replace(source, """        return call('TM','InjectItem',p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()),rawValue=PackValue(raw),
            engValue=PackValue(eng),validity=True,timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))).value""",
            """        try:
            request = p.TmItemValue(item=p.TmItemDesc(mnemonic=item.name()),rawValue=PackValue(raw),
                engValue=PackValue(eng),validity=True,timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))
        except (ValueError, OverflowError, TypeError, SyntaxError) as error:
            raise DriverException('Injection cannot be represented by the original driver schema') from error
        return call('TM','InjectItem',request).value""")
    return source.encode()


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    # Validate every preimage before any write; never partially apply a mismatch.
    outputs = {name: apply(name, (site / name).read_bytes()) for name in PREIMAGES}
    report = {}
    for name, data in outputs.items():
        for stage, content in (('original', (site / name).read_bytes()), ('patched', data)):
            target = evidence / stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (site / name).write_bytes(data)
        report[name] = dict(preimage_sha256=PREIMAGES[name], sha256=hashlib.sha256(data).hexdigest())
    (evidence / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    apply_tree(sys.argv[1], sys.argv[2])
