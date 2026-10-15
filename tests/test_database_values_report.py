"""The diagnostic overlay must retain its source and native persistence evidence."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from database_values_report import qualify


@pytest.fixture(scope='module')
def proof():
    record = json.loads((ROOT / 'conformance/evidence/database_values.json').read_bytes())
    return (Path(record['raw']['values']['path']), Path(record['raw']['user']['path']),
            Path(record['build']['path']))


def test_diagnostic_pass_does_not_promote_an_overlaid_artifact(proof):
    report = qualify(*proof)
    assert report['passed_checks'] == {'values_and_import': 24, 'user_persistence': 20, 'user_prompts': 2}
    assert report['qualified_contracts'] == []
    assert report['source']['name'] == 'spell/utils/vimport.py'
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['failed', 'missing-regression', 'image', 'recipe', 'payload', 'prompt'])
def test_altered_diagnostic_observations_are_rejected(proof, tmp_path, mutation):
    index = 1 if mutation == 'prompt' else 0
    original = proof[index]
    report = json.loads(original.read_bytes())
    shutil.copyfile(original.parent / 'workspace.tar', tmp_path / 'workspace.tar')
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    args = list(proof)
    args[index] = target
    qualify(*args)
    if mutation == 'failed':
        report['checks']['octal-values']['passed'] = False
    elif mutation == 'missing-regression':
        del report['checks']['regression-ground:recovery']
    elif mutation == 'image':
        report['runtime_image'] = report['runtime_sources']['profile']
    elif mutation == 'recipe':
        report['runtime_sources']['overlay']['files']['database_values_patches.py'] = '0' * 64
    elif mutation == 'payload':
        report['runtime_sources']['installed']['spell/utils/vimport.py'] = '0' * 64
    else:
        report['prompts']['prompt-abort']['files']['existing.IMP'] = 'OVERWRITTEN'
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(*args)
