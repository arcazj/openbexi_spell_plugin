"""Build a checked original CIF prompt patch without changing accepted images."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from ui_native_patches import SOURCE, apply
from incremental_native import rebuild

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = Path('/ui-native-patch')
output.mkdir()
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
with zipfile.ZipFile(archive) as bundle:
    original = bundle.read(SOURCE)
source = Path('/source') / SOURCE
ported = source.read_bytes()
patched = apply(SOURCE, original, ported)
records = {}
for label, content in (('original', original), ('ported', ported), ('patched', patched)):
    path = output / label / SOURCE
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    records[label] = sha(path)
for name in ('ui_native_patches.py', 'ui_native_build.py', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent / name, output / name)
source.write_bytes(patched)
result = rebuild([SOURCE], output / 'compiled')
manifest = {'archive_sha256': sha(archive), 'source': SOURCE, 'source_hashes': records,
            'recipes': {p.name: sha(p) for p in output.glob('*.py')},
            'artifacts': {name: row['sha256'] for name, row in result['artifacts'].items()},
            'profile': 'Native UI conformance overlay; complete qualification remains separate'}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
