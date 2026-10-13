"""Integrate checked UI and FLOW patches into one executor singleton library."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import flow_patches
import ui_native_patches
from incremental_native import rebuild

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = Path('/combined-native-patch')
output.mkdir()
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
names = sorted([ui_native_patches.SOURCE, *flow_patches.PREIMAGES])
records = {}
with zipfile.ZipFile(archive) as bundle:
    for name in names:
        original = bundle.read(name)
        source = Path('/source') / name
        ported = source.read_bytes()
        records[name] = {}
        for label, content in (('original', original), ('ported', ported)):
            path = output / label / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            records[name][label] = sha(path)
        if name == ui_native_patches.SOURCE:
            source.write_bytes(ui_native_patches.apply(name, original, ported))
flow_patches.apply_tree('/source', output / 'flow-source-patches.json')
for name in names:
    path = output / 'patched' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path('/source') / name, path)
    records[name]['patched'] = sha(path)
for name in ('ui_native_patches.py', 'flow_patches.py', 'flow_analyze.py',
             'combined_native_build.py', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent / name, output / name)
result = rebuild(names, output / 'compiled')
manifest = {'archive_sha256': sha(archive), 'source_hashes': records,
            'recipes': {p.name: sha(p) for p in output.glob('*.py')},
            'artifacts': {name: row['sha256'] for name, row in result['artifacts'].items()},
            'profile': 'Integrated UI/FLOW native overlay on DATA runtime; not release acceptance'}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
