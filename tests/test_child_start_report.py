"""Failed-start proof must retain the observed child and parent lifecycle."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from child_start_report import qualify


@pytest.fixture(scope='module')
def proof():
    record = json.loads((ROOT / 'conformance/evidence/child_start.json').read_bytes())
    return Path(record['raw']['path']), record['runtime_image']


def test_all_four_modes_reject_failed_loads_then_recover(proof):
    report = qualify(*proof)
    assert len(report['checks']) == 8 and report['qualified_contracts'] == []
    assert report['passed'] and not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['missing', 'failed', 'image', 'host', 'source',
    'exception', 'boolean', 'child-state', 'open-mode', 'manual-started', 'early-return',
    'lost-child', 'events', 'cleanup'])
def test_altered_startup_observations_are_rejected(proof, tmp_path, mutation):
    original, image = proof
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    report = json.loads(original.read_bytes())
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    qualify(target, image)
    name = 'automatic-False-blocking-True-recovery'
    row = report['checks'][name]
    if mutation == 'missing':
        del report['checks'][name]
    elif mutation == 'failed':
        row['passed'] = False
    elif mutation == 'image':
        report['runtime_image'] = 'sha256:' + '0' * 64
    elif mutation == 'host':
        report['host_inputs'] = {}
    elif mutation == 'source':
        (tmp_path / 'workspace' / name / 'main.py').write_text('pass\n')
    elif mutation == 'exception':
        row['rejection']['exception'] = 'TypeError'
    elif mutation == 'boolean':
        row['result']['returned'] = 1
    elif mutation == 'child-state':
        row['child_status'] = 'ERROR'
    elif mutation == 'open-mode':
        row['child_info']['OpenMode'] = '{Automatic:True,Visible:True,Blocking:True}'
    elif mutation == 'manual-started':
        row['observations'][0]['child_finished'] = True
    elif mutation == 'early-return':
        row['observations'][0]['parent_returned'] = True
    elif mutation == 'lost-child':
        row['inventory']['ExecutorList'] = row['parent_instance']
    elif mutation == 'events':
        (tmp_path / 'workspace' / name / 'events.json').write_text('[]')
    else:
        row['cleanup_error'] = 'Unreaped process'
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(target, image)
