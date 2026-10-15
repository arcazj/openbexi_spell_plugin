"""Return-clause qualification requires every observed load and execution outcome."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from check import supported_check
from child_return_report import CONTRACTS, qualify


@pytest.fixture(scope='module')
def proof():
    start = json.loads((ROOT / 'conformance/evidence/child_start.json').read_bytes())
    modes = json.loads((ROOT / 'conformance/evidence/prompt_controls.json').read_bytes())
    return Path(start['raw']['path']), Path(modes['raw']['modes']['path']), start['runtime_image']


def test_only_both_return_clauses_have_all_independent_dimensions(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == CONTRACTS
    assert len(report['checks']) == 21
    for dimension in ('positive', 'boundary', 'failure', 'recovery'):
        assert supported_check(report, 'return:' + dimension, dimension)
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['different-image', 'missing-failed-load', 'numeric-true', 'missing-parent-file'])
def test_return_qualification_rejects_incomplete_or_inconsistent_proof(proof, tmp_path, mutation):
    start, modes, image = proof
    kind = 0 if mutation == 'missing-failed-load' else 1
    original = (start, modes)[kind]
    report = json.loads(original.read_bytes())
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    args = [start, modes, image]
    args[kind] = target
    qualify(*args)
    if mutation == 'different-image':
        report['runtime_image'] = 'sha256:' + '0' * 64
    elif mutation == 'missing-failed-load':
        del report['checks']['automatic-False-blocking-False-failure']
    elif mutation == 'numeric-true':
        report['checks']['blocking-success']['parent_result']['returned'] = 1
    else:
        (tmp_path / 'workspace/blocking-success/parent-result.json').unlink()
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError, FileNotFoundError)):
        qualify(*args)
