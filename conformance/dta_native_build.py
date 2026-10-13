"""Relink one original executor graph with DTA plus retained UI/FLOW changes."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import dta_native_patches
import dta_time_patches
import data_files_native_patches
import flow_patches
import ui_native_patches
from incremental_native import rebuild

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = Path('/dta-native-patch')
output.mkdir()
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
names = sorted([dta_native_patches.SOURCE, data_files_native_patches.NAME, ui_native_patches.SOURCE,
                *flow_patches.PREIMAGES, *dta_time_patches.PREIMAGES])
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
        for recipe in (dta_native_patches, ui_native_patches):
            if name == recipe.SOURCE:
                source.write_bytes(recipe.apply(name, original, ported))
        if name in dta_time_patches.PREIMAGES:
            source.write_bytes(dta_time_patches.apply(name, original, ported))
        if name == data_files_native_patches.NAME:
            source.write_bytes(data_files_native_patches.apply(original, ported))
flow_patches.apply_tree('/source', output / 'flow-source-patches.json')
for name in names:
    path = output / 'patched' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path('/source') / name, path)
    records[name]['patched'] = sha(path)
for name in ('dta_native_patches.py', 'dta_time_patches.py', 'data_files_native_patches.py',
             'ui_native_patches.py', 'flow_patches.py', 'flow_analyze.py',
             'dta_native_build.py', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent / name, output / name)
try:
    result = rebuild(names, output / 'compiled')
except Exception:
    for log in (output / 'compiled').glob('*.log'):
        print(log.name, log.read_text()[-12000:])
    raise
manifest = {'archive_sha256': sha(archive), 'source_hashes': records,
            'recipes': {path.name: sha(path) for path in output.glob('*.py')},
            'artifacts': {name: row['sha256'] for name, row in result['artifacts'].items()},
            'profile': 'Integrated DTA/UI/FLOW native overlay; original DATA context and Python overlays retained; not release acceptance'}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
