"""Full command qualification cannot omit an argument or composed Send dimension."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from command_complete_report import MAP,component_checks


@pytest.fixture
def components():
    # Structural dependency tests. qualify() obtains these components by
    # independently reviewing fresh native evidence on one immutable image.
    names=dict(command='cmd',features='command_display_composed',verification='send_verify',
        timing='timing',complete='send_complete_review',arguments='child_arguments',observation='obs')
    reports={key:json.loads((ROOT/'conformance/evidence'/f'{name}.json').read_bytes()) for key,name in names.items()}
    for report in reports.values():report['runtime_image']='unit-test-only'
    return reports


def test_exactly_all_nineteen_remaining_command_rows(components):
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and r['package']=='CMD'}
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==19
    checks=component_checks(components)
    from check import supported_check
    roots={key:row for key,row in checks.items() if row['contracts']}
    assert len(roots)==76
    assert all(supported_check({'checks':checks},key,row['dimension']) for key,row in roots.items())


@pytest.mark.parametrize('defect',['analog','status','complex','arguments','verification','build','image','dimension'])
def test_composed_command_mapping_requires_every_component(components,defect):
    changed=deepcopy(components)
    targets={'analog':('complete','adjust-analog:failure'),'status':('complete','adjust-status:boundary'),
        'complex':('complete','complex-send:recovery'),'arguments':('arguments','arguments:failure'),
        'verification':('verification','retries:failure'),'build':('command','build-basic:positive')}
    if defect=='image':changed['complete']['runtime_image']='another-image'
    elif defect=='dimension':changed['complete']['checks']['complex-send:boundary']['dimension']='wrong'
    else:
        kind,key=targets[defect];changed[kind]['checks'][key]['passed']=False
    with pytest.raises(AssertionError):component_checks(changed)
