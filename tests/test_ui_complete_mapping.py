"""Full UI qualification cannot omit native event, prompt or resource behavior."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from ui_complete_report import MAP,DIMENSIONS,component_checks
from check import supported_check


@pytest.fixture
def components():
    # Retained reports are structural fixtures only. Actual qualification reruns
    # their independent reviewers against a single final image and source tree.
    reports={name:json.loads((ROOT/'conformance/evidence'/f'{file}.json').read_bytes())
        for name,file in (('ui','ui'),('timed','prompt_timeout'),('event','events'),('resource','resource'),('flow','flow'))}
    reports['complete']=dict(checks={feature+':'+dimension:dict(passed=True,dimension=dimension)
        for feature in ('empty-default','typed-default','reminder') for dimension in DIMENSIONS})
    for report in reports.values():report.update(passed=True,runtime_image='unit-test-only')
    return reports


def test_eight_ui_rows_exclude_separately_reviewed_ranging_error(components):
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and r['package']=='UI'}
    expected.remove('CMP-LRM244-CONSTANT-RANGING-STATE-ERROR')
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==8
    checks=component_checks(components);roots={k:r for k,r in checks.items() if r['contracts']}
    assert len(roots)==32
    assert all(supported_check({'checks':checks},k,r['dimension']) for k,r in roots.items())


@pytest.mark.parametrize('defect',['event','reminder','empty','typed','severity','resource','missing','image'])
def test_missing_or_failed_component_prevents_ui_acceptance(components,defect):
    changed=deepcopy(components)
    target={'event':('event','event:boundary'),'reminder':('complete','reminder:positive'),
        'empty':('complete','empty-default:recovery'),'typed':('complete','typed-default:failure'),
        'severity':('flow','user-action:failure')}
    if defect=='image':changed['complete']['runtime_image']='another-image'
    elif defect=='missing':del changed['complete']['checks']['reminder:positive']
    elif defect=='resource':next(iter(changed['resource']['checks'].values()))['passed']=False
    else:
        report,key=target[defect];changed[report]['checks'][key]['passed']=False
    with pytest.raises((AssertionError,KeyError)):component_checks(changed)
