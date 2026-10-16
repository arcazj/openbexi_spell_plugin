"""Reject child-policy claims without exact native effects and observations."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from check import DIMENSIONS, supported_check
from child_policy_report import CONTRACTS, qualify, verify_policy


@pytest.fixture(scope='module')
def proof():
    report = json.loads((ROOT / 'conformance/evidence/child_policy.json').read_bytes())
    return [Path(report['raw'][name]['path']) for name in ('policy', 'start', 'modes')] + [report['runtime_image']]


def test_blocking_policy_retains_failure_and_recovery(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == CONTRACTS and report['native_controls'] == 25
    for contract in CONTRACTS:
        for dimension in DIMENSIONS:
            assert supported_check(report, contract + ':' + dimension, dimension)
    assert not report['full_v05_accepted']


@pytest.mark.parametrize('change', ['missing', 'failed', 'early-return', 'replayed', 'cancel-value', 'no-recovery'])
def test_incorrect_policy_observations_are_rejected(proof, tmp_path, change):
    original, _, _, image = proof
    raw = json.loads(original.read_bytes())
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    if change == 'missing':
        del raw['checks']['aborted-abort']
    elif change == 'failed':
        raw['checks']['error-cancel']['passed'] = False
    elif change == 'early-return':
        raw['checks']['error-skip']['held'][0]['parent_returned'] = True
    elif change == 'replayed':
        raw['checks']['error-repeat']['attempts'] = 3
    elif change == 'cancel-value':
        raw['checks']['aborted-cancel']['result']['returned'] = True
    else:
        (tmp_path / 'workspace/error-repeat/recovery-completed.txt').write_text('not finished')
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        verify_policy(path, image)
