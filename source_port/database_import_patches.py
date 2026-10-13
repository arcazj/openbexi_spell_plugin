"""Restore typed original database imports. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/utils/vimport.py': 'f19bb2df486b8b5d9d2499b8175aaaf56233a9f669e19dfbca8235facf6f8ee7',
    'spell/lib/adapter/databases/dbfile.py': 'd3b3da232b938170f05e3158035f863df69ea448a1518ab448c18b8562d2c88a',
}


def apply(name, content):
    if name not in PREIMAGES or hashlib.sha256(content).hexdigest() != PREIMAGES[name]:
        raise ValueError('Unexpected original database importer: ' + name)
    text = content.decode('utf-8')
    if name.endswith('/vimport.py'):
        before = 'from spell.lib.exception import DriverException\n'
        assert text.count(before) == 1
        text = text.replace(before, '# ImportValue supplies os in its original trusted expression namespace.\n'
                                   '# Do not rely on another module exporting this standard-library name.\n'
                                   'import os\n' + before)
    else:
        before = 'with open(self._filename) as f:'
        assert text.count(before) == 1
        text = text.replace(before, 'with open(self._filename, encoding="utf-8") as f:')
    result = text.encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    changes = {name: ((site / name).read_bytes(), apply(name, (site / name).read_bytes())) for name in PREIMAGES}
    report = {}
    for name, (original, patched) in changes.items():
        for label, content in (('original', original), ('patched', patched)):
            output = evidence / label / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
        (site / name).write_bytes(patched)
        report[name] = dict(preimage=hashlib.sha256(original).hexdigest(), sha256=hashlib.sha256(patched).hexdigest())
    (evidence / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
