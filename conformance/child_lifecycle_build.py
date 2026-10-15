"""Build the preimage-checked native child lifecycle units."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import child_lifecycle_patches as patch
from incremental_native import rebuild

output = Path('/child-lifecycle-patch')
output.mkdir()
archive = Path('/input/SPELL2.6.10-src.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
sources = {}
with zipfile.ZipFile(archive) as bundle:
    for name in patch.PREIMAGES:
        original = bundle.read(name)
        path = Path('/source')/name
        ported = path.read_bytes()
        patched = patch.apply(name, original, ported)
        hashes = {}
        for label, raw in (('original', original), ('ported', ported), ('patched', patched)):
            target = output/label/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            hashes[label+'_sha256'] = hashlib.sha256(raw).hexdigest()
        sources[name] = hashes
        path.write_bytes(patched)
for name in ('child_lifecycle_patches.py', 'child_lifecycle_build.py', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent/name, output/name)
result = rebuild(list(sources), output/'compiled')
report = dict(mode='child-lifecycle', sources=sources,
    recipes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.py')},
    artifacts={name: row['sha256'] for name, row in result['artifacts'].items()},
    original_artifacts={name: row['original_sha256'] for name, row in result['artifacts'].items()},
    limitation='Diagnostic native overlay; original installed RECORD retained. Fresh composed distribution and complete qualification remain separate.')
(output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
