"""Sub-procedure coverage cannot drop priority, mode, arguments or visible source."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from flow_complete_report import MAP,LIBRARY,DIMENSIONS,component_checks


@pytest.fixture
def components():
    # Structural unit fixtures; qualification rereads actual retained native
    # artifacts with each independent component reviewer before this mapping.
    reports={}
    for name,file in (('execution','child_execution'),('returns','child_returns'),
                      ('policy','child_policy'),('arguments','child_arguments'),('start','child_start')):
        reports[name]=json.loads((ROOT/'conformance/evidence'/f'{file}.json').read_bytes())
    reports['library']=dict(checks={name:dict(passed=True) for group in LIBRARY.values() for name in group})
    reports['visibility']=dict(checks={'visible-source:'+d:dict(passed=True,dimension=d) for d in DIMENSIONS})
    for r in reports.values():r.update(passed=True,runtime_image='unit-test-only')
    return reports


def test_all_fifteen_open_flow_rows_are_mapped(components):
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and r['package']=='FLOW'}
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==15
    checks=component_checks(components)
    from check import supported_check
    roots={key:row for key,row in checks.items() if row['contracts']}
    assert len(roots)==60
    assert all(supported_check({'checks':checks},key,row['dimension']) for key,row in roots.items())


@pytest.mark.parametrize('defect',['priority','override','header','visible','hidden','arguments','load','manual','image'])
def test_required_child_behavior_is_not_optional(components,defect):
    changed=deepcopy(components)
    target={'priority':('library','configured-priority'),'override':('library','configured-override'),
        'header':('library','header-name'),'visible':('visibility','visible-source:positive'),
        'hidden':('visibility','visible-source:boundary'),'arguments':('arguments','arguments:failure'),
        'load':('start','automatic-True-blocking-True-failure'),
        'manual':('execution','modes/manual-blocking:positive')}
    if defect=='image':changed['visibility']['runtime_image']='different'
    else:
        kind,key=target[defect];changed[kind]['checks'][key]['passed']=False
    with pytest.raises(AssertionError):component_checks(changed)
