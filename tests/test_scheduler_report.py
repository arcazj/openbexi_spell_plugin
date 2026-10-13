"""Observation references cannot weaken the generic check-dependency gate."""
import copy
from pathlib import Path
import runpy
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from scheduler_report import qualify_observation

supported_check = runpy.run_path(str(ROOT / 'conformance/check.py'))['supported_check']


def fixture():
    name = 'until-positive'
    spec = {'contracts': ['CMP-LRM244-MODIFIER-UNTIL'], 'dimension': 'positive'}
    check = dict(spec, passed=True, oracle='Independent native scheduler observation',
                 dependencies=[name])
    observations = {name: {'passed': True, 'status': 'FINISHED', 'asrun': 'actual trace'}}
    return name, check, observations, spec


def test_only_validated_scenario_reference_becomes_observation_dependency():
    name, check, observations, spec = fixture()
    raw = copy.deepcopy(check)
    with pytest.raises(ValueError, match='Cyclic'):
        supported_check({'checks': {name: raw}}, name, 'positive')
    qualify_observation(name, check, observations, spec)
    assert check['observation_dependencies'] == [name]
    assert 'dependencies' not in check
    assert raw['dependencies'] == [name]
    assert supported_check({'checks': {name: check}}, name, 'positive')


@pytest.mark.parametrize('change', [
    'missing', 'failed', 'unfinished', 'no_trace', 'unknown_reference',
    'additional_reference', 'empty_reference', 'string_reference',
    'ambiguous_reference', 'wrong_contract', 'wrong_dimension',
])
def test_invalid_observation_or_reference_is_rejected_without_conversion(change):
    name, check, observations, spec = fixture()
    if change == 'missing':
        observations.clear()
    elif change == 'failed':
        observations[name]['passed'] = False
    elif change == 'unfinished':
        observations[name]['status'] = 'RUNNING'
    elif change == 'no_trace':
        observations[name]['asrun'] = ''
    elif change == 'unknown_reference':
        check['dependencies'] = ['unknown']
    elif change == 'additional_reference':
        check['dependencies'].append('other')
    elif change == 'empty_reference':
        check['dependencies'] = []
    elif change == 'string_reference':
        check['dependencies'] = name
    elif change == 'ambiguous_reference':
        check['observation_dependencies'] = [name]
    elif change == 'wrong_contract':
        check['contracts'] = ['different-contract']
    else:
        check['dimension'] = 'failure'
    before = copy.deepcopy(check)
    with pytest.raises(AssertionError):
        qualify_observation(name, check, observations, spec)
    assert check == before
