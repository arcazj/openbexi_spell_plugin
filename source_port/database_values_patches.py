"""Keep LRM p83 legacy octal database values ahead of TIME/string fallback.

SPDX-License-Identifier: GPL-3.0-or-later
Apply after the existing database import and user-database corrections.
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {'spell/utils/vimport.py': '7555ba779eb3927869e6efe67b0f09d370be28443326ba31b3782dd91909736c'}


def apply(name, raw):
    if name not in PREIMAGES or hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Unexpected composed database value importer: ' + name)
    text = raw.decode('utf-8')
    before = "    if value == '':\n        return [value,None]\n    try:\n"
    after = """    if value == '':
        return [value,None]
    # LRM p83 retains Python-2-style octal in database files. CPython 3 rejects
    # this literal; recognize only the complete numeric token before the old
    # TIME/string fallback. Quoted strings, floats and expressions stay intact.
    if isinstance(orig_value, str):
        token = orig_value.strip()
        digits = token[1:] if token.startswith(('+', '-')) else token
        if len(digits) > 1 and digits[0] == '0' and all(c in '01234567' for c in digits):
            return [int(token, 8), OCT]
    try:
"""
    if text.count(before) != 1:
        raise ValueError('Database value import anchor differs')
    result = text.replace(before, after).encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    changes = {name: ((site / name).read_bytes(), apply(name, (site / name).read_bytes()))
               for name in PREIMAGES}
    manifest = {}
    for name, (original, patched) in changes.items():
        for label, content in (('original', original), ('patched', patched)):
            target = evidence / label / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (site / name).write_bytes(patched)
        manifest[name] = {'preimage_sha256': PREIMAGES[name], 'sha256': hashlib.sha256(patched).hexdigest()}
    (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
