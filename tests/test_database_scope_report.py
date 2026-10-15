"""The p79 resolution requires native SCDB evidence, not built-in migration tests."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from database_scope_report import CONTRACT, qualify


@pytest.fixture(scope='module')
def proof():
    record = json.loads((ROOT / 'conformance/evidence/database_scope.json').read_bytes())
    return Path(record['raw']['path']), record['runtime_image']


def test_page79_qualifies_only_the_original_scdb_existence_method(proof):
    result = qualify(*proof)
    assert result['qualified_contracts'] == [CONTRACT]
    assert len(result['checks']) == 4
    assert result['manual_resolution']['documented_callable'] == 'SCDB.has_key'
    assert result['manual_resolution']['builtin_dict_has_key_supported'] is False
    assert not result['full_v05_accepted'] and not result['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['failed', 'missing', 'runtime', 'source', 'type', 'legacy-migration', 'archive'])
def test_changed_database_evidence_is_rejected(proof, tmp_path, mutation):
    original, image = proof
    row = json.loads(original.read_bytes())
    target = tmp_path / 'result.json'
    shutil.copyfile(original.parent / 'workspace.tar', tmp_path / 'workspace.tar')
    # Prove this relocated fixture qualifies before changing one observation.
    target.write_text(json.dumps(row), encoding='utf-8')
    qualify(target, image)
    key = 'spacecraft-existence:positive'
    if mutation == 'failed':
        row['checks'][key]['passed'] = False
    elif mutation == 'missing':
        del row['checks']['spacecraft-existence:recovery']
    elif mutation == 'runtime':
        row['runtime_image'] = 'sha256:' + '0' * 64
    elif mutation == 'source':
        row['checks'][key]['source'] = 'assert True'
    elif mutation == 'type':
        row['runtime_sources']['installed']['spell/lib/adapter/databases/dbfile.py'] = '0' * 64
    elif mutation == 'legacy-migration':
        row['checks'][key]['source'] = "assert 'Spacecraft_Name' in {'Spacecraft_Name': None}"
    else:
        (tmp_path / 'workspace.tar').write_bytes(b'altered archive')
    target.write_text(json.dumps(row), encoding='utf-8')
    import tarfile
    with pytest.raises((AssertionError, ValueError, tarfile.ReadError)):
        qualify(target, image)
