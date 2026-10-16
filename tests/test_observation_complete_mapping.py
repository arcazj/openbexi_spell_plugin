"""Whole telemetry clauses cannot omit faults, policies or native wait controls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from observation_complete_report import MAP,DIMENSIONS,component_checks
from telemetry_features_cases import CASES as TELEMETRY
from telemetry_policy_cases import CASES as POLICY
from limit_features_cases import CASES as LIMITS


@pytest.fixture
def components():
    # Structural test fixtures only; the qualification entry point independently
    # reviews retained native reports before calling this dependency assembler.
    reports={}
    for name,file in (('obs','obs'),('timing','timing'),('controls','wait_control'),
                      ('intervals','wait_interval'),('times','wait_time'),('scheduler','scheduler')):
        reports[name]=json.loads((ROOT/'conformance/evidence'/f'{file}.json').read_bytes())
    for name,catalog in (('telemetry',TELEMETRY),('policy',POLICY),('limits',LIMITS)):
        reports[name]=dict(passed=True,checks={key:dict(passed=True,dimension=spec['dimension'])
            for key,spec in catalog.items()})
    for report in reports.values():report['runtime_image']='unit-test-only'
    return reports


def test_exactly_all_sixteen_remaining_observation_rows(components):
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and r['package']=='OBS'}
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==16
    checks=component_checks(components)
    from check import supported_check
    roots={key:row for key,row in checks.items() if row['contracts']}
    assert len(roots)==64
    assert all(supported_check({'checks':checks},key,row['dimension']) for key,row in roots.items())


@pytest.mark.parametrize('defect',['quality','prompt','minute','printed','between','wait-delay',
    'interrupt','interval','all-limits','image','dimension'])
def test_required_behavior_cannot_disappear(components,defect):
    changed=deepcopy(components)
    targets={'quality':('telemetry','quality:failure'),'prompt':('policy','failure-policy:recovery'),
        'minute':('telemetry','minute:positive'),'printed':('telemetry','printed:failure'),
        'between':('telemetry','between-list:boundary'),'wait-delay':('timing','waitfor-delay:failure'),
        'interrupt':('controls','telemetry:step:recovery'),'interval':('intervals','simple:positive'),
        'all-limits':('limits','selectors:boundary')}
    if defect=='image':changed['telemetry']['runtime_image']='another-image'
    elif defect=='dimension':changed['policy']['checks']['failure-policy:positive']['dimension']='wrong'
    else:
        report,key=targets[defect];changed[report]['checks'][key]['passed']=False
    with pytest.raises(AssertionError):component_checks(changed)
