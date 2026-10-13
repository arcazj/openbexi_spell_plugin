"""Audit original integrated installation and exact typed/SCDB overlay chain."""
import hashlib
import importlib.util
import json
from pathlib import Path
from installed_provenance import capture as installed_capture


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture():
    root = Path(importlib.util.find_spec('spell_native').origin).parent
    if not Path('/opt/scdb-input/baseline-installed.json').exists():
        integrated = installed_capture()
        composition = integrated['manifest']['composition']['python']
        stages = [stage for stage in composition['stages'] if stage['recipe'] == 'scdb_patches.py']
        if len(stages) != 1:
            raise ValueError('Expected one checked SCDB composition stage')
        return dict(integrated=integrated, scdb_stage=stages[0])
    base = json.loads(Path('/opt/scdb-input/baseline-installed.json').read_bytes())
    assert sha((root/'manifest.json').read_bytes()) == base['manifest_sha256']
    importer_root = Path('/opt/database-import-patch')
    importer = json.loads((importer_root/'manifest.json').read_bytes())
    expected = dict(base['python_sources'])
    for name, row in importer.items():
        assert expected[name] == row['preimage']
        assert sha((importer_root/'original'/name).read_bytes()) == row['preimage']
        assert sha((importer_root/'patched'/name).read_bytes()) == row['sha256']
        expected[name] = row['sha256']
    patch_root = Path('/opt/scdb-patch')
    patch = json.loads((patch_root/'manifest.json').read_bytes()) if patch_root.exists() else None
    if patch:
        assert sha((patch_root/'scdb_patches.py').read_bytes()) == patch['recipe_sha256']
        for name, row in patch['sources'].items():
            assert expected[name] == row['ported_sha256']
            for label in ('original','ported','patched'):
                assert sha((patch_root/label/name).read_bytes()) == row[label+'_sha256']
            expected[name] = row['patched_sha256']
    for name, value in expected.items():
        assert sha((root.parent/name).read_bytes()) == value, name
    for name, value in base['native_artifacts'].items():
        assert sha((root/'bin'/name).read_bytes()) == value, name
    return dict(baseline=base, importer=importer, scdb=patch,
        import_recipe_sha256=sha(Path('/opt/scdb-input/database_import_patches.py').read_bytes()))
