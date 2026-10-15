"""Compile only the exact-preimage native comparison experiment."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import legacy_compare_patches as patch
from incremental_native import rebuild

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
output = Path('/legacy-compare-patch')
output.mkdir()
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
sources = {}
with zipfile.ZipFile(archive) as bundle:
    for name in patch.PREIMAGES:
        original = bundle.read(name)
        path = Path('/source') / name
        ported = path.read_bytes()
        patched = patch.apply(name, original, ported)
        sources[name] = {}
        for label, content in (('original', original), ('ported', ported), ('patched', patched)):
            target = output / label / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            sources[name][label + '_sha256'] = sha(target)
        path.write_bytes(patched)
for name in ('legacy_compare_patches.py', 'legacy_compare_syntax.py', 'legacy_compare_build.py', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent / name, output / name)
compiled = rebuild(list(sources), output / 'compiled')
report = dict(passed=True, sources=sources, recipes={p.name: sha(p) for p in output.glob('*.py')},
    artifacts={name: row['sha256'] for name, row in compiled['artifacts'].items()},
    original_artifacts={name: row['original_sha256'] for name, row in compiled['artifacts'].items()},
    incremental_build_sha256=sha(output/'compiled/incremental-build.json'),
    scope='Declared native diagnostic overlay; original installed RECORD retained; no release acceptance')
(output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
