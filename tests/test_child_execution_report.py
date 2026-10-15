"""Execution-mode requirements must retain actual pause and parent timing proof."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from check import supported_check
from child_execution_report import CONTRACTS, qualify


@pytest.fixture(scope='module')
def proof():
    start = json.loads((ROOT / 'conformance/evidence/child_start.json').read_bytes())
    modes = json.loads((ROOT / 'conformance/evidence/prompt_controls.json').read_bytes())
    return Path(start['raw']['path']), Path(modes['raw']['modes']['path']), start['runtime_image']


def test_bounded_execution_clauses_have_independent_dimensions(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == CONTRACTS
    for contract in CONTRACTS:
        for dimension in ('positive', 'boundary', 'failure', 'recovery'):
            assert supported_check(report, contract + ':' + dimension, dimension)
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['ran-before-run', 'parent-blocked', 'late-error', 'missing-recovery'])
def test_execution_mapping_rejects_incorrect_observations(proof, tmp_path, mutation):
    start, modes, image = proof
    kind = 0 if mutation == 'missing-recovery' else 1
    original = (start, modes)[kind]
    report = json.loads(original.read_bytes())
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    args = [start, modes, image]
    args[kind] = target
    qualify(*args)
    if mutation == 'ran-before-run':
        row = next(r for r in report['checks']['manual-blocking']['observations'] if r['phase'] == 'before-manual-run')
        row['child_started'] = True
    elif mutation == 'parent-blocked':
        row = next(r for r in report['checks']['nonblocking-success']['observations'] if r['phase'] == 'child-awaiting-input')
        row['parent_returned'] = False
    elif mutation == 'late-error':
        report['checks']['nonblocking-late-error']['parent_result'] = {'exception': 'DriverException', 'rejected': False}
    else:
        del report['checks']['automatic-False-blocking-True-recovery']
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(*args)
