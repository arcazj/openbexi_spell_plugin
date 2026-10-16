"""Shared modifiers cannot be accepted from only one of their service families."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from common_complete_report import MAP,DIMENSIONS,component_checks
from check import supported_check


@pytest.fixture
def components():
    # Structural fixtures only; qualify() obtains real fresh independent reviews.
    return {kind:dict(passed=True,runtime_image='unit-test-only',checks={
        dimension:dict(passed=True,dimension=dimension,oracle='Unit fixture') for dimension in DIMENSIONS})
        for kind in {kind for groups in MAP.values() for kind in groups}}


def test_all_seventeen_open_shared_contracts(components):
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and r['package']=='COMMON'}
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==17
    checks=component_checks(components);roots={k:r for k,r in checks.items() if r['contracts']}
    assert len(roots)==68
    assert all(supported_check({'checks':checks},k,r['dimension']) for k,r in roots.items())


@pytest.mark.parametrize('kind',sorted({kind for groups in MAP.values() for kind in groups}))
def test_every_native_family_is_required(components,kind):
    changed=deepcopy(components);changed[kind]['checks']['failure']['passed']=False
    with pytest.raises(AssertionError):component_checks(changed)


def test_missing_dimension_and_mixed_image_are_rejected(components):
    changed=deepcopy(components);del changed['extension']['checks']['recovery']
    with pytest.raises(AssertionError):component_checks(changed)
    components['ui']['runtime_image']='different'
    with pytest.raises(AssertionError):component_checks(components)
