"""Reject diagnostic overlays and altered native observations as release evidence."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from legacy_compare_composed_report import CONTRACT, qualify


@pytest.fixture(scope='module')
def proof():
    report = json.loads((ROOT / 'conformance/evidence/legacy_compare_composed.json').read_bytes())
    return Path(report['raw']['path']), report['runtime_image']


def test_only_native_comparison_contract_is_qualified(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == [CONTRACT]
    assert set(report['checks']) == {'positive', 'boundary', 'failure', 'recovery'}
    assert report['regressions'] == 15
    assert 'Imported Python modules' in report['exclusions']
    assert not report['full_v05_accepted'] and not report['stable_v1_accepted']


@pytest.mark.parametrize('mutation', ['failure', 'missing', 'image', 'source', 'overlay', 'payload', 'stage', 'recipe'])
def test_unqualified_runtime_is_rejected(proof, tmp_path, mutation):
    path, image = proof
    raw = json.loads(path.read_bytes())
    shutil.copyfile(path.parent / 'workspace.tar', tmp_path / 'workspace.tar')
    if mutation == 'failure':
        raw['checks']['recovery']['passed'] = False
    elif mutation == 'missing':
        del raw['checks']['goto']
    elif mutation == 'image':
        raw['runtime_image'] = 'sha256:' + '0' * 64
    elif mutation == 'source':
        raw['checks']['positive']['source'] = 'assert 1 != 2'
    elif mutation == 'overlay':
        raw['runtime_sources']['overlay'] = {'unpackaged': True}
    elif mutation == 'payload':
        raw['runtime_sources']['installed']['spell_native/bin/libspell_executor313.so'] = '0' * 64
    elif mutation == 'stage':
        stages = raw['runtime_sources']['integrated']['manifest']['composition']['native']['stages']
        stages[:] = [row for row in stages if row['recipe'] != 'legacy_compare_patches.py']
    elif mutation == 'recipe':
        raw['runtime_sources']['integrated']['manifest']['composition']['native']['recipes']['legacy_compare_syntax.py']['sha256'] = '0' * 64
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(target, image)
