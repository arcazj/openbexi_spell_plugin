"""Startup evidence must refer to the packaged fix and actual procedure effects."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from context_snapshot_composed_report import qualify


@pytest.fixture(scope='module')
def proof():
    report = json.loads((ROOT / 'conformance/evidence/context_snapshot_composed.json').read_bytes())
    return Path(report['raw']['path']), report['runtime_image']


def test_fresh_installed_listener_retains_startup_controls(proof):
    report = qualify(*proof)
    assert report['passed'] and len(report['checks']) == 40 and report['qualified_contracts'] == []


@pytest.mark.parametrize('change', ['failed', 'missing', 'runtime', 'stage', 'recipe', 'overlay'])
def test_unqualified_startup_evidence_is_rejected(proof, tmp_path, change):
    original, image = proof
    raw = json.loads(original.read_bytes())
    shutil.copyfile(original.parent / 'workspace.tar', tmp_path / 'workspace.tar')
    if change == 'failed':
        raw['checks']['startup-000']['passed'] = False
    elif change == 'missing':
        del raw['checks']['startup-039']
    elif change == 'runtime':
        raw['runtime_image'] = 'sha256:' + '0' * 64
    elif change == 'stage':
        rows = raw['runtime_sources']['manifest']['composition']['native']['stages']
        rows[:] = [row for row in rows if row['recipe'] != 'context_snapshot_patches.py']
    elif change == 'recipe':
        raw['runtime_sources']['manifest']['composition']['native']['recipes']['context_snapshot_patches.py']['sha256'] = '0' * 64
    else:
        raw['runtime_sources']['context_snapshot_overlay'] = {'diagnostic': True}
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(path, image)
