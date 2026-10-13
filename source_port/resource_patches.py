"""Checked original resource helper corrections. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lang/helpers/rschelper.py': 'bfbbca7fa7c79dac1c8b3f702e3350c63d0168f63d5f540c67a012c10aad055d',
    'spell/lib/adapter/resources.py': 'c33189285856245aaf0c530ec26c05306357ad9bc4aa860120131dfa2a2e8c15',
}


def apply(name, content):
    if name not in PREIMAGES or hashlib.sha256(content).hexdigest() != PREIMAGES[name]:
        raise ValueError('Unexpected original resource helper: ' + name)
    text = content.decode('utf-8')
    if name.endswith('/resources.py'):
        start = text.index('    def setResource(')
        end = text.index('    def _setResource(', start)
        section = text[start:end]
        before = 'self.buildConfig(args, kargs, self.getConfig(), INTERFACE_DEFAULTS)'
        assert section.count(before) == 1
        section = section.replace(before, 'self.buildConfig(args[:1] + args[2:], kargs, self.getConfig(), INTERFACE_DEFAULTS)')
        result = (text[:start] + section + text[end:]).encode('utf-8')
        compile(result, name, 'exec')
        return result
    start = text.index('class GetResource_Helper(')
    end = text.index('class GetResources_Helper(', start)
    section = text[start:end]
    assert section.count('        if result:\n') == 1
    section = section.replace('        if result:\n',
        '        # Driver errors or None mean unavailable; zero/False/empty are values.\n'
        '        if result is not None:\n')
    section = section.replace('if len(args)==0 or type(args[0])!=str:',
                              'if len(args)!=1 or type(args[0])!=str:')
    text = text[:start] + section + text[end:]
    start = text.index('class SetResource_Helper(')
    end = text.index('class GetResource_Helper(', start)
    section = text[start:end]
    marker = '    def _doOperation(self, *args, **kargs ):\n'
    assert section.count(marker) == 1
    section = section.replace(marker, '''    def configure(self, *args, **kargs):
        # The second positional argument is data, including dictionaries.
        # Only later positional dictionaries are modifier dictionaries.
        return WrapperHelper.configure(self, *(args[:1] + args[2:]), **kargs)

    def execute(self, *args, **kargs):
        # The generic wrapper consumes one trailing modifier dictionary.
        if len(args) == 2 and type(args[1]) is dict:
            args = args + ({},)
        return WrapperHelper.execute(self, *args, **kargs)

''' + marker)
    before = '        elif len(args)==1:\n            raise SyntaxException("Expected resource value")\n'
    assert section.count(before) == 1
    section = section.replace(before, before + '        elif len(args)!=2:\n            raise SyntaxException("Expected resource name and value only")\n')
    text = text[:start] + section + text[end:]
    result = text.encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    manifest_path = evidence / 'manifest.json'
    report = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in PREIMAGES:
        path = site / name
        original = path.read_bytes()
        patched = apply(name, original)
        for label, content in (('original', original), ('patched', patched)):
            output = evidence / label / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
        path.write_bytes(patched)
        report[name] = dict(preimage=hashlib.sha256(original).hexdigest(), sha256=hashlib.sha256(patched).hexdigest())
    manifest_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
